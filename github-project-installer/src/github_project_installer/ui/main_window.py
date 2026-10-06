"""
Main Application Window for GitHub Project Installer.
Coordinates repository inspection, file navigation, README rendering,
syntax highlighting, and source code installation.
"""

import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Optional

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Pango, GdkPixbuf

from github_project_installer import __version__, __app_name__
from github_project_installer.core.config import config_manager, DEFAULT_INSTALL_DIR, CACHE_DIR
from github_project_installer.core.github_api import parse_github_url, GitHubRepoInfo
from github_project_installer.core.git_inspector import inspect_repository, RepoSnapshot, format_bytes
from github_project_installer.core.extractor import install_repository_to_documents, InstallResult
from github_project_installer.ui.tree_view import RepoTreeWidget
from github_project_installer.ui.readme_view import ReadmeWidget
from github_project_installer.ui.code_viewer import CodeViewerWidget
from github_project_installer.ui.deps_view import DepsViewWidget
from github_project_installer.ui.terminal_view import TerminalViewWidget


class MainWindow(Gtk.ApplicationWindow):
    """Main window of GitHub Project Installer."""

    def __init__(self, app, initial_url: str = ""):
        super().__init__(application=app, title=__app_name__)
        self.set_default_size(1200, 800)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.get_style_context().add_class("app-window")

        self.current_snapshot: Optional[RepoSnapshot] = None
        self.last_install_path: Optional[str] = None
        self.is_inspecting: bool = False
        self.is_installing: bool = False

        # Set Window Icon
        icon_path = Path(__file__).parent.parent / "assets" / "github-project-installer.png"
        if icon_path.is_file():
            self.set_icon_from_file(str(icon_path))

        # 1. Header Bar
        self.header_bar = Gtk.HeaderBar()
        self.header_bar.set_show_close_button(True)
        self.header_bar.set_title(__app_name__)
        self.header_bar.set_subtitle("Preview code, inspect README, and install to Documents")
        self.set_titlebar(self.header_bar)

        # Settings Button
        btn_settings = Gtk.Button()
        btn_settings.set_tooltip_text("Settings & Preferences")
        btn_settings.set_image(Gtk.Image.new_from_icon_name("emblem-system-symbolic", Gtk.IconSize.BUTTON))
        btn_settings.connect("clicked", self._open_settings_dialog)
        self.header_bar.pack_end(btn_settings)

        # About Button
        btn_about = Gtk.Button()
        btn_about.set_tooltip_text("About")
        btn_about.set_image(Gtk.Image.new_from_icon_name("help-about-symbolic", Gtk.IconSize.BUTTON))
        btn_about.connect("clicked", self._open_about_dialog)
        self.header_bar.pack_end(btn_about)

        # 2. Main Layout Vertical Box
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_vbox.set_margin_top(8)
        main_vbox.set_margin_bottom(8)
        main_vbox.set_margin_start(10)
        main_vbox.set_margin_end(10)
        self.add(main_vbox)

        # 3. Search / URL Input Card
        input_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        input_card.get_style_context().add_class("search-card")

        row_input = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        # GitHub Icon
        icon_gh = Gtk.Image.new_from_icon_name("git", Gtk.IconSize.LARGE_TOOLBAR)
        row_input.pack_start(icon_gh, False, False, 0)

        # URL Text Entry
        self.entry_url = Gtk.Entry()
        self.entry_url.get_style_context().add_class("url-entry")
        self.entry_url.set_placeholder_text("Paste any GitHub repository link (e.g. https://github.com/owner/project or owner/project)...")
        self.entry_url.connect("activate", lambda e: self._on_inspect_clicked(None))
        row_input.pack_start(self.entry_url, True, True, 0)

        # Paste Button
        btn_paste = Gtk.Button(label="📋 Paste")
        btn_paste.get_style_context().add_class("btn-action")
        btn_paste.set_tooltip_text("Paste link from clipboard")
        btn_paste.connect("clicked", self._on_paste_clicked)
        row_input.pack_start(btn_paste, False, False, 0)

        # Inspect Button
        self.btn_inspect = Gtk.Button(label="🔍 Inspect Repository")
        self.btn_inspect.get_style_context().add_class("btn-install")
        self.btn_inspect.connect("clicked", self._on_inspect_clicked)
        row_input.pack_start(self.btn_inspect, False, False, 0)

        input_card.pack_start(row_input, False, False, 0)

        # Status Bar / Progress Row
        row_status = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.spinner = Gtk.Spinner()
        row_status.pack_start(self.spinner, False, False, 0)

        self.lbl_progress = Gtk.Label(label="Ready. Paste a GitHub repository link to inspect and install.")
        self.lbl_progress.set_halign(Gtk.Align.START)
        row_status.pack_start(self.lbl_progress, True, True, 0)

        input_card.pack_start(row_status, False, False, 0)
        main_vbox.pack_start(input_card, False, False, 0)

        # 4. Repository Header Info Card (Hidden until repo inspected)
        self.repo_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.repo_card.get_style_context().add_class("repo-card")
        self.repo_card.set_no_show_all(True)

        # Title & Badges Row
        row_title = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.lbl_repo_title = Gtk.Label(label="")
        self.lbl_repo_title.get_style_context().add_class("repo-title")
        self.lbl_repo_title.set_halign(Gtk.Align.START)
        row_title.pack_start(self.lbl_repo_title, False, False, 0)

        # Badges box
        self.badges_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row_title.pack_start(self.badges_box, False, False, 0)

        self.repo_card.pack_start(row_title, False, False, 0)

        # Description Label
        self.lbl_repo_desc = Gtk.Label(label="")
        self.lbl_repo_desc.get_style_context().add_class("repo-desc")
        self.lbl_repo_desc.set_halign(Gtk.Align.START)
        self.lbl_repo_desc.set_line_wrap(True)
        self.repo_card.pack_start(self.lbl_repo_desc, False, False, 0)

        main_vbox.pack_start(self.repo_card, False, False, 0)

        # 5. Paned Content View (Left: TreeView, Right: Notebook Tabs)
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.paned.set_position(320)

        # Left: File and Folder Explorer Tree
        self.tree_widget = RepoTreeWidget(on_file_selected=self._on_file_selected)
        self.paned.pack1(self.tree_widget, False, False)

        # Right: Notebook with 4 Tabs
        self.notebook = Gtk.Notebook()
        self.notebook.set_scrollable(True)

        # Tab 0: README Viewer (FIRST, as requested)
        self.readme_widget = ReadmeWidget()
        tab_label_readme = Gtk.Label(label="📖 README & Overview")
        self.notebook.append_page(self.readme_widget, tab_label_readme)

        # Tab 1: Code Viewer
        self.code_widget = CodeViewerWidget()
        tab_label_code = Gtk.Label(label="💻 Code Viewer")
        self.notebook.append_page(self.code_widget, tab_label_code)

        # Tab 2: Dependencies & Setup
        self.deps_widget = DepsViewWidget(on_run_command=self._run_terminal_command)
        tab_label_deps = Gtk.Label(label="📦 Dependencies & Setup")
        self.notebook.append_page(self.deps_widget, tab_label_deps)

        # Tab 3: Terminal Console & Logs
        self.terminal_widget = TerminalViewWidget()
        tab_label_term = Gtk.Label(label="🖥️ Installation Console")
        self.notebook.append_page(self.terminal_widget, tab_label_term)

        self.paned.pack2(self.notebook, True, False)
        main_vbox.pack_start(self.paned, True, True, 0)

        # 6. Bottom Installation & Action Bar
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        bottom_box.get_style_context().add_class("search-card")

        row_install = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        # Destination Label
        self.lbl_dest = Gtk.Label()
        self._update_destination_label()
        self.lbl_dest.set_halign(Gtk.Align.START)
        self.lbl_dest.set_ellipsize(Pango.EllipsizeMode.START)
        row_install.pack_start(self.lbl_dest, True, True, 0)

        # Change Folder Button
        btn_change_dest = Gtk.Button(label="📁 Change Destination")
        btn_change_dest.get_style_context().add_class("btn-action")
        btn_change_dest.connect("clicked", self._on_change_destination)
        row_install.pack_start(btn_change_dest, False, False, 0)

        # Auto Extract Checkbox
        self.chk_auto_extract = Gtk.CheckButton(label="Auto-Extract Archives")
        self.chk_auto_extract.set_active(config_manager.auto_extract_archives)
        self.chk_auto_extract.connect("toggled", lambda c: setattr(config_manager, "auto_extract_archives", c.get_active()))
        row_install.pack_start(self.chk_auto_extract, False, False, 0)

        # Big Install Button
        self.btn_install = Gtk.Button(label="📥 Install Source Code & Auto-Extract")
        self.btn_install.get_style_context().add_class("btn-install")
        self.btn_install.set_sensitive(False)
        self.btn_install.connect("clicked", self._on_install_clicked)
        row_install.pack_end(self.btn_install, False, False, 0)

        bottom_box.pack_start(row_install, False, False, 0)

        # Row with Quick Action Buttons after installation (Hidden initially)
        self.row_post_install = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.row_post_install.set_no_show_all(True)

        self.lbl_installed_status = Gtk.Label(label="✅ Ready!")
        self.lbl_installed_status.set_halign(Gtk.Align.START)
        self.row_post_install.pack_start(self.lbl_installed_status, True, True, 0)

        btn_open_folder = Gtk.Button(label="📂 Open in File Manager (Nemo)")
        btn_open_folder.get_style_context().add_class("btn-action")
        btn_open_folder.connect("clicked", lambda b: self._open_installed_folder())
        self.row_post_install.pack_start(btn_open_folder, False, False, 0)

        btn_open_term = Gtk.Button(label="💻 Open Terminal Here")
        btn_open_term.get_style_context().add_class("btn-action")
        btn_open_term.connect("clicked", lambda b: self._open_installed_terminal())
        self.row_post_install.pack_start(btn_open_term, False, False, 0)

        self.btn_run_script = Gtk.Button(label="⚡ Run Install Script")
        self.btn_run_script.get_style_context().add_class("btn-action")
        self.btn_run_script.connect("clicked", lambda b: self._run_detected_script())
        self.row_post_install.pack_start(self.btn_run_script, False, False, 0)

        bottom_box.pack_start(self.row_post_install, False, False, 0)

        main_vbox.pack_start(bottom_box, False, False, 0)

        # Handle initial URL if given
        if initial_url:
            self.entry_url.set_text(initial_url)
            GLib.idle_add(lambda: self._on_inspect_clicked(None))

    def _update_destination_label(self):
        repo_sub = f"/{self.current_snapshot.info.repo}" if self.current_snapshot else "/<repo_name>"
        self.lbl_dest.set_text(f"Install Path: {config_manager.install_dir}{repo_sub}")

    def _on_paste_clicked(self, btn):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        text = clipboard.wait_for_text()
        if text:
            self.entry_url.set_text(text.strip())

    def _on_inspect_clicked(self, btn):
        if self.is_inspecting:
            return

        url_text = self.entry_url.get_text().strip()
        if not url_text:
            self._show_info_dialog("No URL Entered", "Please paste or enter a GitHub repository URL first.")
            return

        info = parse_github_url(url_text)
        if not info:
            self._show_error_dialog(
                "Invalid GitHub URL",
                f"Could not parse '{url_text}'. Please provide a valid repository URL like:\n"
                "• https://github.com/owner/repository\n"
                "• owner/repository"
            )
            return

        # Start Inspection
        self.is_inspecting = True
        self.spinner.start()
        self.btn_inspect.set_sensitive(False)
        self.btn_install.set_sensitive(False)
        self.row_post_install.hide()

        config_manager.add_recent_repo(url_text)

        def progress_cb(msg: str, frac: float):
            def _update():
                self.lbl_progress.set_text(msg)
                self.terminal_widget.log(f"ℹ {msg}")
                return False
            GLib.idle_add(_update)

        def worker():
            try:
                snapshot = inspect_repository(
                    info,
                    progress_cb=progress_cb,
                    token=config_manager.github_token,
                )

                def on_success():
                    self.current_snapshot = snapshot
                    self._update_destination_label()
                    self._display_snapshot(snapshot)
                    self.spinner.stop()
                    self.is_inspecting = False
                    self.btn_inspect.set_sensitive(True)
                    self.btn_install.set_sensitive(True)
                    self.lbl_progress.set_text(f"✓ Successfully inspected '{info.owner}/{info.repo}'. Ready to install.")
                    return False

                GLib.idle_add(on_success)

            except Exception as e:
                def on_failure():
                    self.spinner.stop()
                    self.is_inspecting = False
                    self.btn_inspect.set_sensitive(True)
                    self.lbl_progress.set_text(f"✗ Failed to inspect repository: {str(e)}")
                    self.terminal_widget.log(f"Error inspecting repo: {e}", "error")
                    self._show_error_dialog("Inspection Error", str(e))
                    return False

                GLib.idle_add(on_failure)

        threading.Thread(target=worker, daemon=True).start()

    def _display_snapshot(self, snapshot: RepoSnapshot):
        """Updates all views with the newly inspected repository snapshot."""
        # 1. Update Repo Info Card
        self.lbl_repo_title.set_text(f"{snapshot.info.owner} / {snapshot.info.repo}")
        self.lbl_repo_desc.set_text(snapshot.info.description or "No description provided.")

        # Clear old badges
        for child in self.badges_box.get_children():
            self.badges_box.remove(child)

        def make_badge(text: str, css_class: str):
            b = Gtk.Label(label=text)
            b.get_style_context().add_class("badge-pill")
            b.get_style_context().add_class(css_class)
            self.badges_box.pack_start(b, False, False, 0)

        if snapshot.info.stars:
            make_badge(f"⭐ {snapshot.info.stars:,}", "badge-star")
        if snapshot.info.forks:
            make_badge(f"🍴 {snapshot.info.forks:,}", "badge-fork")
        if snapshot.info.language:
            make_badge(snapshot.info.language, "badge-lang")
        if snapshot.info.license_name and snapshot.info.license_name != "None":
            make_badge(f"⚖ {snapshot.info.license_name}", "badge-license")
        make_badge(f"🌿 {snapshot.info.default_branch}", "badge-branch")
        make_badge(f"📦 {snapshot.formatted_size} ({snapshot.file_count} files)", "badge-branch")

        self.repo_card.show_all()

        # 2. Populate Left TreeView
        if snapshot.root_node:
            self.tree_widget.populate(snapshot.root_node)

        # 3. Populate README (Tab 0 - Displayed First)
        readme_title = Path(snapshot.readme_path).name if snapshot.readme_path else "README.md"
        self.readme_widget.set_content(snapshot.readme_content, readme_title)
        self.notebook.set_current_page(0)

        # 4. Populate Dependencies Tab (Tab 2)
        self.deps_widget.set_detected_info(snapshot.detected, snapshot.info.repo)

    def _on_file_selected(self, abs_path: str, rel_path: str):
        """When a file is clicked in the left tree, open it in the Code Viewer."""
        self.code_widget.load_file(abs_path, rel_path)
        # Switch to Code Viewer tab
        self.notebook.set_current_page(1)

    def _on_change_destination(self, btn):
        dialog = Gtk.FileChooserDialog(
            title="Select Base Destination Folder",
            parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_APPLY, Gtk.ResponseType.APPLY,
        )
        dialog.set_current_folder(config_manager.install_dir)
        response = dialog.run()
        if response == Gtk.ResponseType.APPLY:
            folder = dialog.get_filename()
            if folder:
                config_manager.install_dir = folder
                self._update_destination_label()
        dialog.destroy()

    def _on_install_clicked(self, btn):
        if not self.current_snapshot or self.is_installing:
            return

        target_dir = Path(config_manager.install_dir) / self.current_snapshot.info.repo

        # Check if folder exists
        overwrite = True
        if target_dir.exists():
            dlg = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.NONE,
                text=f"Project folder already exists:\n{target_dir}",
            )
            dlg.format_secondary_text("Would you like to replace the existing directory, or create a unique numbered folder?")
            dlg.add_button("Overwrite Existing", Gtk.ResponseType.YES)
            dlg.add_button("Create New Folder", Gtk.ResponseType.NO)
            dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
            resp = dlg.run()
            dlg.destroy()

            if resp == Gtk.ResponseType.CANCEL:
                return
            elif resp == Gtk.ResponseType.NO:
                overwrite = False

        self.is_installing = True
        self.btn_install.set_sensitive(False)
        self.spinner.start()
        self.notebook.set_current_page(3)  # Switch to Terminal tab

        self.terminal_widget.log(f"📥 Starting installation of {self.current_snapshot.info.repo}...", "info")

        def progress_cb(msg: str, frac: float):
            def _update():
                self.lbl_progress.set_text(msg)
                self.terminal_widget.log(f"● {msg}")
                return False
            GLib.idle_add(_update)

        def worker():
            try:
                res = install_repository_to_documents(
                    self.current_snapshot,
                    base_install_dir=config_manager.install_dir,
                    overwrite=overwrite,
                    auto_extract=config_manager.auto_extract_archives,
                    keep_git=config_manager.keep_git_history,
                    progress_cb=progress_cb,
                )

                def on_done():
                    self.spinner.stop()
                    self.is_installing = False
                    self.btn_install.set_sensitive(True)

                    if res.success:
                        self.last_install_path = res.target_path
                        self.lbl_progress.set_text(f"✓ Installed to {res.target_path}")
                        self.terminal_widget.log(f"✓ {res.message}", "success")

                        # Show quick action buttons
                        self.lbl_installed_status.set_text(f"Installed at: {Path(res.target_path).name}")
                        if res.executable_scripts:
                            self.btn_run_script.set_visible(True)
                            self.btn_run_script.set_label(f"⚡ Run {res.executable_scripts[0]}")
                        else:
                            self.btn_run_script.set_visible(False)

                        self.row_post_install.show_all()
                    else:
                        self.lbl_progress.set_text(f"✗ Installation failed: {res.message}")
                        self.terminal_widget.log(f"Installation failed: {res.message}", "error")
                        self._show_error_dialog("Installation Error", res.message)

                    return False

                GLib.idle_add(on_done)

            except Exception as e:
                def on_error():
                    self.spinner.stop()
                    self.is_installing = False
                    self.btn_install.set_sensitive(True)
                    self.terminal_widget.log(f"Error during installation: {e}", "error")
                    self._show_error_dialog("Installation Error", str(e))
                    return False
                GLib.idle_add(on_error)

        threading.Thread(target=worker, daemon=True).start()

    def _open_installed_folder(self):
        if self.last_install_path and os.path.exists(self.last_install_path):
            try:
                subprocess.Popen(["nemo", self.last_install_path])
            except Exception:
                subprocess.Popen(["xdg-open", self.last_install_path])

    def _open_installed_terminal(self):
        if self.last_install_path and os.path.exists(self.last_install_path):
            for term in ["x-terminal-emulator", "gnome-terminal", "mate-terminal", "xfce4-terminal", "xterm"]:
                if shutil.which(term):
                    try:
                        subprocess.Popen([term], cwd=self.last_install_path)
                        return
                    except Exception:
                        pass

    def _run_detected_script(self):
        if not self.last_install_path or not self.current_snapshot:
            return

        scripts = self.current_snapshot.detected.get("install_commands", [])
        if scripts:
            cmd = scripts[0]
            self._run_terminal_command(cmd)

    def _run_terminal_command(self, cmd_str: str):
        """Runs a command inside the terminal tab."""
        cwd = self.last_install_path or (self.current_snapshot.local_path if self.current_snapshot else os.path.expanduser("~"))
        self.notebook.set_current_page(3)
        self.terminal_widget.run_command(cmd_str.split(), cwd=cwd)

    def _open_settings_dialog(self, btn):
        dlg = Gtk.Dialog(title="Settings & Preferences", parent=self, flags=0)
        dlg.add_buttons(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
        dlg.set_default_size(500, 300)

        box = dlg.get_content_area()
        box.set_spacing(12)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)

        # Default Install Path
        lbl_inst = Gtk.Label(label="<b>Default Projects Installation Folder:</b>")
        lbl_inst.set_use_markup(True)
        lbl_inst.set_halign(Gtk.Align.START)
        box.pack_start(lbl_inst, False, False, 0)

        row_dest = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        entry_dest = Gtk.Entry(text=config_manager.install_dir)
        row_dest.pack_start(entry_dest, True, True, 0)

        btn_browse = Gtk.Button(label="Browse...")
        btn_browse.connect("clicked", lambda b: self._browse_dir_into_entry(entry_dest))
        row_dest.pack_start(btn_browse, False, False, 0)
        box.pack_start(row_dest, False, False, 0)

        # GitHub Token
        lbl_tok = Gtk.Label(label="<b>GitHub Personal Access Token (Optional):</b>")
        lbl_tok.set_use_markup(True)
        lbl_tok.set_halign(Gtk.Align.START)
        box.pack_start(lbl_tok, False, False, 0)

        entry_tok = Gtk.Entry(text=config_manager.github_token)
        entry_tok.set_visibility(False)
        entry_tok.set_placeholder_text("ghp_... (for private repositories or higher rate limits)")
        box.pack_start(entry_tok, False, False, 0)

        # Cache management
        btn_clear_cache = Gtk.Button(label="🗑 Clear Repository Cache (~/.cache)")
        btn_clear_cache.connect("clicked", lambda b: self._clear_cache())
        box.pack_start(btn_clear_cache, False, False, 0)

        box.show_all()
        dlg.run()

        # Save settings
        config_manager.install_dir = entry_dest.get_text().strip() or str(DEFAULT_INSTALL_DIR)
        config_manager.github_token = entry_tok.get_text().strip()
        self._update_destination_label()
        dlg.destroy()

    def _browse_dir_into_entry(self, entry):
        chooser = Gtk.FileChooserDialog(
            title="Choose Directory",
            parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        chooser.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        if chooser.run() == Gtk.ResponseType.OK:
            f = chooser.get_filename()
            if f:
                entry.set_text(f)
        chooser.destroy()

    def _clear_cache(self):
        try:
            shutil.rmtree(CACHE_DIR / "repos", ignore_errors=True)
            shutil.rmtree(CACHE_DIR / "zips", ignore_errors=True)
            (CACHE_DIR / "repos").mkdir(parents=True, exist_ok=True)
            (CACHE_DIR / "zips").mkdir(parents=True, exist_ok=True)
            self._show_info_dialog("Cache Cleared", "Repository cache has been successfully emptied.")
        except Exception as e:
            self._show_error_dialog("Error", str(e))

    def _open_about_dialog(self, btn):
        dlg = Gtk.AboutDialog(parent=self)
        dlg.set_program_name(__app_name__)
        dlg.set_version(__version__)
        dlg.set_comments(
            "Native GTK3 desktop utility for Linux Mint.\n"
            "Inspect any GitHub repository, preview directory trees and source codes,\n"
            "read markdown documentation, and 1-click install & auto-extract into Documents."
        )
        dlg.set_website("https://github.com")
        dlg.set_authors(["Sam", "Linux Mint Omni Projects"])
        icon_path = Path(__file__).parent.parent / "assets" / "github-project-installer.png"
        if icon_path.is_file():
            dlg.set_logo(GdkPixbuf.Pixbuf.new_from_file(str(icon_path)))
        dlg.run()
        dlg.destroy()

    def _show_error_dialog(self, title: str, message: str):
        dlg = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=title,
        )
        dlg.format_secondary_text(message)
        dlg.run()
        dlg.destroy()

    def _show_info_dialog(self, title: str, message: str):
        dlg = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=title,
        )
        dlg.format_secondary_text(message)
        dlg.run()
        dlg.destroy()
