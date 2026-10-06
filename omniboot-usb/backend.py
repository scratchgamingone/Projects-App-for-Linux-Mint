#!/usr/bin/env python3
"""
backend.py - Privileged execution backend for OmniBoot USB.
Executed with root privileges (via pkexec). Communicates progress via JSON lines on stdout.
"""

import os
import sys
import time
import json
import shutil
import argparse
import subprocess
import glob

# Ensure system drives are protected
PROTECTED_MOUNTS = {
    '/', '/boot', '/boot/efi', '/home', '/var', '/usr', '[SWAP]',
    '/run/timeshift/backup', '/run/timeshift'
}

def emit(msg_type, **kwargs):
    """Output structured JSON to stdout for the GUI to read."""
    data = {"type": msg_type}
    data.update(kwargs)
    sys.stdout.write(json.dumps(data) + "\n")
    sys.stdout.flush()

def format_speed(bytes_per_sec):
    if bytes_per_sec < 1024 * 1024:
        return f"{bytes_per_sec / 1024:.1f} KB/s"
    return f"{bytes_per_sec / (1024 * 1024):.1f} MB/s"

def format_eta(seconds):
    if seconds < 0 or seconds > 86400:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m {s:02d}s"

def verify_safety(target_device):
    """Assert device is real and not a protected system drive."""
    if not os.path.exists(target_device):
        raise ValueError(f"Target device {target_device} does not exist.")

    # Query lsblk for mountpoints on this device or its partitions
    cmd = ['lsblk', '-J', '-b', '-o', 'NAME,PATH,MOUNTPOINTS', target_device]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
    except Exception as e:
        raise RuntimeError(f"Failed to query target device {target_device}: {e}")

    def check_dev(dev):
        for m in dev.get('mountpoints') or []:
            if m and m.strip() in PROTECTED_MOUNTS:
                return True
        for ch in dev.get('children', []):
            if check_dev(ch):
                return True
        return False

    for dev in data.get('blockdevices', []):
        if check_dev(dev):
            raise RuntimeError(f"ABORTED: {target_device} contains system mountpoints! Cannot erase system drive.")

def unmount_device(target_device):
    """Unmount all partitions of the target drive."""
    emit("log", message=f"Unmounting active partitions on {target_device}...")
    parts = glob.glob(f"{target_device}*")
    for p in parts:
        if p != target_device:
            subprocess.run(['umount', '-f', p], capture_output=True)
            subprocess.run(['udisksctl', 'unmount', '-b', p], capture_output=True)
    time.sleep(0.5)

def find_ventoy_partition(target_device):
    """Find the first data partition created by Ventoy."""
    time.sleep(1)
    subprocess.run(['partprobe', target_device], capture_output=True)
    subprocess.run(['udevadm', 'settle'], capture_output=True)

    # Check /dev/sdX1 or /dev/nvmeXn1p1
    base_name = os.path.basename(target_device)
    if 'nvme' in base_name or 'mmcblk' in base_name:
        p1 = f"{target_device}p1"
    else:
        p1 = f"{target_device}1"

    if os.path.exists(p1):
        return p1

    # Fallback to blkid search
    try:
        p = subprocess.run(['lsblk', '-ln', '-o', 'PATH,LABEL', target_device],
                           capture_output=True, text=True)
        for line in p.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) >= 2 and 'ventoy' in parts[1].lower():
                return parts[0]
            elif len(parts) >= 1 and parts[0] != target_device:
                return parts[0]
    except Exception:
        pass

    return p1

def action_flash_direct(target_device, iso_path):
    """Raw block write for single ISO (Linux hybrid images)."""
    verify_safety(target_device)
    unmount_device(target_device)

    total_size = os.path.getsize(iso_path)
    filename = os.path.basename(iso_path)
    emit("log", message=f"Wiping old partition signatures on {target_device}...")
    subprocess.run(['wipefs', '-a', target_device], capture_output=True)

    emit("log", message=f"Flashing {filename} directly to {target_device}...")
    chunk_size = 4 * 1024 * 1024  # 4MB chunks
    written = 0
    start_time = time.time()
    last_update = 0

    with open(iso_path, 'rb') as in_f, open(target_device, 'wb') as out_f:
        while True:
            chunk = in_f.read(chunk_size)
            if not chunk:
                break
            out_f.write(chunk)
            written += len(chunk)

            now = time.time()
            if now - last_update >= 0.25 or written == total_size:
                elapsed = now - start_time
                speed = written / elapsed if elapsed > 0 else 0
                pct = (written / total_size) * 100.0
                rem = total_size - written
                eta = rem / speed if speed > 0 else 0

                emit("progress",
                     percent=round(pct, 1),
                     speed=format_speed(speed),
                     eta=format_eta(eta),
                     status=f"Writing {filename} ({written // (1024*1024)} MB / {total_size // (1024*1024)} MB)...",
                     bytes_written=written,
                     total_bytes=total_size)
                last_update = now

        emit("sync", message="Flushing OS write cache to USB drive (please wait)...")
        out_f.flush()
        os.fsync(out_f.fileno())

    subprocess.run(['sync'], check=True)
    subprocess.run(['partprobe', target_device], capture_output=True)
    emit("success", message=f"Successfully flashed {filename} to {target_device}!")

def action_install_ventoy(target_device, iso_paths, ventoy_dir=None, gpt=False, single_auto=None):
    """
    Install Ventoy bootloader and optionally copy ISO files.
    If single_auto is provided (Windows ISO path), configures ventoy.json for direct auto-boot!
    """
    verify_safety(target_device)
    unmount_device(target_device)

    # Determine ventoy directory
    if not ventoy_dir or not os.path.isdir(ventoy_dir):
        # Look in known locations
        candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ventoy'),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ventoy-1.1.17'),
            '/usr/lib/omniboot-usb/ventoy',
            '/home/sam/Projects/omniboot-usb/ventoy-1.1.17',
            '/home/sam/omniboot-usb/ventoy-1.1.17',
        ]
        for c in candidates:
            if os.path.isfile(os.path.join(c, 'Ventoy2Disk.sh')):
                ventoy_dir = c
                break

    if not ventoy_dir or not os.path.isfile(os.path.join(ventoy_dir, 'Ventoy2Disk.sh')):
        raise RuntimeError("Ventoy installation directory not found!")

    emit("log", message=f"Installing Ventoy bootloader on {target_device}...")
    vtoy_script = os.path.join(ventoy_dir, 'Ventoy2Disk.sh')

    args = [vtoy_script, '-I']
    if gpt:
        args.append('-g')
    args.append(target_device)

    # Pipe "y\ny\n" to answer Ventoy confirmations
    proc = subprocess.Popen(
        args,
        cwd=ventoy_dir,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    stdout, _ = proc.communicate(input="y\ny\n")

    if proc.returncode != 0:
        raise RuntimeError(f"Ventoy installation failed:\n{stdout}")

    emit("log", message="Ventoy bootloader installed. Locating data partition...")
    part1 = find_ventoy_partition(target_device)
    emit("log", message=f"Found Ventoy partition: {part1}")

    # Prepare temporary mount point
    mount_dir = "/mnt/omniboot_ventoy_tmp"
    os.makedirs(mount_dir, exist_ok=True)

    try:
        emit("log", message=f"Mounting {part1} to {mount_dir}...")
        # Try exfat mount
        m_res = subprocess.run(['mount', part1, mount_dir], capture_output=True, text=True)
        if m_res.returncode != 0:
            # Fallback with explicit exfat
            subprocess.run(['mount', '-t', 'exfat', part1, mount_dir], check=True)

        # If single_auto mode (dedicated single Windows or Linux boot):
        if single_auto:
            vtoy_cfg_dir = os.path.join(mount_dir, 'ventoy')
            os.makedirs(vtoy_cfg_dir, exist_ok=True)
            iso_fn = os.path.basename(single_auto)
            vtoy_cfg = {
                "control": [
                    { "VTOY_DEFAULT_IMAGE": f"/{iso_fn}" },
                    { "VTOY_MENU_TIMEOUT": "2" },
                    { "VTOY_WIN11_BYPASS_CHECK": "1" },
                    { "VTOY_WIN11_BYPASS_NRO": "1" }
                ]
            }
            with open(os.path.join(vtoy_cfg_dir, 'ventoy.json'), 'w') as f:
                json.dump(vtoy_cfg, f, indent=4)
            emit("log", message=f"Configured Ventoy dedicated auto-boot for {iso_fn} (Win11 bypass enabled).")

        # Copy ISOs
        if iso_paths:
            total_bytes = sum(os.path.getsize(p) for p in iso_paths if os.path.isfile(p))
            cumulative_written = 0
            chunk_size = 4 * 1024 * 1024

            for idx, iso_path in enumerate(iso_paths):
                if not os.path.isfile(iso_path):
                    continue
                filename = os.path.basename(iso_path)
                file_size = os.path.getsize(iso_path)
                dest_path = os.path.join(mount_dir, filename)

                emit("log", message=f"Copying {filename} ({idx+1}/{len(iso_paths)})...")
                file_written = 0
                start_time = time.time()
                last_update = 0

                with open(iso_path, 'rb') as src, open(dest_path, 'wb') as dst:
                    while True:
                        buf = src.read(chunk_size)
                        if not buf:
                            break
                        dst.write(buf)
                        file_written += len(buf)
                        cumulative_written += len(buf)

                        now = time.time()
                        if now - last_update >= 0.25 or cumulative_written == total_bytes:
                            elapsed = now - start_time
                            speed = file_written / elapsed if elapsed > 0 else 0
                            pct = (cumulative_written / total_bytes) * 100.0
                            rem = total_bytes - cumulative_written
                            eta = rem / speed if speed > 0 else 0

                            emit("progress",
                                 percent=round(pct, 1),
                                 speed=format_speed(speed),
                                 eta=format_eta(eta),
                                 status=f"Copying {filename} [{idx+1}/{len(iso_paths)}]...",
                                 bytes_written=cumulative_written,
                                 total_bytes=total_bytes)
                            last_update = now

                    dst.flush()
                    os.fsync(dst.fileno())

        emit("sync", message="Flushing disk writes (syncing USB drive)...")
        subprocess.run(['sync'], check=True)

    finally:
        emit("log", message="Unmounting Ventoy data partition...")
        subprocess.run(['umount', '-f', mount_dir], capture_output=True)
        if os.path.exists(mount_dir):
            try:
                os.rmdir(mount_dir)
            except Exception:
                pass

    emit("success", message=f"Ventoy Multi-Boot USB setup completed successfully on {target_device}!")

def main():
    parser = argparse.ArgumentParser(description="OmniBoot Privileged Backend Worker")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # Flash direct
    p_flash = subparsers.add_parser("flash")
    p_flash.add_argument("--device", required=True, help="Target device node, e.g. /dev/sdb")
    p_flash.add_argument("--iso", required=True, help="Path to ISO file")

    # Ventoy
    p_ventoy = subparsers.add_parser("ventoy")
    p_ventoy.add_argument("--device", required=True, help="Target device node, e.g. /dev/sdb")
    p_ventoy.add_argument("--iso", action="append", default=[], help="Path to ISO file (can repeat)")
    p_ventoy.add_argument("--gpt", action="store_true", help="Use GPT partition style")
    p_ventoy.add_argument("--single-auto", default=None, help="Configure single auto-boot for this ISO")
    p_ventoy.add_argument("--ventoy-dir", default=None, help="Custom Ventoy directory")

    args = parser.parse_args()

    try:
        if args.action == "flash":
            action_flash_direct(args.device, args.iso)
        elif args.action == "ventoy":
            action_install_ventoy(
                target_device=args.device,
                iso_paths=args.iso,
                ventoy_dir=args.ventoy_dir,
                gpt=args.gpt,
                single_auto=args.single_auto
            )
    except Exception as e:
        emit("error", message=str(e))
        sys.exit(1)

if __name__ == '__main__':
    main()
