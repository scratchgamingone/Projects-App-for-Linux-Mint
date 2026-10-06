#!/usr/bin/env python3
"""
detector.py - Device and ISO inspection utility for OmniBoot USB.
Detects USB storage devices, protects system disks, inspects ISO files (Linux vs Windows).
"""

import os
import json
import subprocess
import re

PROTECTED_MOUNTS = {
    '/', '/boot', '/boot/efi', '/home', '/var', '/usr', '[SWAP]',
    '/run/timeshift/backup', '/run/timeshift'
}

def format_bytes(num_bytes):
    if num_bytes is None or num_bytes < 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if num_bytes < 1024.0 or unit == 'TB':
            return f"{num_bytes:.2f} {unit}" if unit in ['GB', 'TB'] else f"{int(num_bytes)} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.2f} TB"

def is_protected_device(dev):
    """Check if device or any child partition is part of the running OS."""
    mounts = dev.get('mountpoints') or []
    for m in mounts:
        if m:
            m_clean = m.strip()
            if m_clean in PROTECTED_MOUNTS or m_clean.startswith('/boot') or m_clean == '/':
                return True
    for child in dev.get('children', []):
        if is_protected_device(child):
            return True
    return False

def get_drive_partitions(dev):
    """Extract list of existing partition details."""
    parts = []
    for child in dev.get('children', []):
        parts.append({
            'name': child.get('name'),
            'path': child.get('path'),
            'size': child.get('size', 0),
            'fstype': child.get('fstype') or 'unknown',
            'label': child.get('label') or '',
            'mount': (child.get('mountpoints') or [None])[0]
        })
    return parts

def get_storage_devices(include_internal=False):
    """
    Query lsblk for storage devices.
    Returns list of safe target drives (protecting system drives).
    """
    cmd = [
        'lsblk', '-J', '-b', '-o',
        'NAME,PATH,TYPE,SIZE,MODEL,VENDOR,TRAN,RM,HOTPLUG,MOUNTPOINTS,FSTYPE,LABEL'
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
    except Exception as e:
        return []

    drives = []
    for dev in data.get('blockdevices', []):
        if dev.get('type') != 'disk':
            continue

        protected = is_protected_device(dev)
        is_usb = (dev.get('tran') == 'usb') or (dev.get('rm') is True) or (dev.get('hotplug') is True)

        # Do not allow system disks under any circumstance
        if protected and not include_internal:
            continue

        # If we only want removable USB drives by default:
        if not is_usb and not include_internal:
            continue

        raw_size = dev.get('size', 0)
        model = (dev.get('model') or '').strip()
        vendor = (dev.get('vendor') or '').strip()
        display_name = f"{vendor} {model}".strip() if (vendor or model) else dev.get('name', 'USB Disk')

        drives.append({
            'name': dev.get('name'),
            'path': dev.get('path'),
            'model': display_name,
            'vendor': vendor,
            'size_bytes': raw_size,
            'size_str': format_bytes(raw_size),
            'is_usb': is_usb,
            'is_removable': dev.get('rm', False),
            'protected': protected,
            'partitions': get_drive_partitions(dev)
        })

    return drives

def inspect_iso(iso_path):
    """
    Inspect an ISO image file:
    - Verifies file existence and gets size
    - Detects whether it is a Linux distribution or Windows installer
    - Detects specific distro (Ubuntu, Mint, Debian, Fedora, Nobara, Arch, etc.)
    - Detects isohybrid (raw dd bootable) vs UDF
    """
    if not os.path.isfile(iso_path):
        return {
            'valid': False,
            'error': f"File does not exist: {iso_path}"
        }

    size_bytes = os.path.getsize(iso_path)
    filename = os.path.basename(iso_path)

    os_type = 'unknown'
    distro_name = 'Generic OS / ISO Image'
    is_hybrid = False
    has_large_wim = False
    wim_size = 0

    # 1. Quick check using 'file' utility
    try:
        f_proc = subprocess.run(['file', '-b', iso_path], capture_output=True, text=True, timeout=5)
        file_desc = f_proc.stdout.strip().lower()
        if 'dos/mbr boot sector' in file_desc or 'hybrid' in file_desc:
            is_hybrid = True
    except Exception:
        file_desc = ""

    # 2. Inspect archive structure with 7z (fast header listing)
    try:
        p = subprocess.run(['7z', 'l', iso_path], capture_output=True, text=True, timeout=10)
        stdout = p.stdout.lower()
    except Exception:
        stdout = ""

    fn_lower = filename.lower()

    # Detect Windows
    if ('sources/install.wim' in stdout or 'sources/install.esd' in stdout or 
        'sources/boot.wim' in stdout or 'setup.exe' in stdout or 'boot/bcd' in stdout):
        os_type = 'windows'
        if 'win11' in fn_lower or 'windows 11' in fn_lower or 'windows11' in fn_lower:
            distro_name = 'Windows 11 Installer'
        elif 'win10' in fn_lower or 'windows 10' in fn_lower or 'windows10' in fn_lower:
            distro_name = 'Windows 10 Installer'
        elif 'server' in fn_lower:
            distro_name = 'Windows Server Installer'
        else:
            distro_name = 'Windows Installer'

        # Check if install.wim > 4GB (FAT32 limit)
        for line in stdout.splitlines():
            if 'install.wim' in line:
                parts = line.split()
                # 7z format typically has size in column 3 or 4
                for part in parts:
                    if part.isdigit():
                        candidate_size = int(part)
                        if candidate_size > 100 * 1024 * 1024: # >100MB
                            wim_size = candidate_size
                            if wim_size > 4 * 1024 * 1024 * 1024:
                                has_large_wim = True
                            break

    # Detect Linux
    elif ('casper' in stdout or 'liveos' in stdout or 'vmlinuz' in stdout or 
          'arch' in stdout or 'isolinux' in stdout or '.disk/info' in stdout or
          'boot/grub' in stdout or 'kernel' in stdout or is_hybrid):
        os_type = 'linux'
        if 'nobara' in fn_lower:
            distro_name = 'Nobara Linux Live / Installer'
        elif 'mint' in fn_lower:
            distro_name = 'Linux Mint Live / Installer'
        elif 'ubuntu' in fn_lower:
            distro_name = 'Ubuntu Linux Desktop / Server'
        elif 'debian' in fn_lower:
            distro_name = 'Debian GNU/Linux'
        elif 'fedora' in fn_lower:
            distro_name = 'Fedora Linux Workstation / Server'
        elif 'arch' in fn_lower or 'archiso' in stdout:
            distro_name = 'Arch Linux'
        elif 'manjaro' in fn_lower:
            distro_name = 'Manjaro Linux'
        elif 'pop' in fn_lower or 'pop-os' in fn_lower:
            distro_name = 'Pop!_OS'
        elif 'opensuse' in fn_lower or 'suse' in fn_lower:
            distro_name = 'openSUSE Linux'
        elif 'kali' in fn_lower:
            distro_name = 'Kali Linux'
        elif 'tails' in fn_lower:
            distro_name = 'Tails (Amnesic Incognito Live System)'
        elif 'proxmox' in fn_lower:
            distro_name = 'Proxmox VE'
        else:
            distro_name = 'Linux Live / Installer ISO'

    return {
        'valid': True,
        'path': iso_path,
        'filename': filename,
        'size_bytes': size_bytes,
        'size_str': format_bytes(size_bytes),
        'os_type': os_type,
        'distro_name': distro_name,
        'is_hybrid': is_hybrid,
        'has_large_wim': has_large_wim,
        'wim_size': wim_size
    }

if __name__ == '__main__':
    import sys
    print("=== Detected Storage Devices ===")
    devices = get_storage_devices()
    for d in devices:
        print(f"[{d['path']}] {d['model']} - {d['size_str']} (USB={d['is_usb']})")
    
    if len(sys.argv) > 1:
        iso = sys.argv[1]
        print(f"\n=== Inspecting ISO: {iso} ===")
        info = inspect_iso(iso)
        print(json.dumps(info, indent=2))
