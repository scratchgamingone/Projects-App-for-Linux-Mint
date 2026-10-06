import sys
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

from .window import MainWindow

CSS_DATA = b"""
.size-label {
    font-weight: bold;
    font-size: 1.1em;
    color: #4a90e2;
}
.dim-label {
    opacity: 0.65;
    font-size: 0.9em;
}
"""

def main():
    # Load custom CSS
    screen = Gdk.Screen.get_default()
    if screen:
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(CSS_DATA)
        context = Gtk.StyleContext()
        context.add_provider_for_screen(screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    win = MainWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    # Hide the spinner initially
    win.spinner.hide()
    Gtk.main()

if __name__ == "__main__":
    main()
