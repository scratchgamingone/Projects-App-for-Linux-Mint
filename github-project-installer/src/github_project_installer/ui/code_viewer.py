"""
Code Viewer: Syntax-highlighted code editor with line numbers, search, and language detection.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, Pango

try:
    gi.require_version('GtkSource', '3.0')
    from gi.repository import GtkSource
    HAS_GTKSOURCE = True
except Exception:
    HAS_GTKSOURCE = False

from github_project_installer.core.git_inspector import format_bytes


class CodeViewerWidget(Gtk.Box):
    """Source code viewer with syntax highlighting and line numbers."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.current_abs_path: Optional[str] = None
        self.current_rel_path: Optional[str] = None
        self.raw_content: str = ""

        # 1. Top Header Bar
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.get_style_context().add_class("code-header-bar")

        # File Icon & Name Label
        self.lbl_path = Gtk.Label(label="No file selected")
        self.lbl_path.set_halign(Gtk.Align.START)
        self.lbl_path.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        header.pack_start(self.lbl_path, True, True, 0)

        # File stats pill
        self.lbl_stats = Gtk.Label(label="")
        self.lbl_stats.get_style_context().add_class("badge-pill")
        self.lbl_stats.get_style_context().add_class("badge-branch")
        header.pack_start(self.lbl_stats, False, False, 0)

        # Word wrap toggle
        self.btn_wrap = Gtk.ToggleButton()
        self.btn_wrap.set_tooltip_text("Toggle Word Wrap")
        self.btn_wrap.set_image(Gtk.Image.new_from_icon_name("format-justify-fill-symbolic", Gtk.IconSize.BUTTON))
        self.btn_wrap.connect("toggled", self._on_toggle_wrap)
        header.pack_end(self.btn_wrap, False, False, 0)

        # Copy button
        btn_copy = Gtk.Button()
        btn_copy.set_tooltip_text("Copy file content")
        btn_copy.set_image(Gtk.Image.new_from_icon_name("edit-copy-symbolic", Gtk.IconSize.BUTTON))
        btn_copy.connect("clicked", self._on_copy_code)
        header.pack_end(btn_copy, False, False, 0)

        # Open in external editor button
        btn_open = Gtk.Button()
        btn_open.set_tooltip_text("Open with system editor")
        btn_open.set_image(Gtk.Image.new_from_icon_name("document-open-symbolic", Gtk.IconSize.BUTTON))
        btn_open.connect("clicked", self._on_open_external)
        header.pack_end(btn_open, False, False, 0)

        self.pack_start(header, False, False, 0)

        # 2. Source View & Buffer
        if HAS_GTKSOURCE:
            self.source_buffer = GtkSource.Buffer()
            self.lang_manager = GtkSource.LanguageManager.get_default()
            self.scheme_manager = GtkSource.StyleSchemeManager.get_default()

            # Set dark scheme
            for scheme_id in ["catppuccin-mocha", "tokyo-night", "oblivion", "solarized-dark"]:
                scheme = self.scheme_manager.get_scheme(scheme_id)
                if scheme:
                    self.source_buffer.set_style_scheme(scheme)
                    break

            self.view = GtkSource.View.new_with_buffer(self.source_buffer)
            self.view.set_show_line_numbers(True)
            self.view.set_highlight_current_line(True)
            self.view.set_show_line_marks(False)
            self.view.set_tab_width(4)
            self.view.set_indent_width(4)
            self.view.set_insert_spaces_instead_of_tabs(True)
            self.view.set_editable(False)
            self.view.set_monospace(True)
        else:
            self.source_buffer = Gtk.TextBuffer()
            self.view = Gtk.TextView.new_with_buffer(self.source_buffer)
            self.view.set_editable(False)
            self.view.set_monospace(True)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self.view)
        self.pack_start(scrolled, True, True, 0)

    def load_file(self, abs_path: str, rel_path: str):
        """Loads and displays file content with auto syntax detection."""
        self.current_abs_path = abs_path
        self.current_rel_path = rel_path

        p = Path(abs_path)
        if not p.is_file():
            self.source_buffer.set_text("File does not exist.")
            return

        # Check file size (cap preview at 5MB)
        file_size = p.stat().st_size
        if file_size > 5 * 1024 * 1024:
            self.source_buffer.set_text(
                f"File is too large to preview directly ({format_bytes(file_size)}).\n"
                "Please use 'Open with system editor' to view this file."
            )
            self.lbl_path.set_text(f"📄 {rel_path}")
            self.lbl_stats.set_text(format_bytes(file_size))
            return

        # Read content
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            self.raw_content = content
        except Exception as e:
            self.raw_content = ""
            self.source_buffer.set_text(f"Error reading file: {e}")
            return

        self.source_buffer.set_text(self.raw_content)

        # Detect language
        lang_name = "Text"
        if HAS_GTKSOURCE:
            lang = self.lang_manager.guess_language(p.name, None)
            if lang:
                self.source_buffer.set_language(lang)
                lang_name = lang.get_name()
            else:
                self.source_buffer.set_language(None)

        line_count = len(self.raw_content.splitlines())
        self.lbl_path.set_text(f"📄 {rel_path}")
        self.lbl_stats.set_text(f"{format_bytes(file_size)} • {line_count:,} lines • {lang_name}")

    def _on_toggle_wrap(self, btn):
        if btn.get_active():
            self.view.set_wrap_mode(Gtk.WrapMode.WORD)
        else:
            self.view.set_wrap_mode(Gtk.WrapMode.NONE)

    def _on_copy_code(self, btn):
        if self.raw_content:
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(self.raw_content, -1)

    def _on_open_external(self, btn):
        if self.current_abs_path and os.path.exists(self.current_abs_path):
            try:
                subprocess.Popen(["xdg-open", self.current_abs_path])
            except Exception as e:
                print(f"Failed to open external editor: {e}")
