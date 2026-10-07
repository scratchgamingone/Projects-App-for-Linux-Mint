#!/usr/bin/env python3
"""
Mint Environment Manager - Entry Point
Enforces administrator (root) privilege verification before opening the application,
with automatic PolicyKit (pkexec) elevation and graphical error dialogs.
"""

import argparse
import os
import shutil
import subprocess
import sys

# Ensure src directory is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


def show_admin_required_dialog(message: str = ""):
    """Shows a graphical GTK dialog informing user that admin is required, then exits."""
    display = os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    if display:
        try:
            import gi
            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk

            dialog = Gtk.MessageDialog(
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="🛡️ Administrator Privileges Required",
            )
            dialog.set_title("Mint Environment Manager")
            secondary = (
                "You must run this application as Administrator (root) before opening.\n"
                "This is required to read, edit, and safely write system-wide environment files (/etc/environment).\n\n"
            )
            if message:
                secondary += f"Reason: {message}\n\n"
            secondary += "Please launch from terminal using:\n  sudo mint-env-manager\nor authenticate when prompted by PolicyKit."
            dialog.format_secondary_text(secondary)
            dialog.run()
            dialog.destroy()
            return
        except Exception:
            pass

    print(
        "\n\033[91m\033[1m[ERROR] Administrator Privileges Required!\033[0m\n"
        "Mint Environment Manager must be run as Administrator (root) before opening.\n"
        "Please run:\n"
        "  \033[92msudo mint-env-manager\033[0m\n",
        file=sys.stderr,
    )


def enforce_admin_or_elevate(args: argparse.Namespace) -> bool:
    """
    Checks if running as root. If not, attempts pkexec elevation.
    If elevation is cancelled or fails, displays required dialog and exits.
    Returns True if execution can proceed as root.
    """
    if os.geteuid() == 0:
        return True

    # Check if preview or user-mode explicitly requested
    if args.no_root_check or args.preview:
        print("[Notice] Running in non-root preview mode (--preview / --no-root-check enabled).")
        return False

    display = os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    pkexec_bin = shutil.which("pkexec")

    if display and pkexec_bin:
        # Allow local root to access X11 display
        if os.environ.get("DISPLAY"):
            subprocess.run(["xhost", "+si:localuser:root"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Build pkexec command forwarding necessary graphical environment variables
        env_vars = [
            f"DISPLAY={os.environ.get('DISPLAY', '')}",
            f"XAUTHORITY={os.environ.get('XAUTHORITY', os.path.expanduser('~/.Xauthority'))}",
        ]
        if os.environ.get("WAYLAND_DISPLAY"):
            env_vars.append(f"WAYLAND_DISPLAY={os.environ['WAYLAND_DISPLAY']}")
        if os.environ.get("XDG_RUNTIME_DIR"):
            env_vars.append(f"XDG_RUNTIME_DIR={os.environ['XDG_RUNTIME_DIR']}")

        site_pkg = os.path.expanduser("~/.local/lib/python3.12/site-packages")
        py_path = f"{SCRIPT_DIR}:{site_pkg}"
        env_vars.append(f"PYTHONPATH={py_path}")

        pkexec_cmd = [
            pkexec_bin,
            "env",
        ] + env_vars + [
            sys.executable,
            os.path.abspath(__file__),
        ] + [arg for arg in sys.argv[1:] if arg not in ("--no-root-check", "--preview")]

        try:
            # Re-exec under pkexec
            res = subprocess.run(pkexec_cmd)
            # Exit with same return code (126 = user dismissed pkexec auth, 127 = pkexec auth failed)
            if res.returncode == 0:
                sys.exit(0)
            elif res.returncode in (126, 127):
                show_admin_required_dialog("Authentication was cancelled or not authorized.")
                sys.exit(res.returncode)
            else:
                sys.exit(res.returncode)
        except Exception as e:
            show_admin_required_dialog(str(e))
            sys.exit(1)

    show_admin_required_dialog("No graphical elevation helper (pkexec) or display detected.")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Mint Environment Manager - System-wide environment & API key manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-f", "--file",
        default="/etc/environment",
        help="Path to environment file (default: /etc/environment)",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Run in preview mode without requiring root privilege",
    )
    parser.add_argument(
        "--no-root-check",
        action="store_true",
        help="Bypass root privilege check (read-only operations)",
    )

    args = parser.parse_args()

    # Enforce admin privilege check before opening
    is_root = enforce_admin_or_elevate(args)

    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    try:
        from mint_env_manager.app_window import AppWindow
    except ImportError:
        from app_window import AppWindow

    # Initialize and show GTK Application Window
    win = AppWindow(target_file=args.file, is_admin=is_root)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
