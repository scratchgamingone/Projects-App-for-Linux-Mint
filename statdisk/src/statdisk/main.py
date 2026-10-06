"""
StatDisk Entry Point.
Runs the Gtk.Application and coordinates window lifecycle.
"""

import sys
import os
import signal

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, Gio, GLib

from statdisk.ui.main_window import MainWindow


class StatDiskApp(Gtk.Application):
    """Main Gtk.Application subclass."""

    def __init__(self, initial_path: str = None):
        super().__init__(
            application_id="io.github.statdisk.analyzer",
            flags=Gio.ApplicationFlags.NON_UNIQUE
        )
        self.initial_path = initial_path
        self.window = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self._load_css()
        self._setup_icons()

    def do_activate(self):
        if not self.window:
            self.window = MainWindow(application=self)
            self.window.connect('destroy', self._on_window_destroy)
            self.window.show_all()

            # Start scan on startup if path was supplied, or default to Home
            scan_target = self.initial_path if (self.initial_path and os.path.exists(self.initial_path)) else os.path.expanduser("~")
            GLib.idle_add(self.window.start_scan, scan_target)

        self.window.present()

    def _on_window_destroy(self, win):
        if win.scanner and win.scanner.is_running():
            win.scanner.cancel()

    def _load_css(self):
        css_provider = Gtk.CssProvider()
        # Look for style.css in assets directory
        pkg_dir = os.path.dirname(os.path.abspath(__file__))
        css_path = os.path.join(pkg_dir, "assets", "style.css")

        if os.path.exists(css_path):
            try:
                css_provider.load_from_path(css_path)
                screen = Gdk.Screen.get_default()
                if screen:
                    Gtk.StyleContext.add_provider_for_screen(
                        screen,
                        css_provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                    )
            except Exception as e:
                print(f"[StatDisk] Note: could not load CSS: {e}")

    def _setup_icons(self):
        # Register assets icon directory with Gtk IconTheme
        pkg_dir = os.path.dirname(os.path.abspath(__file__))
        assets_dir = os.path.join(pkg_dir, "assets")
        theme = Gtk.IconTheme.get_default()
        if theme and os.path.exists(assets_dir):
            theme.append_search_path(assets_dir)

        icon_file = os.path.join(assets_dir, "statdisk.png")
        if os.path.exists(icon_file):
            try:
                Gtk.Window.set_default_icon_from_file(icon_file)
            except Exception:
                pass


def main():
    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    initial_path = None
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        initial_path = os.path.abspath(sys.argv[1])

    app = StatDiskApp(initial_path=initial_path)
    exit_status = app.run(sys.argv[:1])
    sys.exit(exit_status)


if __name__ == "__main__":
    main()
