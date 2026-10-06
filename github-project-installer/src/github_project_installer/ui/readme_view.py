"""
README Viewer: Displays rendered GitHub-flavored Markdown using WebKit2
with fallback to raw syntax-highlighted GtkSourceView.
Zero localhost / 100% in-process HTML rendering.
"""

import html
import markdown

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

try:
    gi.require_version('WebKit2', '4.1')
    from gi.repository import WebKit2
    HAS_WEBKIT = True
except Exception:
    HAS_WEBKIT = False

try:
    gi.require_version('GtkSource', '3.0')
    from gi.repository import GtkSource
    HAS_GTKSOURCE = True
except Exception:
    HAS_GTKSOURCE = False


README_CSS = """
:root {
    --bg-color: #0d1117;
    --text-color: #c9d1d9;
    --heading-color: #58a6ff;
    --border-color: #30363d;
    --code-bg: #161b22;
    --quote-border: #388bfd;
    --table-stripe: #161b22;
}

body {
    background-color: var(--bg-color);
    color: var(--text-color);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    font-size: 14px;
    line-height: 1.6;
    padding: 24px 32px;
    margin: 0;
    max-width: 900px;
}

h1, h2, h3, h4, h5, h6 {
    color: var(--heading-color);
    margin-top: 24px;
    margin-bottom: 16px;
    font-weight: 600;
    line-height: 1.25;
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 6px;
}

h1 { font-size: 2em; border-bottom: 2px solid var(--border-color); }
h2 { font-size: 1.5em; }
h3 { font-size: 1.25em; border-bottom: none; }

p, ul, ol {
    margin-top: 0;
    margin-bottom: 16px;
}

code {
    background-color: var(--code-bg);
    padding: 0.2em 0.4em;
    border-radius: 4px;
    font-family: "JetBrains Mono", "Fira Code", monospace;
    font-size: 85%;
    color: #79c0ff;
}

pre {
    background-color: var(--code-bg);
    padding: 16px;
    overflow: auto;
    font-size: 85%;
    line-height: 1.45;
    border-radius: 6px;
    border: 1px solid var(--border-color);
}

pre code {
    background-color: transparent;
    padding: 0;
    color: #e6edf3;
    font-size: 100%;
}

blockquote {
    padding: 0 1em;
    color: #8b949e;
    border-left: 0.25em solid var(--quote-border);
    margin: 0 0 16px 0;
}

table {
    border-spacing: 0;
    border-collapse: collapse;
    margin-top: 0;
    margin-bottom: 16px;
    width: 100%;
}

table th, table td {
    padding: 8px 13px;
    border: 1px solid var(--border-color);
}

table th {
    background-color: var(--code-bg);
    font-weight: 600;
}

table tr:nth-child(2n) {
    background-color: var(--table-stripe);
}

img {
    max-width: 100%;
    box-sizing: content-box;
}

hr {
    height: 0.25em;
    padding: 0;
    margin: 24px 0;
    background-color: var(--border-color);
    border: 0;
}

a {
    color: #58a6ff;
    text-decoration: none;
}
a:hover {
    text-decoration: underline;
}
"""


class ReadmeWidget(Gtk.Box):
    """Dual rendered / raw README viewer."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.raw_text = ""
        self.current_mode = "rendered"

        # 1. Top Bar
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bar.get_style_context().add_class("code-header-bar")

        self.lbl_title = Gtk.Label(label="📖 README.md")
        self.lbl_title.set_halign(Gtk.Align.START)
        bar.pack_start(self.lbl_title, True, True, 0)

        # Toggle Button: Rendered vs Raw
        self.btn_toggle = Gtk.ToggleButton(label="Show Raw Markdown")
        self.btn_toggle.connect("toggled", self._on_toggle_mode)
        bar.pack_end(self.btn_toggle, False, False, 0)

        # Copy Button
        btn_copy = Gtk.Button()
        btn_copy.set_tooltip_text("Copy README text")
        btn_copy.set_image(Gtk.Image.new_from_icon_name("edit-copy-symbolic", Gtk.IconSize.BUTTON))
        btn_copy.connect("clicked", self._on_copy_clicked)
        bar.pack_end(btn_copy, False, False, 0)

        self.pack_start(bar, False, False, 0)

        # 2. Stack container for Rendered vs Raw View
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # Rendered View (WebKit2)
        if HAS_WEBKIT:
            self.web_view = WebKit2.WebView()
            self.web_view.set_background_color(Gdk.RGBA(0.05, 0.07, 0.09, 1.0))
            self.stack.add_named(self.web_view, "rendered")
        else:
            lbl_fallback = Gtk.Label(label="WebKit2 not available. Showing raw text.")
            self.stack.add_named(lbl_fallback, "rendered")

        # Raw View (GtkSourceView / GtkTextView)
        if HAS_GTKSOURCE:
            self.source_buffer = GtkSource.Buffer()
            lm = GtkSource.LanguageManager.get_default()
            lang = lm.get_language("markdown")
            if lang:
                self.source_buffer.set_language(lang)
            self.source_view = GtkSource.View.new_with_buffer(self.source_buffer)
            self.source_view.set_show_line_numbers(True)
            self.source_view.set_editable(False)
            self.source_view.set_monospace(True)
            self.source_view.set_wrap_mode(Gtk.WrapMode.WORD)
        else:
            self.source_buffer = Gtk.TextBuffer()
            self.source_view = Gtk.TextView.new_with_buffer(self.source_buffer)
            self.source_view.set_editable(False)
            self.source_view.set_monospace(True)

        scrolled_raw = Gtk.ScrolledWindow()
        scrolled_raw.add(self.source_view)
        self.stack.add_named(scrolled_raw, "raw")

        self.pack_start(self.stack, True, True, 0)
        self.stack.set_visible_child_name("rendered")

    def set_content(self, raw_content: str, title: str = "README.md"):
        """Updates the README content in both rendered and raw views."""
        self.raw_text = raw_content
        self.lbl_title.set_text(f"📖 {title}")

        # Update Raw View
        self.source_buffer.set_text(raw_content)

        # Update Rendered View (WebKit2)
        if HAS_WEBKIT:
            try:
                html_body = markdown.markdown(
                    raw_content,
                    extensions=["extra", "tables", "fenced_code", "nl2br"],
                )
            except Exception as e:
                html_body = f"<pre>{html.escape(raw_content)}</pre>"

            full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>{README_CSS}</style>
</head>
<body>
{html_body}
</body>
</html>"""
            self.web_view.load_html(full_html, "file:///")

    def _on_toggle_mode(self, btn):
        if btn.get_active():
            btn.set_label("Show Rendered Preview")
            self.stack.set_visible_child_name("raw")
        else:
            btn.set_label("Show Raw Markdown")
            self.stack.set_visible_child_name("rendered")

    def _on_copy_clicked(self, btn):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(self.raw_text, -1)
