#!/usr/bin/env python3
"""
Mint Auto Clicker entry point.
"""

import os
import signal
import sys

# Ensure package directory is in sys.path
package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if package_dir not in sys.path:
    sys.path.insert(0, package_dir)

from mint_autoclicker import __version__
from mint_autoclicker.gui import run_gui


def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip()
        if arg in ("--version", "-v"):
            print(f"Mint Auto Clicker v{__version__}")
            sys.exit(0)
        elif arg in ("--help", "-h"):
            print("Mint Auto Clicker - Fast, modern auto clicker for Linux Mint")
            print("\nUsage:")
            print("  mint-autoclicker         Launch the graphical user interface")
            print("  mint-autoclicker -v      Display version information")
            print("  mint-autoclicker -h      Display this help message")
            sys.exit(0)

    # Clean exit on Ctrl+C in terminal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    run_gui()


if __name__ == "__main__":
    main()
