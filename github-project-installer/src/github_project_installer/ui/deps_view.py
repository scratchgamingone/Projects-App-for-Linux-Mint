"""
Dependencies & Project Setup Viewer:
Displays detected frameworks, configuration files, and suggested installation commands.
"""

from typing import Dict, Any, Callable, Optional

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Pango


class DepsViewWidget(Gtk.Box):
    """Visualizes detected frameworks, build systems, and provides 1-click execution."""

    def __init__(self, on_run_command: Optional[Callable[[str], None]] = None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.on_run_command = on_run_command
        self.set_margin_top(16)
        self.set_margin_bottom(16)
        self.set_margin_start(16)
        self.set_margin_end(16)

        # Scrolled container
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self.content_box)
        self.pack_start(scrolled, True, True, 0)

        # Initial placeholder
        self._show_placeholder()

    def _show_placeholder(self):
        for child in self.content_box.get_children():
            self.content_box.remove(child)

        lbl = Gtk.Label(label="Inspect a repository to detect project dependencies and build systems.")
        lbl.get_style_context().add_class("repo-owner")
        lbl.set_margin_top(40)
        self.content_box.pack_start(lbl, True, True, 0)
        self.show_all()

    def set_detected_info(self, detected: Dict[str, Any], project_name: str):
        """Populates cards based on detected project metadata."""
        for child in self.content_box.get_children():
            self.content_box.remove(child)

        # 1. Summary Card
        summary_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        summary_card.get_style_context().add_class("repo-card")

        lbl_head = Gtk.Label(label=f"Project Analysis: {project_name}")
        lbl_head.get_style_context().add_class("repo-title")
        lbl_head.set_halign(Gtk.Align.START)
        summary_card.pack_start(lbl_head, False, False, 0)

        lbl_summary = Gtk.Label(label=detected.get("summary", "Generic Project"))
        lbl_summary.get_style_context().add_class("repo-desc")
        lbl_summary.set_halign(Gtk.Align.START)
        lbl_summary.set_line_wrap(True)
        summary_card.pack_start(lbl_summary, False, False, 0)

        self.content_box.pack_start(summary_card, False, False, 0)

        # 2. Detected Configuration Files
        configs = detected.get("configs", [])
        if configs:
            cfg_frame = Gtk.Frame(label=" Detected Configuration & Package Files ")
            cfg_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            cfg_box.set_margin_top(8)
            cfg_box.set_margin_bottom(8)
            cfg_box.set_margin_start(10)
            cfg_box.set_margin_end(10)

            for cfg in configs:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                icon = Gtk.Image.new_from_icon_name("text-x-generic", Gtk.IconSize.BUTTON)
                row.pack_start(icon, False, False, 0)

                lbl_file = Gtk.Label(label=f"<b>{cfg['file']}</b>")
                lbl_file.set_use_markup(True)
                lbl_file.set_halign(Gtk.Align.START)
                row.pack_start(lbl_file, False, False, 0)

                lbl_type = Gtk.Label(label=f"({cfg['type']})")
                lbl_type.get_style_context().add_class("repo-owner")
                row.pack_start(lbl_type, False, False, 0)

                cfg_box.pack_start(row, False, False, 0)

            cfg_frame.add(cfg_box)
            self.content_box.pack_start(cfg_frame, False, False, 0)

        # 3. Suggested Installation Commands
        install_cmds = detected.get("install_commands", [])
        if install_cmds:
            inst_frame = Gtk.Frame(label=" Suggested Installation Commands ")
            inst_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            inst_box.set_margin_top(8)
            inst_box.set_margin_bottom(8)
            inst_box.set_margin_start(10)
            inst_box.set_margin_end(10)

            for cmd in install_cmds:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                lbl_cmd = Gtk.Label(label=f"<code>{cmd}</code>")
                lbl_cmd.set_use_markup(True)
                lbl_cmd.set_halign(Gtk.Align.START)
                row.pack_start(lbl_cmd, True, True, 0)

                btn_run = Gtk.Button(label="⚡ Run Command")
                btn_run.get_style_context().add_class("btn-action")
                btn_run.connect("clicked", lambda b, c=cmd: self._run_command(c))
                row.pack_end(btn_run, False, False, 0)

                inst_box.pack_start(row, False, False, 0)

            inst_frame.add(inst_box)
            self.content_box.pack_start(inst_frame, False, False, 0)

        # 4. Suggested Run / Launch Commands
        run_cmds = detected.get("run_commands", [])
        if run_cmds:
            run_frame = Gtk.Frame(label=" Suggested Launch Commands ")
            run_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            run_box.set_margin_top(8)
            run_box.set_margin_bottom(8)
            run_box.set_margin_start(10)
            run_box.set_margin_end(10)

            for cmd in run_cmds:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                lbl_cmd = Gtk.Label(label=f"<code>{cmd}</code>")
                lbl_cmd.set_use_markup(True)
                lbl_cmd.set_halign(Gtk.Align.START)
                row.pack_start(lbl_cmd, True, True, 0)

                btn_run = Gtk.Button(label="▶ Run")
                btn_run.get_style_context().add_class("btn-action")
                btn_run.connect("clicked", lambda b, c=cmd: self._run_command(c))
                row.pack_end(btn_run, False, False, 0)

                run_box.pack_start(row, False, False, 0)

            run_frame.add(run_box)
            self.content_box.pack_start(run_frame, False, False, 0)

        self.show_all()

    def _run_command(self, cmd: str):
        if self.on_run_command:
            self.on_run_command(cmd)
