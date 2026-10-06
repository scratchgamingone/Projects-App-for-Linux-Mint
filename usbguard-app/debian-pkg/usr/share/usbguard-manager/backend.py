"""
Backend interface for USBGuard.
Communicates with the USBGuard CLI/IPC and falls back to sysfs when needed.
"""

import os
import subprocess
import shutil
import re
from typing import List, Tuple, Optional, Dict
from models import USBDevice, USBRule, parse_device_line, parse_rule_line, decode_interface_class

HELPER_BIN = "/usr/lib/usbguard-manager/usbguard-helper"
DAEMON_CONF = "/etc/usbguard/usbguard-daemon.conf"
RULES_CONF = "/etc/usbguard/rules.conf"

class USBGuardBackend:
    def __init__(self):
        self.usbguard_bin = shutil.which("usbguard") or "/usr/bin/usbguard"

    def is_installed(self) -> bool:
        return os.path.exists(self.usbguard_bin)

    def is_service_active(self) -> bool:
        try:
            res = subprocess.run(
                ["systemctl", "is-active", "--quiet", "usbguard"],
                check=False
            )
            return res.returncode == 0
        except Exception:
            return False

    def get_implicit_policy(self) -> str:
        """Returns 'block', 'allow', or 'unknown'."""
        if not os.path.exists(DAEMON_CONF):
            return "block"  # default
        try:
            with open(DAEMON_CONF, "r", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("#"):
                        continue
                    if line.startswith("ImplicitPolicyTarget="):
                        val = line.split("=", 1)[1].strip().lower()
                        return val
        except Exception:
            pass
        return "block"

    def list_rules(self) -> List[USBRule]:
        """Lists permanent rules currently stored in the USBGuard policy."""
        rules: List[USBRule] = []
        if not self.is_installed() or not self.is_service_active():
            # Try reading rules.conf directly if accessible
            if os.path.exists(RULES_CONF) and os.access(RULES_CONF, os.R_OK):
                try:
                    with open(RULES_CONF, "r") as f:
                        for idx, line in enumerate(f, 1):
                            parsed = parse_rule_line(f"{idx}: {line}")
                            if parsed:
                                rules.append(parsed)
                except Exception:
                    pass
            return rules

        try:
            res = subprocess.run(
                [self.usbguard_bin, "list-rules"],
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    r = parse_rule_line(line)
                    if r:
                        rules.append(r)
        except Exception as e:
            print(f"[USBGuard] Error listing rules: {e}")

        return rules

    def list_devices(self) -> List[USBDevice]:
        """Lists connected USB devices via usbguard or fallback sysfs."""
        active_rules = self.list_rules()
        trusted_dev_ids = {r.device_id for r in active_rules if r.is_allow and r.device_id}
        trusted_serials = {r.serial for r in active_rules if r.is_allow and r.serial}

        devices: List[USBDevice] = []

        if self.is_installed() and self.is_service_active():
            try:
                res = subprocess.run(
                    [self.usbguard_bin, "list-devices"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        dev = parse_device_line(line)
                        if dev:
                            # Determine if matched by trusted rule
                            if (dev.device_id and dev.device_id in trusted_dev_ids) or \
                               (dev.serial and dev.serial in trusted_serials):
                                dev.is_trusted = True
                            devices.append(dev)
                    return devices
            except Exception as e:
                print(f"[USBGuard] Error running list-devices: {e}")

        # Fallback to sysfs direct enumeration if usbguard service is not running
        return self._list_devices_from_sysfs(trusted_dev_ids, trusted_serials)

    def _list_devices_from_sysfs(self, trusted_ids=None, trusted_serials=None) -> List[USBDevice]:
        devices: List[USBDevice] = []
        sysfs_dir = "/sys/bus/usb/devices"
        if not os.path.isdir(sysfs_dir):
            return devices

        trusted_ids = trusted_ids or set()
        trusted_serials = trusted_serials or set()

        idx = 1
        for name in sorted(os.listdir(sysfs_dir)):
            if ":" in name:
                continue  # skip interfaces
            p = os.path.join(sysfs_dir, name)
            vid_file = os.path.join(p, "idVendor")
            pid_file = os.path.join(p, "idProduct")
            if not os.path.exists(vid_file) or not os.path.exists(pid_file):
                continue

            try:
                with open(vid_file) as f:
                    vid = f.read().strip().lower()
                with open(pid_file) as f:
                    pid = f.read().strip().lower()
                dev_id = f"{vid}:{pid}"

                prod_name = ""
                prod_f = os.path.join(p, "product")
                if os.path.exists(prod_f):
                    with open(prod_f, errors="ignore") as f:
                        prod_name = f.read().strip()

                serial = ""
                ser_f = os.path.join(p, "serial")
                if os.path.exists(ser_f):
                    with open(ser_f, errors="ignore") as f:
                        serial = f.read().strip()

                auth_f = os.path.join(p, "authorized")
                target = "allow"
                if os.path.exists(auth_f):
                    with open(auth_f) as f:
                        target = "allow" if f.read().strip() == "1" else "block"

                is_trusted = (dev_id in trusted_ids) or (serial and serial in trusted_serials)

                dev = USBDevice(
                    rule_id=idx,
                    target=target,
                    device_id=dev_id,
                    name=prod_name,
                    serial=serial,
                    via_port=name,
                    interfaces="",
                    is_trusted=is_trusted,
                    raw=f"{idx}: {target} id {dev_id} serial \"{serial}\" name \"{prod_name}\""
                )
                devices.append(dev)
                idx += 1
            except Exception:
                continue

        return devices

    def allow_device(self, rule_id: int, permanent: bool = True) -> Tuple[bool, str]:
        """Authorizes a device. If permanent is True, adds to trusted whitelist."""
        cmd = [self.usbguard_bin, "allow-device"]
        if permanent:
            cmd.append("-p")
        cmd.append(str(rule_id))

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                action_str = "trusted and allowed permanently" if permanent else "allowed for current session"
                return True, f"Device #{rule_id} has been {action_str}."
            err = res.stderr.strip() or res.stdout.strip() or f"Exit code {res.returncode}"
            return False, f"Failed to allow device #{rule_id}: {err}"
        except Exception as e:
            return False, f"Error: {e}"

    def block_device(self, rule_id: int, permanent: bool = False) -> Tuple[bool, str]:
        """Deauthorizes / blocks a device."""
        cmd = [self.usbguard_bin, "block-device"]
        if permanent:
            cmd.append("-p")
        cmd.append(str(rule_id))

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                return True, f"Device #{rule_id} has been blocked."
            err = res.stderr.strip() or res.stdout.strip() or f"Exit code {res.returncode}"
            return False, f"Failed to block device #{rule_id}: {err}"
        except Exception as e:
            return False, f"Error: {e}"

    def remove_rule(self, rule_id: int) -> Tuple[bool, str]:
        """Removes a permanent rule from policy."""
        try:
            res = subprocess.run(
                [self.usbguard_bin, "remove-rule", str(rule_id)],
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode == 0:
                return True, f"Rule #{rule_id} was removed from trusted list."
            err = res.stderr.strip() or res.stdout.strip()
            return False, f"Failed to remove rule #{rule_id}: {err}"
        except Exception as e:
            return False, f"Error: {e}"

    def append_rule(self, target: str, device_id: str, name: str = "", serial: str = "") -> Tuple[bool, str]:
        """Appends a new rule to policy."""
        parts = [target.lower(), "id", device_id.lower()]
        if serial:
            parts.extend(["serial", f'"{serial}"'])
        if name:
            parts.extend(["name", f'"{name}"'])
        rule_str = " ".join(parts)

        try:
            res = subprocess.run(
                [self.usbguard_bin, "append-rule", rule_str],
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode == 0:
                return True, f"Rule added: {rule_str}"
            err = res.stderr.strip() or res.stdout.strip()
            return False, f"Failed to add rule: {err}"
        except Exception as e:
            return False, f"Error: {e}"

    def run_privileged_action(self, action: str, *args) -> Tuple[bool, str]:
        """Runs an administrative action via pkexec helper."""
        cmd = ["pkexec", HELPER_BIN, action] + list(args)
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                return True, res.stdout.strip() or "Action completed successfully."
            err = res.stderr.strip() or res.stdout.strip() or f"Exit code {res.returncode}"
            return False, f"Privileged action failed: {err}"
        except Exception as e:
            return False, f"Error: {e}"

    def restart_service(self) -> Tuple[bool, str]:
        return self.run_privileged_action("restart")

    def set_implicit_policy(self, target: str) -> Tuple[bool, str]:
        """Sets default policy to 'block' or 'allow'."""
        if target not in ("block", "allow"):
            return False, "Target must be 'block' or 'allow'"
        return self.run_privileged_action("set-policy", target)

    def trust_all_current_baseline(self) -> Tuple[bool, str]:
        """Generates policy for all currently connected devices and adds them to rules."""
        return self.run_privileged_action("trust-all-current")

    def fix_permissions(self) -> Tuple[bool, str]:
        """Configures IPC access permissions so current user can use USBGuard without passwords."""
        return self.run_privileged_action("setup-permissions")
