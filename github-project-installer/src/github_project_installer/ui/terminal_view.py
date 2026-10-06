"""
Execution Console & Live Log View.
Streams installation outputs, script executions, and system commands line-by-line
with ANSI color stripping, timestamps, auto-scroll, and process control.
"""

import os
import signal
import subprocess
import threading
from datetime import datetime
from typing import Optional, Callable

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Pango


class TerminalViewWidget(Gtk.Box):
    """Real-time console output view for extraction, git, and install commands."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.active_proc: Optional[subprocess.Popen] = None
        self.active_thread: Optional[threading.Thread] = None

        # 1. Top Controls Bar
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        top_bar.get_style_context().add_class("code-header-bar")

        self.lbl_status = Gtk.Label(label="Console Ready")
        self.lbl_status.set_halign(Gtk.Align.START)
        top_bar.pack_start(self.lbl_status, True, True, 0)

        # Stop Button
        self.btn_stop = Gtk.Button(label="⏹ Stop Process")
        self.btn_stop.get_style_context().add_class("btn-action")
        self.btn_stop.set_sensitive(False)
        self.btn_stop.connect("clicked", self._on_stop_clicked)
        top_bar.pack_end(self.btn_stop, False, False, 0)

        # Clear Button
        btn_clear = Gtk.Button()
        btn_clear.set_tooltip_text("Clear Console")
        btn_clear.set_image(Gtk.Image.new_from_icon_name("edit-clear-symbolic", Gtk.IconSize.BUTTON))
        btn_clear.connect("clicked", lambda b: self.clear())
        top_bar.pack_end(btn_clear, False, False, 0)

        self.pack_start(top_bar, False, False, 0)

        # 2. Text View Console
        self.text_buffer = Gtk.TextBuffer()
        self.text_view = Gtk.TextView.new_with_buffer(self.text_buffer)
        self.text_view.set_editable(False)
        self.text_view.set_cursor_visible(False)
        self.text_view.set_monospace(True)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.text_view.set_left_margin(12)
        self.text_view.set_right_margin(12)
        self.text_view.set_top_margin(10)
        self.text_view.set_bottom_margin(10)

        # Dark console background
        self.text_view.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0.06, 0.08, 0.11, 1.0))
        self.text_view.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0.9, 0.95, 0.98, 1.0))

        # Color Tags
        self.tag_info = self.text_buffer.create_tag("info", foreground="#38bdf8")
        self.tag_success = self.text_buffer.create_tag("success", foreground="#34d399", weight=Pango.Weight.BOLD)
        self.tag_error = self.text_buffer.create_tag("error", foreground="#f87171", weight=Pango.Weight.BOLD)
        self.tag_dim = self.text_buffer.create_tag("dim", foreground="#64748b")
        self.tag_bold = self.text_buffer.create_tag("bold", weight=Pango.Weight.BOLD)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scrolled.add(self.text_view)
        self.pack_start(self.scrolled, True, True, 0)

    def log(self, text: str, tag: Optional[str] = None):
        """Thread-safe append text to console."""
        def _append():
            ts = datetime.now().strftime("%H:%M:%S")
            iter_end = self.text_buffer.get_end_iter()
            self.text_buffer.insert_with_tags_by_name(iter_end, f"[{ts}] ", "dim")

            iter_end = self.text_buffer.get_end_iter()
            if tag:
                self.text_buffer.insert_with_tags_by_name(iter_end, f"{text}\n", tag)
            else:
                self.text_buffer.insert(iter_end, f"{text}\n")

            # Scroll to bottom
            mark = self.text_buffer.create_mark(None, self.text_buffer.get_end_iter(), False)
            self.text_view.scroll_to_mark(mark, 0.05, False, 0.0, 1.0)
            return False

        GLib.idle_add(_append)

    def clear(self):
        """Clears the console text."""
        self.text_buffer.set_text("")
        self.lbl_status.set_text("Console Ready")

    def run_command(self, cmd: list, cwd: str, on_finished: Optional[Callable[[int], None]] = None):
        """Executes a command asynchronously and streams its stdout/stderr line by line."""
        if self.active_proc and self.active_proc.poll() is None:
            self.log("A process is already running. Please stop it first.", "error")
            return

        cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        self.log(f"⚡ Running command in {cwd}:", "info")
        self.log(f"$ {cmd_str}\n", "bold")
        self.btn_stop.set_sensitive(True)
        self.lbl_status.set_text(f"Running: {cmd[0] if isinstance(cmd, list) else cmd}...")

        def _worker():
            try:
                self.active_proc = subprocess.Popen(
                    cmd,
                    cwd=cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    preexec_fn=os.setsid,
                )

                for line in iter(self.active_proc.stdout.readline, ""):
                    clean_line = line.rstrip()
                    if clean_line:
                        # Detect errors or success strings
                        tag = None
                        lower = clean_line.lower()
                        if "error" in lower or "failed" in lower or "fatal" in lower:
                            tag = "error"
                        elif "success" in lower or "done" in lower or "installed" in lower:
                            tag = "success"
                        self.log(clean_line, tag)

                self.active_proc.stdout.close()
                rc = self.active_proc.wait()

                def _finish():
                    self.btn_stop.set_sensitive(False)
                    if rc == 0:
                        self.lbl_status.set_text("Process completed successfully (Exit code 0)")
                        self.log("✓ Command completed successfully.", "success")
                    else:
                        self.lbl_status.set_text(f"Process failed (Exit code {rc})")
                        self.log(f"✗ Command finished with exit code {rc}", "error")

                    if on_finished:
                        on_finished(rc)
                    return False

                GLib.idle_add(_finish)

            except Exception as e:
                def _error():
                    self.btn_stop.set_sensitive(False)
                    self.lbl_status.set_text("Command failed to start")
                    self.log(f"Failed to execute command: {e}", "error")
                    if on_finished:
                        on_finished(-1)
                    return False
                GLib.idle_add(_error)

        self.active_thread = threading.Thread(target=_worker, daemon=True)
        self.active_thread.start()

    def _on_stop_clicked(self, btn):
        """Kills the active process group."""
        if self.active_proc and self.active_proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.active_proc.pid), signal.SIGTERM)
                self.log("Process stopped by user (SIGTERM sent).", "error")
            except Exception as e:
                self.log(f"Error stopping process: {e}", "error")
            self.btn_stop.set_sensitive(False)
            self.lbl_status.set_text("Process stopped")
