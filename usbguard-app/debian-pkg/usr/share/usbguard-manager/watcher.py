"""
Watcher thread for live USB device insertions, removals, and policy changes.
Sends desktop notifications when untrusted devices are plugged in and blocked.
"""

import threading
import subprocess
import time
import re
from typing import Callable, Optional
import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib

try:
    gi.require_version("Notify", "0.7")
    from gi.repository import Notify
    HAS_NOTIFY = True
except Exception:
    HAS_NOTIFY = False


class USBGuardWatcher:
    def __init__(self, backend, on_change_callback: Callable[[], None]):
        self.backend = backend
        self.on_change_callback = on_change_callback
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.poll_timer_id: Optional[int] = None
        self.notifications_enabled = True

        if HAS_NOTIFY:
            try:
                Notify.init("USBGuard Manager")
            except Exception:
                pass

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.thread.start()

        # Fallback polling timer (every 4 seconds) in case IPC events miss something or daemon reloads
        self.poll_timer_id = GLib.timeout_add_seconds(4, self._on_poll_tick)

    def stop(self):
        self.running = False
        if self.poll_timer_id is not None:
            GLib.source_remove(self.poll_timer_id)
            self.poll_timer_id = None

    def _on_poll_tick(self) -> bool:
        if not self.running:
            return False
        # Request UI refresh
        GLib.idle_add(self.on_change_callback)
        return True

    def _watch_loop(self):
        while self.running:
            if not self.backend.is_installed() or not self.backend.is_service_active():
                time.sleep(3)
                continue

            try:
                proc = subprocess.Popen(
                    [self.backend.usbguard_bin, "watch"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )

                while self.running and proc.poll() is None:
                    line = proc.stdout.readline()
                    if not line:
                        break
                    line = line.strip()
                    if not line:
                        continue

                    # Trigger UI update
                    GLib.idle_add(self.on_change_callback)

                    # Check if an untrusted device was inserted and blocked
                    if "DeviceInserted" in line or "target=block" in line or "PresenceChanged" in line:
                        if "block" in line.lower() or "reject" in line.lower():
                            self._handle_blocked_event(line)

                if proc.poll() is None:
                    proc.terminate()
            except Exception as e:
                pass

            time.sleep(2)

    def _handle_blocked_event(self, line: str):
        if not self.notifications_enabled or not HAS_NOTIFY:
            return

        # Extract device details if present in the event line
        dev_id = "Unknown"
        m_id = re.search(r'\bid\s+([0-9a-fA-F]{4}:[0-9a-fA-F]{4})\b', line)
        if m_id:
            dev_id = m_id.group(1).lower()

        name = ""
        m_name = re.search(r'\bname\s+"([^"]*)"', line)
        if m_name:
            name = m_name.group(1)

        title = "🛡️ USB Device Blocked"
        if name:
            body = f"Blocked device: '{name}' ({dev_id}).\nIt has been blocked by default security policy."
        elif dev_id != "Unknown":
            body = f"Blocked USB device ID: {dev_id}.\nIt has been blocked by default security policy."
        else:
            body = "An unknown USB device was plugged in and blocked by default security policy."

        try:
            notification = Notify.Notification.new(title, body, "security-high")
            notification.set_urgency(Notify.Urgency.CRITICAL)
            notification.show()
        except Exception:
            pass
