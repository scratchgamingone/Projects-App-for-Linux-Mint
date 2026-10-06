"""
Application entry point for Mint Script Runner.
"""

import sys
import os
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk

from .app_window import MainWindow


def main():
    # Pass optional script argument from sys.argv
    initial_script = None
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if Path(arg).is_file():
            initial_script = arg

    win = MainWindow(initial_script=initial_script)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
