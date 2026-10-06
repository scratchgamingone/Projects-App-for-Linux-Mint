#!/usr/bin/env python3
"""
USB Guard Manager - Main entry point.
"""

import sys
import os
import signal
import gi

# Ensure local module directory is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gtk, GLib

from backend import USBGuardBackend
from watcher import USBGuardWatcher
from ui import MainWindow

def main():
    GLib.set_prgname("usbguard-manager")
    GLib.set_application_name("USB Guard")

    # Allow clean exit with Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    backend = USBGuardBackend()
    
    window = None
    def on_change():
        if window:
            window.refresh_all()

    watcher = USBGuardWatcher(backend, on_change)
    window = MainWindow(backend, watcher)
    window.show_all()

    watcher.start()

    try:
        Gtk.main()
    except KeyboardInterrupt:
        pass
    finally:
        watcher.stop()

if __name__ == "__main__":
    main()
