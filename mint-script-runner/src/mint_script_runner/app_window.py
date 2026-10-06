"""
Main GUI window for Mint Script Runner.
Provides Drag-and-Drop script execution, admin elevation dialog, live terminal output, and GitHub settings.
"""

import os
import time
import urllib.parse
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

from .settings_manager import SettingsManager
from .detector import ScriptInspector
from .runner import ScriptRunner


class MainWindow(Gtk.Window):
    def __init__(self, initial_script=None):
        super().__init__(title="Mint Script Runner")
        self.set_default_size(860, 680)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.settings = SettingsManager()
        self.runner = ScriptRunner(self.settings)
        self.current_script_info = None
        self.start_time = None

        # Build UI
        self._build_header_bar()
        self._build_content()
        self._setup_drag_and_drop()

        # Load initial script if passed via arguments
        if initial_script and Path(initial_script).is_file():
            GLib.idle_add(lambda: self.load_script(initial_script))

    def _build_header_bar(self):
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title("Mint Script Runner")
        header.set_subtitle("Drag & Drop .sh Shell Script Executor")
        self.set_titlebar(header)

        # Tab Switcher in HeaderBar
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(200)

        stack_switcher = Gtk.StackSwitcher()
        stack_switcher.set_stack(self.stack)
        header.set_custom_title(stack_switcher)

        # Quick Run Button
        self.btn_run_header = Gtk.Button(label="▶ Run")
        self.btn_run_header.get_style_context().add_class("suggested-action")
        self.btn_run_header.set_sensitive(False)
        self.btn_run_header.connect("clicked", self.on_run_clicked)
        header.pack_end(self.btn_run_header)

        # Stop Button
        self.btn_stop_header = Gtk.Button(label="⏹ Stop")
        self.btn_stop_header.get_style_context().add_class("destructive-action")
        self.btn_stop_header.set_sensitive(False)
        self.btn_stop_header.connect("clicked", self.on_stop_clicked)
        header.pack_end(self.btn_stop_header)

    def _build_content(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(main_box)
        main_box.pack_start(self.stack, True, True, 0)

        # 1. Main Runner Page
        runner_page = self._build_runner_page()
        self.stack.add_titled(runner_page, "runner", "🚀 Script Runner")

        # 2. GitHub Settings Page
        settings_page = self._build_settings_page()
        self.stack.add_titled(settings_page, "settings", "⚙️ GitHub Settings")

    def _build_runner_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.set_margin_start(14)
        page.set_margin_end(14)
        page.set_margin_top(12)
        page.set_margin_bottom(12)

        # Drag and Drop Target Box
        self.drop_event_box = Gtk.EventBox()
        drop_frame = Gtk.Frame()
        drop_frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        self.drop_event_box.add(drop_frame)

        self.drop_inner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.drop_inner_box.set_margin_top(18)
        self.drop_inner_box.set_margin_bottom(18)
        self.drop_inner_box.set_margin_start(16)
        self.drop_inner_box.set_margin_end(16)
        drop_frame.add(self.drop_inner_box)

        # Drop message
        self.lbl_drop_title = Gtk.Label()
        self.lbl_drop_title.set_markup("<span size='large' weight='bold'>📥 Drag &amp; Drop Any .sh Script Here</span>")
        self.drop_inner_box.pack_start(self.lbl_drop_title, False, False, 0)

        self.lbl_drop_sub = Gtk.Label(label="or click below to choose a shell script from your files")
        self.lbl_drop_sub.get_style_context().add_class("dim-label")
        self.drop_inner_box.pack_start(self.lbl_drop_sub, False, False, 0)

        btn_browse = Gtk.Button(label="📁 Browse Script File...")
        btn_browse.set_halign(Gtk.Align.CENTER)
        btn_browse.connect("clicked", self.on_browse_file_clicked)
        self.drop_inner_box.pack_start(btn_browse, False, False, 4)

        page.pack_start(self.drop_event_box, False, False, 0)

        # Script Details Card (Hidden until script is loaded)
        self.card_details = Gtk.Frame(label="Script Information")
        card_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card_box.set_margin_start(12)
        card_box.set_margin_end(12)
        card_box.set_margin_top(8)
        card_box.set_margin_bottom(8)
        self.card_details.add(card_box)

        # File path and metadata
        self.lbl_script_path = Gtk.Label(xalign=0)
        self.lbl_script_path.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        card_box.pack_start(self.lbl_script_path, False, False, 0)

        self.lbl_script_meta = Gtk.Label(xalign=0)
        card_box.pack_start(self.lbl_script_meta, False, False, 0)

        # Badges row (GitHub Badge, Admin Badge)
        self.box_badges = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.lbl_badge_github = Gtk.Label()
        self.lbl_badge_admin = Gtk.Label()
        self.box_badges.pack_start(self.lbl_badge_github, False, False, 0)
        self.box_badges.pack_start(self.lbl_badge_admin, False, False, 0)
        card_box.pack_start(self.box_badges, False, False, 2)

        # Options Row inside Details Card
        opts_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        opts_box.set_margin_top(4)

        self.chk_run_admin = Gtk.CheckButton(label="🔒 Run as Administrator (Root / pkexec)")
        self.chk_run_admin.set_active(False)
        opts_box.pack_start(self.chk_run_admin, False, False, 0)

        self.chk_inject_github = Gtk.CheckButton(label="🐙 Inject GitHub Credentials & AskPass")
        self.chk_inject_github.set_active(True)
        opts_box.pack_start(self.chk_inject_github, False, False, 0)

        card_box.pack_start(opts_box, False, False, 0)

        # Script arguments row
        args_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_args = Gtk.Label(label="Script Arguments:")
        self.entry_args = Gtk.Entry()
        self.entry_args.set_placeholder_text("Optional arguments (e.g. -y -m \"Initial commit\")")
        args_box.pack_start(lbl_args, False, False, 0)
        args_box.pack_start(self.entry_args, True, True, 0)
        card_box.pack_start(args_box, False, False, 2)

        self.card_details.set_no_show_all(True)
        page.pack_start(self.card_details, False, False, 0)

        # Console Header with Actions
        console_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_console = Gtk.Label(label="Execution Output Console")
        lbl_console.get_style_context().add_class("dim-label")
        console_header.pack_start(lbl_console, False, False, 0)

        self.btn_copy_output = Gtk.Button(label="📋 Copy Output")
        self.btn_copy_output.connect("clicked", self.on_copy_output_clicked)
        console_header.pack_end(self.btn_copy_output, False, False, 0)

        self.btn_clear_output = Gtk.Button(label="🗑 Clear")
        self.btn_clear_output.connect("clicked", self.on_clear_output_clicked)
        console_header.pack_end(self.btn_clear_output, False, False, 0)

        page.pack_start(console_header, False, False, 0)

        # Live Terminal Output Console
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_shadow_type(Gtk.ShadowType.IN)

        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_cursor_visible(False)
        self.text_view.set_monospace(True)
        self.text_view.set_wrap_mode(Gtk.WrapMode.CHAR)
        self.text_view.set_left_margin(10)
        self.text_view.set_right_margin(10)
        self.text_view.set_top_margin(8)
        self.text_view.set_bottom_margin(8)

        # Terminal style colors (Dark background, light text)
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            textview text {
                background-color: #1a1b26;
                color: #c0caf5;
                font-family: 'Ubuntu Mono', 'Monospace', monospace;
                font-size: 10.5pt;
            }
        """)
        self.text_view.get_style_context().add_provider(
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.text_buffer = self.text_view.get_buffer()
        # Setup tags
        self.text_buffer.create_tag("green", foreground="#9ece6a", weight=Pango.Weight.BOLD)
        self.text_buffer.create_tag("red", foreground="#f7768e", weight=Pango.Weight.BOLD)
        self.text_buffer.create_tag("cyan", foreground="#7dcfff")
        self.text_buffer.create_tag("yellow", foreground="#e0af68")
        self.text_buffer.create_tag("dim", foreground="#565f89")

        scrolled.add(self.text_view)
        page.pack_start(scrolled, True, True, 0)

        # Bottom Status Bar
        self.status_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.lbl_status = Gtk.Label(label="Status: Ready (Drop a .sh file to begin)", xalign=0)
        self.status_bar.pack_start(self.lbl_status, True, True, 0)

        self.lbl_timer = Gtk.Label(label="", xalign=1)
        self.lbl_timer.get_style_context().add_class("dim-label")
        self.status_bar.pack_end(self.lbl_timer, False, False, 0)

        page.pack_start(self.status_bar, False, False, 0)

        return page

    def _build_settings_page(self):
        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_top(18)
        content.set_margin_bottom(18)
        page.add(content)

        # Title
        lbl_title = Gtk.Label(xalign=0)
        lbl_title.set_markup("<span size='large' weight='bold'>🐙 GitHub &amp; Git Authentication Settings</span>")
        content.pack_start(lbl_title, False, False, 0)

        lbl_desc = Gtk.Label(xalign=0)
        lbl_desc.set_text(
            "Configure your GitHub information once here. Any .sh script running through Mint Script "
            "Runner will automatically receive your credentials and seamlessly authenticate Git operations "
            "(push, pull, clone) without asking you in the terminal!"
        )
        lbl_desc.set_line_wrap(True)
        lbl_desc.get_style_context().add_class("dim-label")
        content.pack_start(lbl_desc, False, False, 0)

        # Settings Form Frame
        form_frame = Gtk.Frame()
        form_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        form_box.set_margin_start(16)
        form_box.set_margin_end(16)
        form_box.set_margin_top(14)
        form_box.set_margin_bottom(14)
        form_frame.add(form_box)
        content.pack_start(form_frame, False, False, 0)

        # 1. GitHub Username
        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lbl_user = Gtk.Label(label="GitHub Username:", xalign=0)
        lbl_user.set_size_request(180, -1)
        self.entry_gh_user = Gtk.Entry()
        self.entry_gh_user.set_text(self.settings.get("github_username", "scratchgamingone"))
        row1.pack_start(lbl_user, False, False, 0)
        row1.pack_start(self.entry_gh_user, True, True, 0)
        form_box.pack_start(row1, False, False, 0)

        # 2. GitHub Email
        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lbl_email = Gtk.Label(label="Git Author Email:", xalign=0)
        lbl_email.set_size_request(180, -1)
        self.entry_gh_email = Gtk.Entry()
        self.entry_gh_email.set_text(self.settings.get("github_email", "scratchgamingone@users.noreply.github.com"))
        row2.pack_start(lbl_email, False, False, 0)
        row2.pack_start(self.entry_gh_email, True, True, 0)
        form_box.pack_start(row2, False, False, 0)

        # 3. Personal Access Token (PAT)
        row3 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lbl_token = Gtk.Label(label="Personal Access Token:", xalign=0)
        lbl_token.set_size_request(180, -1)

        token_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.entry_gh_token = Gtk.Entry()
        self.entry_gh_token.set_visibility(False)
        self.entry_gh_token.set_text(self.settings.get("github_token", ""))
        self.entry_gh_token.set_placeholder_text("ghp_... or github_pat_...")

        self.btn_toggle_token = Gtk.Button(label="👁")
        self.btn_toggle_token.set_tooltip_text("Toggle token visibility")
        self.btn_toggle_token.connect("clicked", self.on_toggle_token_visibility)

        token_box.pack_start(self.entry_gh_token, True, True, 0)
        token_box.pack_start(self.btn_toggle_token, False, False, 0)

        row3.pack_start(lbl_token, False, False, 0)
        row3.pack_start(token_box, True, True, 0)
        form_box.pack_start(row3, False, False, 0)

        # Helper link for generating token
        token_help_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_spacer = Gtk.Label(label="")
        lbl_spacer.set_size_request(180, -1)
        btn_open_tokens = Gtk.LinkButton(
            uri="https://github.com/settings/tokens",
            label="🔑 Generate Token (Classic with 'repo' scope OR Fine-grained with 'Contents: Read and write')"
        )
        token_help_box.pack_start(lbl_spacer, False, False, 0)
        token_help_box.pack_start(btn_open_tokens, False, False, 0)
        form_box.pack_start(token_help_box, False, False, 0)

        # 4. Default Git Remote Repository URL
        row4 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lbl_remote = Gtk.Label(label="Default Remote URL:", xalign=0)
        lbl_remote.set_size_request(180, -1)
        self.entry_gh_remote = Gtk.Entry()
        self.entry_gh_remote.set_text(self.settings.get("default_remote", ""))
        row4.pack_start(lbl_remote, False, False, 0)
        row4.pack_start(self.entry_gh_remote, True, True, 0)
        form_box.pack_start(row4, False, False, 0)

        # Actions Row in Settings
        actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        actions_box.set_margin_top(8)

        btn_save = Gtk.Button(label="💾 Save Settings")
        btn_save.get_style_context().add_class("suggested-action")
        btn_save.connect("clicked", self.on_save_settings_clicked)
        actions_box.pack_start(btn_save, False, False, 0)

        btn_test = Gtk.Button(label="🔌 Test GitHub Connection")
        btn_test.connect("clicked", self.on_test_connection_clicked)
        actions_box.pack_start(btn_test, False, False, 0)

        self.lbl_test_result = Gtk.Label(xalign=0)
        actions_box.pack_start(self.lbl_test_result, True, True, 0)

        content.pack_start(actions_box, False, False, 0)

        return page

    def _setup_drag_and_drop(self):
        """Enables drag-and-drop targeting for .sh and text files."""
        targets = [
            Gtk.TargetEntry.new("text/uri-list", 0, 0),
            Gtk.TargetEntry.new("STRING", 0, 1),
            Gtk.TargetEntry.new("text/plain", 0, 2),
        ]
        self.drop_event_box.drag_dest_set(
            Gtk.DestDefaults.ALL,
            targets,
            Gdk.DragAction.COPY | Gdk.DragAction.MOVE,
        )
        self.drop_event_box.connect("drag-data-received", self.on_drag_data_received)

    def on_drag_data_received(self, widget, drag_context, x, y, data, info, time_stamp):
        uris = data.get_uris()
        if uris:
            first_uri = uris[0]
            parsed = urllib.parse.urlparse(first_uri)
            file_path = urllib.parse.unquote(parsed.path)
            self.load_script(file_path)
            drag_context.finish(True, False, time_stamp)
        else:
            drag_context.finish(False, False, time_stamp)

    def on_browse_file_clicked(self, button):
        dialog = Gtk.FileChooserDialog(
            title="Choose a Shell Script to Run",
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT,
        )

        # Filters
        filter_sh = Gtk.FilterList()
        filter_sh = Gtk.FileFilter()
        filter_sh.set_name("Shell Scripts (*.sh, *.bash)")
        filter_sh.add_pattern("*.sh")
        filter_sh.add_pattern("*.bash")
        dialog.add_filter(filter_sh)

        filter_all = Gtk.FileFilter()
        filter_all.set_name("All Files")
        filter_all.add_pattern("*")
        dialog.add_filter(filter_all)

        response = dialog.run()
        if response == Gtk.ResponseType.ACCEPT:
            filename = dialog.get_filename()
            dialog.destroy()
            self.load_script(filename)
        else:
            dialog.destroy()

    def load_script(self, file_path):
        """Loads and inspects the dropped or selected script."""
        info = ScriptInspector.inspect(file_path)
        if not info["is_valid"]:
            self.show_error_dialog("Invalid Script File", info.get("error", "Unknown error."))
            return

        self.current_script_info = info

        # Make executable if needed
        if not info["is_executable"]:
            ScriptInspector.make_executable(file_path)
            info["is_executable"] = True

        # Update Drop Area UI to reflect loaded script
        self.lbl_drop_title.set_markup(
            f"<span size='large' weight='bold' color='#9ece6a'>✓ Loaded: {info['file_name']}</span>"
        )
        self.lbl_drop_sub.set_text(info["file_path"])

        # Update Details Card
        self.card_details.show_all()
        self.lbl_script_path.set_markup(f"<b>Path:</b> <tt>{info['file_path']}</tt>")
        self.lbl_script_meta.set_markup(
            f"<b>Size:</b> {info['file_size_human']}  |  <b>Lines:</b> {info['line_count']}  |  "
            f"<b>Executable:</b> <span color='#9ece6a'>Yes</span>"
        )

        # Auto-configure admin suggestion if script uses sudo/apt
        if info["admin_suggested"]:
            self.chk_run_admin.set_active(True)
            self.lbl_badge_admin.set_markup(
                "<span background='#f7768e' color='#ffffff' weight='bold'> 🛡️ Admin Recommended </span>"
            )
        else:
            self.lbl_badge_admin.set_markup("")

        # GitHub Badge & Token Check
        if info["uses_github"]:
            self.chk_inject_github.set_active(True)
            has_token = self.settings.has_github_token()
            if has_token:
                self.lbl_badge_github.set_markup(
                    "<span background='#bb9af7' color='#1a1b26' weight='bold'> 🐙 GitHub Credentials Ready </span>"
                )
            else:
                self.lbl_badge_github.set_markup(
                    "<span background='#e0af68' color='#1a1b26' weight='bold'> ⚠️ GitHub Token Needed (Settings) </span>"
                )
        else:
            self.lbl_badge_github.set_markup("")

        # Enable Run Button
        self.btn_run_header.set_sensitive(True)
        self.lbl_status.set_text(f"Ready to run '{info['file_name']}'")

        # Automatically show execution confirmation modal
        self.prompt_execution_confirmation(info)

    def prompt_execution_confirmation(self, info):
        """Displays permission & administrative confirmation modal before execution."""
        dialog = Gtk.Dialog(
            title="Run Script Confirmation",
            parent=self,
            flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
        )
        dialog.set_default_size(500, 280)

        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_start(18)
        content.set_margin_end(18)
        content.set_margin_top(16)
        content.set_margin_bottom(12)

        # Dialog Title & Description
        lbl_head = Gtk.Label(xalign=0)
        lbl_head.set_markup(
            f"<span size='large' weight='bold'>Execute '{info['file_name']}'?</span>"
        )
        content.pack_start(lbl_head, False, False, 0)

        lbl_desc = Gtk.Label(xalign=0)
        lbl_desc.set_markup(
            f"Select execution permissions for this shell script:\n"
            f"<tt>{info['file_path']}</tt>"
        )
        lbl_desc.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        lbl_desc.get_style_context().add_class("dim-label")
        content.pack_start(lbl_desc, False, False, 0)

        # Warning / Info Cards
        if info["admin_suggested"]:
            msg_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            lbl_adm_warn = Gtk.Label(xalign=0)
            lbl_adm_warn.set_markup(
                "<span color='#f7768e'><b>Notice:</b> This script contains system commands (sudo, apt, systemctl). "
                "Running as Administrator is recommended.</span>"
            )
            lbl_adm_warn.set_line_wrap(True)
            msg_box.pack_start(lbl_adm_warn, True, True, 0)
            content.pack_start(msg_box, False, False, 0)

        if info["uses_github"] and not self.settings.has_github_token():
            gh_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            lbl_gh_warn = Gtk.Label(xalign=0)
            lbl_gh_warn.set_markup(
                "<span color='#e0af68'><b>Notice:</b> Script contains Git/GitHub operations, but your GitHub Token "
                "is not configured in Settings.</span>"
            )
            lbl_gh_warn.set_line_wrap(True)
            gh_box.pack_start(lbl_gh_warn, True, True, 0)
            content.pack_start(gh_box, False, False, 0)

        if info["uses_github"] and not info["admin_suggested"]:
            gh_info_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            lbl_gh_info = Gtk.Label(xalign=0)
            lbl_gh_info.set_markup(
                "<span color='#7dcfff'>💡 <b>Tip:</b> Git sync scripts should be run as Standard User.</span>"
            )
            gh_info_box.pack_start(lbl_gh_info, True, True, 0)
            content.pack_start(gh_info_box, False, False, 0)

        # Action Buttons
        btn_cancel = dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        btn_user = dialog.add_button("👤 Run as Standard User", 100)
        btn_admin = dialog.add_button("🔒 Run as Administrator (Root)", 200)

        if info["admin_suggested"]:
            btn_admin.get_style_context().add_class("suggested-action")
        else:
            btn_user.get_style_context().add_class("suggested-action")

        if info["uses_github"] and not self.settings.has_github_token():
            btn_settings = dialog.add_button("⚙️ Open Settings", 300)

        dialog.show_all()
        response = dialog.run()
        dialog.destroy()

        if response == 200:
            # Run as Admin
            self.chk_run_admin.set_active(True)
            self.start_execution(as_admin=True)
        elif response == 100:
            # Run as Normal User
            self.chk_run_admin.set_active(False)
            self.start_execution(as_admin=False)
        elif response == 300:
            # Switch to settings tab
            self.stack.set_visible_child_name("settings")

    def on_run_clicked(self, button):
        if not self.current_script_info:
            return
        as_admin = self.chk_run_admin.get_active()
        self.start_execution(as_admin=as_admin)

    def start_execution(self, as_admin=False):
        """Starts the script runner engine."""
        if not self.current_script_info:
            return

        if self.runner.is_running:
            self.show_error_dialog("Already Running", "A script is currently running. Please stop it first.")
            return

        script_path = self.current_script_info["file_path"]
        args_text = self.entry_args.get_text().strip()
        args_list = args_text.split() if args_text else []
        inject_gh = self.chk_inject_github.get_active()

        # Clear output
        self.text_buffer.set_text("")
        self.start_time = time.time()

        # UI updates
        self.btn_run_header.set_sensitive(False)
        self.btn_stop_header.set_sensitive(True)

        mode_desc = "Administrator (Root / pkexec)" if as_admin else "Standard User"
        self._append_console(f"🚀 Launching '{self.current_script_info['file_name']}' as {mode_desc}...\n", "cyan")
        self._append_console(f"📁 Working Directory: {self.current_script_info['dir_path']}\n", "dim")
        if inject_gh:
            gh_user = self.settings.get("github_username")
            self._append_console(f"🐙 Injecting GitHub Credentials for @{gh_user} (AskPass Active)\n", "yellow")
        self._append_console("----------------------------------------------------------------\n", "dim")

        success, msg = self.runner.execute(
            script_path=script_path,
            args_list=args_list,
            as_admin=as_admin,
            inject_github=inject_gh,
            working_dir=self.current_script_info["dir_path"],
            on_output=self._append_console,
            on_status=self._update_status,
            on_finished=self._on_execution_finished,
        )

        if not success:
            self._append_console(f"❌ Failed to launch: {msg}\n", "red")
            self.btn_run_header.set_sensitive(True)
            self.btn_stop_header.set_sensitive(False)

    def on_stop_clicked(self, button):
        if self.runner.is_running:
            self._append_console("\n⚠️ Stopping process...\n", "yellow")
            self.runner.stop()

    def _append_console(self, text, tag=None):
        end_iter = self.text_buffer.get_end_iter()
        if tag:
            self.text_buffer.insert_with_tags_by_name(end_iter, text, tag)
        else:
            self.text_buffer.insert(end_iter, text)

        # Auto-scroll to bottom
        mark = self.text_buffer.create_mark(None, self.text_buffer.get_end_iter(), False)
        self.text_view.scroll_to_mark(mark, 0.05, True, 0.0, 1.0)

    def _update_status(self, text):
        self.lbl_status.set_text(f"Status: {text}")

    def _on_execution_finished(self, return_code):
        elapsed = time.time() - (self.start_time or time.time())
        elapsed_str = f"{elapsed:.1f}s"

        self.btn_run_header.set_sensitive(True)
        self.btn_stop_header.set_sensitive(False)

        self._append_console("----------------------------------------------------------------\n", "dim")
        if return_code == 0:
            self._append_console(f"✅ Finished successfully! (Exit Code: 0, Elapsed: {elapsed_str})\n", "green")
            self.lbl_status.set_markup(
                f"<span color='#9ece6a'><b>Status: Completed Successfully (Exit: 0)</b> in {elapsed_str}</span>"
            )
        elif return_code == 126 or return_code == 127:
            self._append_console(f"❌ Authentication / Command Not Found (Exit Code: {return_code})\n", "red")
            self.lbl_status.set_markup(f"<span color='#f7768e'><b>Status: Admin Authentication Cancelled / Failed</b></span>")
        else:
            self._append_console(f"❌ Script terminated with exit code: {return_code} (Elapsed: {elapsed_str})\n", "red")
            self.lbl_status.set_markup(
                f"<span color='#f7768e'><b>Status: Failed (Exit Code: {return_code})</b> in {elapsed_str}</span>"
            )

    def on_toggle_token_visibility(self, button):
        is_visible = self.entry_gh_token.get_visibility()
        self.entry_gh_token.set_visibility(not is_visible)
        button.set_label("🔒" if not is_visible else "👁")

    def on_save_settings_clicked(self, button):
        self.settings.set("github_username", self.entry_gh_user.get_text().strip())
        self.settings.set("github_email", self.entry_gh_email.get_text().strip())
        self.settings.set("github_token", self.entry_gh_token.get_text().strip())
        self.settings.set("default_remote", self.entry_gh_remote.get_text().strip())

        if self.settings.save():
            self.lbl_test_result.set_markup("<span color='#9ece6a'>✓ Settings saved securely!</span>")
            # Refresh badges if script is loaded
            if self.current_script_info:
                self.load_script(self.current_script_info["file_path"])
        else:
            self.lbl_test_result.set_markup("<span color='#f7768e'>❌ Failed to save settings.</span>")

    def on_test_connection_clicked(self, button):
        # Save temporary entries first
        self.settings.set("github_username", self.entry_gh_user.get_text().strip())
        self.settings.set("github_token", self.entry_gh_token.get_text().strip())

        self.lbl_test_result.set_markup("<span color='#7dcfff'>Connecting to GitHub API...</span>")

        def check_async():
            valid, msg = self.settings.test_github_token()
            def update_ui():
                if valid:
                    self.lbl_test_result.set_markup(f"<span color='#9ece6a'>✓ {msg}</span>")
                else:
                    self.lbl_test_result.set_markup(f"<span color='#f7768e'>❌ {msg}</span>")
            GLib.idle_add(update_ui)

        import threading
        threading.Thread(target=check_async, daemon=True).start()

    def on_copy_output_clicked(self, button):
        start = self.text_buffer.get_start_iter()
        end = self.text_buffer.get_end_iter()
        text = self.text_buffer.get_text(start, end, True)
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(text, -1)
        self.lbl_status.set_text("Status: Output copied to clipboard!")

    def on_clear_output_clicked(self, button):
        self.text_buffer.set_text("")
        self.lbl_status.set_text("Status: Output cleared")

    def show_error_dialog(self, title, message):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=title,
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()
