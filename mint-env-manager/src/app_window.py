"""
GTK 3 Desktop Interface for Mint Environment Manager.
Provides native Linux Mint Cinnamon styling, variable editor,
safety backup notifications, and live API key validation.
"""

import os
import re
import sys
import threading
from typing import Dict, List, Optional, Tuple

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

try:
    from mint_env_manager.env_parser import EnvFile, detect_service, EnvEntry
    from mint_env_manager.api_tester import test_api_key, SERVICES_CATALOG, TestResult
except ImportError:
    from env_parser import EnvFile, detect_service, EnvEntry
    from api_tester import test_api_key, SERVICES_CATALOG, TestResult

CUSTOM_CSS = b"""
/* Mint Environment Manager Modern Theme */
headerbar {
    padding: 6px 12px;
}

.admin-badge {
    background-color: #065f46;
    color: #ecfdf5;
    font-weight: bold;
    font-size: 11px;
    padding: 3px 10px;
    border-radius: 12px;
}

.preview-badge {
    background-color: #b45309;
    color: #fef3c7;
    font-weight: bold;
    font-size: 11px;
    padding: 3px 10px;
    border-radius: 12px;
}

.card-frame {
    background-color: alpha(@theme_base_color, 0.4);
    border: 1px solid alpha(@theme_fg_color, 0.15);
    border-radius: 8px;
    padding: 12px;
    margin: 6px 10px;
}

.editor-label {
    font-weight: bold;
    font-size: 12px;
    color: alpha(@theme_fg_color, 0.85);
}

.code-entry {
    font-family: monospace;
    font-size: 13px;
}

.suggested-action {
    background-color: #10b981;
    color: white;
    font-weight: bold;
    border-radius: 6px;
    padding: 4px 14px;
}

.suggested-action:hover {
    background-color: #059669;
}

.test-btn {
    background-color: #0284c7;
    color: white;
    font-weight: bold;
    border-radius: 6px;
    padding: 4px 14px;
}

.test-btn:hover {
    background-color: #0369a1;
}

.status-valid {
    color: #10b981;
    font-weight: bold;
}

.status-invalid {
    color: #ef4444;
    font-weight: bold;
}

.status-untested {
    color: alpha(@theme_fg_color, 0.5);
}

.result-card-success {
    background-color: rgba(16, 185, 129, 0.15);
    border: 1px solid #10b981;
    border-radius: 8px;
    padding: 12px;
}

.result-card-error {
    background-color: rgba(239, 68, 68, 0.15);
    border: 1px solid #ef4444;
    border-radius: 8px;
    padding: 12px;
}
"""


class AppWindow(Gtk.Window):
    def __init__(self, target_file: str = "/etc/environment", is_admin: bool = True):
        super().__init__(title="Mint Environment Manager")
        self.set_default_size(1050, 700)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.is_admin = is_admin
        self.env_file = EnvFile(target_file)
        self.reveal_secrets = False
        self.current_filter_text = ""

        # Apply CSS
        self._apply_styles()

        # Build UI
        self._create_header_bar()
        self._create_body()

        # Connect delete event for unsaved changes warning
        self.connect("delete-event", self._on_window_delete)

        # Load file
        self._load_file(target_file)

    def _apply_styles(self):
        screen = Gdk.Screen.get_default()
        if screen:
            css_provider = Gtk.CssProvider()
            css_provider.load_from_data(CUSTOM_CSS)
            Gtk.StyleContext.add_provider_for_screen(
                screen,
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    def _create_header_bar(self):
        self.header_bar = Gtk.HeaderBar()
        self.header_bar.set_show_close_button(True)
        self.header_bar.props.title = "Mint Environment Manager"
        self.header_bar.props.subtitle = self.env_file.file_path
        self.set_titlebar(self.header_bar)

        # Admin Badge
        badge_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        if self.is_admin:
            badge_label = Gtk.Label(label="🛡️ Admin (Root)")
            badge_label.get_style_context().add_class("admin-badge")
        else:
            badge_label = Gtk.Label(label="⚠️ Preview Mode (Read-Only)")
            badge_label.get_style_context().add_class("preview-badge")
        badge_box.pack_start(badge_label, False, False, 0)
        self.header_bar.pack_start(badge_box)

        # File Selector Menu
        file_menu_btn = Gtk.MenuButton(label="📁 Switch File")
        menu = Gtk.Menu()

        item_default = Gtk.MenuItem(label="System Default (/etc/environment)")
        item_default.connect("activate", lambda w: self._switch_to_file("/etc/environment"))
        menu.append(item_default)

        item_custom = Gtk.MenuItem(label="Open Custom .env File...")
        item_custom.connect("activate", lambda w: self._on_choose_custom_file())
        menu.append(item_custom)

        item_reload = Gtk.MenuItem(label="🔄 Reload Current File")
        item_reload.connect("activate", lambda w: self._load_file(self.env_file.file_path))
        menu.append(item_reload)

        menu.show_all()
        file_menu_btn.set_popup(menu)
        self.header_bar.pack_start(file_menu_btn)

        # Right Controls: Save Button
        self.btn_save = Gtk.Button(label="💾 Save to File")
        self.btn_save.get_style_context().add_class("suggested-action")
        self.btn_save.connect("clicked", self._on_save_clicked)
        self.header_bar.pack_end(self.btn_save)

        # Unsaved indicator
        self.lbl_unsaved = Gtk.Label(label="")
        self.header_bar.pack_end(self.lbl_unsaved)

    def _create_body(self):
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add(main_vbox)

        # InfoBar for alerts
        self.info_bar = Gtk.InfoBar()
        self.info_bar.set_show_close_button(True)
        self.info_bar.connect("response", lambda ib, resp: ib.hide())
        self.lbl_infobar = Gtk.Label(label="")
        self.info_bar.get_content_area().add(self.lbl_infobar)
        self.info_bar.set_no_show_all(True)
        main_vbox.pack_start(self.info_bar, False, False, 0)

        # Card: Add / Edit Variable
        card_box = self._create_editor_card()
        main_vbox.pack_start(card_box, False, False, 4)

        # Toolbar: Search, Masking, Total
        toolbar = self._create_list_toolbar()
        main_vbox.pack_start(toolbar, False, False, 2)

        # Table: Variables TreeView
        tree_scroll = self._create_variables_tree()
        main_vbox.pack_start(tree_scroll, True, True, 2)

        # Footer Status Bar
        footer = self._create_footer()
        main_vbox.pack_start(footer, False, False, 0)

    def _create_editor_card(self) -> Gtk.Widget:
        frame = Gtk.Frame(label=" ➕ Add or Modify Environment Variable ")
        frame.get_style_context().add_class("card-frame")

        grid = Gtk.Grid()
        grid.set_column_spacing(10)
        grid.set_row_spacing(8)
        grid.set_border_width(8)
        frame.add(grid)

        # Row 0: Variable Name & Presets
        lbl_name = Gtk.Label(label="Variable Name:", xalign=0)
        lbl_name.get_style_context().add_class("editor-label")
        grid.attach(lbl_name, 0, 0, 1, 1)

        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.entry_name = Gtk.Entry()
        self.entry_name.set_placeholder_text("e.g. OPENAI_API_KEY, STEAM_API_KEY, Personal_Access_Token")
        self.entry_name.get_style_context().add_class("code-entry")
        self.entry_name.set_hexpand(True)
        self.entry_name.connect("changed", self._on_name_changed)
        name_box.pack_start(self.entry_name, True, True, 0)

        # Template Presets ComboBox
        self.combo_presets = Gtk.ComboBoxText()
        self.combo_presets.append_text("⚡ Quick Service Presets...")
        self.preset_map = {
            "🎮 Steam Web API": "STEAM_API_KEY",
            "🐙 GitHub Token": "Personal_Access_Token",
            "🤖 OpenAI API": "OPENAI_API_KEY",
            "♊ Google Gemini": "GEMINI_API_KEY",
            "🧠 Anthropic Claude": "ANTHROPIC_API_KEY",
            "⚡ Groq Cloud": "GROQ_API_KEY",
            "📥 Real-Debrid API": "RD_API_KEY",
            "🤗 Hugging Face Token": "HF_TOKEN",
            "💬 Discord Webhook": "DISCORD_WEBHOOK",
            "🎬 TMDB API": "TMDB_API_KEY",
            "⛅ WeatherAPI": "WEATHERAPI_KEY",
            "🌪️ Mistral AI": "MISTRAL_API_KEY",
            "🧬 Cohere API": "COHERE_API_KEY",
        }
        for name in self.preset_map.keys():
            self.combo_presets.append_text(name)
        self.combo_presets.set_active(0)
        self.combo_presets.connect("changed", self._on_preset_selected)
        name_box.pack_start(self.combo_presets, False, False, 0)

        grid.attach(name_box, 1, 0, 3, 1)

        # Row 1: Variable Value & Actions
        lbl_val = Gtk.Label(label="Value / Key:", xalign=0)
        lbl_val.get_style_context().add_class("editor-label")
        grid.attach(lbl_val, 0, 1, 1, 1)

        val_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.entry_value = Gtk.Entry()
        self.entry_value.set_placeholder_text("Enter secret key, token, or value")
        self.entry_value.get_style_context().add_class("code-entry")
        self.entry_value.set_visibility(False)
        self.entry_value.set_hexpand(True)
        val_box.pack_start(self.entry_value, True, True, 0)

        # Eye button to toggle visibility
        self.btn_eye = Gtk.Button(label="👁️ Show")
        self.btn_eye.set_tooltip_text("Toggle Show/Hide Secret")
        self.btn_eye.connect("clicked", self._on_toggle_entry_visibility)
        val_box.pack_start(self.btn_eye, False, False, 0)

        # Paste button
        btn_paste = Gtk.Button(label="📋 Paste")
        btn_paste.set_tooltip_text("Paste from Clipboard")
        btn_paste.connect("clicked", self._on_paste_clicked)
        val_box.pack_start(btn_paste, False, False, 0)

        grid.attach(val_box, 1, 1, 3, 1)

        # Row 2: Action Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        self.btn_add_update = Gtk.Button(label="➕ Add / Update Variable")
        self.btn_add_update.get_style_context().add_class("suggested-action")
        self.btn_add_update.connect("clicked", self._on_add_or_update_clicked)
        btn_box.pack_start(self.btn_add_update, False, False, 0)

        # Test API Key Button
        self.btn_test_current = Gtk.Button(label="🧪 Test API Key")
        self.btn_test_current.get_style_context().add_class("test-btn")
        self.btn_test_current.set_tooltip_text("Test this API key against online verification service")
        self.btn_test_current.connect("clicked", self._on_test_current_clicked)
        btn_box.pack_start(self.btn_test_current, False, False, 0)

        btn_clear = Gtk.Button(label="🧹 Clear Fields")
        btn_clear.connect("clicked", self._on_clear_clicked)
        btn_box.pack_start(btn_clear, False, False, 0)

        self.lbl_detected_service = Gtk.Label(label="Provider: 🔍 Auto-Detect")
        self.lbl_detected_service.get_style_context().add_class("editor-label")
        btn_box.pack_end(self.lbl_detected_service, False, False, 0)

        grid.attach(btn_box, 1, 2, 3, 1)

        return frame

    def _create_list_toolbar(self) -> Gtk.Widget:
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)
        toolbar.set_margin_top(4)
        toolbar.set_margin_bottom(4)

        # Search Bar
        lbl_search = Gtk.Label(label="🔍 Search:")
        toolbar.pack_start(lbl_search, False, False, 0)

        self.entry_search = Gtk.SearchEntry()
        self.entry_search.set_placeholder_text("Filter by variable name or value...")
        self.entry_search.connect("search-changed", self._on_search_changed)
        self.entry_search.set_hexpand(True)
        toolbar.pack_start(self.entry_search, True, True, 0)

        # Reveal all values toggle
        self.btn_toggle_all_secrets = Gtk.Button(label="👁️ Reveal All Values")
        self.btn_toggle_all_secrets.connect("clicked", self._on_toggle_all_secrets)
        toolbar.pack_start(self.btn_toggle_all_secrets, False, False, 0)

        # Counter
        self.lbl_count = Gtk.Label(label="0 variables")
        toolbar.pack_start(self.lbl_count, False, False, 6)

        return toolbar

    def _create_variables_tree(self) -> Gtk.Widget:
        # Columns:
        # 0: idx (str)
        # 1: key (str)
        # 2: displayed_val (str)
        # 3: raw_val (str)
        # 4: service_name (str)
        # 5: test_status (str)
        # 6: service_id (str)
        self.store = Gtk.ListStore(str, str, str, str, str, str, str)

        # Filter model for search
        self.filter_model = self.store.filter_new()
        self.filter_model.set_visible_func(self._filter_func)

        self.tree = Gtk.TreeView(model=self.filter_model)
        self.tree.set_rules_hint(True)
        self.tree.connect("row-activated", self._on_row_double_click)

        # Column 0: Index
        col_idx = Gtk.TreeViewColumn("#", Gtk.CellRendererText(), text=0)
        col_idx.set_resizable(False)
        self.tree.append_column(col_idx)

        # Column 1: Variable Name
        cell_name = Gtk.CellRendererText()
        cell_name.props.weight = Pango.Weight.BOLD
        cell_name.props.family = "monospace"
        col_name = Gtk.TreeViewColumn("Variable Name", cell_name, text=1)
        col_name.set_resizable(True)
        col_name.set_min_width(200)
        self.tree.append_column(col_name)

        # Column 2: Value
        cell_val = Gtk.CellRendererText()
        cell_val.props.family = "monospace"
        cell_val.props.ellipsize = Pango.EllipsizeMode.END
        col_val = Gtk.TreeViewColumn("Value / Key", cell_val, text=2)
        col_val.set_resizable(True)
        col_val.set_min_width(240)
        self.tree.append_column(col_val)

        # Column 3: Service Provider
        cell_service = Gtk.CellRendererText()
        col_service = Gtk.TreeViewColumn("Detected Provider", cell_service, text=4)
        col_service.set_resizable(True)
        col_service.set_min_width(160)
        self.tree.append_column(col_service)

        # Column 4: Status
        cell_status = Gtk.CellRendererText()
        col_status = Gtk.TreeViewColumn("Verification Status", cell_status, text=5)
        col_status.set_cell_data_func(cell_status, self._render_status_cell)
        col_status.set_resizable(True)
        col_status.set_min_width(170)
        self.tree.append_column(col_status)

        # Column 5: Actions
        col_actions = Gtk.TreeViewColumn("Row Actions")
        col_actions.set_resizable(False)
        col_actions.set_min_width(220)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        # We handle row actions via selection and context buttons
        self.tree.append_column(col_actions)

        # Scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_margin_start(10)
        scrolled.set_margin_end(10)
        scrolled.add(self.tree)

        # Action bar directly below tree
        action_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        action_bar.set_margin_start(12)
        action_bar.set_margin_end(12)
        action_bar.set_margin_top(4)
        action_bar.set_margin_bottom(6)

        btn_table_test = Gtk.Button(label="🧪 Test Selected Key")
        btn_table_test.get_style_context().add_class("test-btn")
        btn_table_test.connect("clicked", self._on_table_test_clicked)
        action_bar.pack_start(btn_table_test, False, False, 0)

        btn_table_edit = Gtk.Button(label="✏️ Edit Selected")
        btn_table_edit.connect("clicked", self._on_table_edit_clicked)
        action_bar.pack_start(btn_table_edit, False, False, 0)

        btn_table_copy = Gtk.Button(label="📋 Copy Value")
        btn_table_copy.connect("clicked", self._on_table_copy_clicked)
        action_bar.pack_start(btn_table_copy, False, False, 0)

        btn_table_del = Gtk.Button(label="🗑️ Delete Variable")
        btn_table_del.connect("clicked", self._on_table_delete_clicked)
        action_bar.pack_start(btn_table_del, False, False, 0)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vbox.pack_start(scrolled, True, True, 0)
        vbox.pack_start(action_bar, False, False, 0)

        return vbox

    def _render_status_cell(self, column, cell, model, iter, data):
        status_text = model.get_value(iter, 5)
        if "Valid" in status_text or "Verified" in status_text or "Online" in status_text or "Active" in status_text:
            cell.props.foreground = "#10b981"
        elif "Invalid" in status_text or "Failed" in status_text or "Denied" in status_text or "Error" in status_text:
            cell.props.foreground = "#ef4444"
        else:
            cell.props.foreground = "#888888"

    def _create_footer(self) -> Gtk.Widget:
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        footer.set_margin_start(14)
        footer.set_margin_end(14)
        footer.set_margin_top(6)
        footer.set_margin_bottom(8)

        self.lbl_file_info = Gtk.Label(label="File: /etc/environment")
        footer.pack_start(self.lbl_file_info, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        footer.pack_start(sep, False, False, 0)

        self.lbl_backup_info = Gtk.Label(label="Automatic safety backups enabled")
        footer.pack_start(self.lbl_backup_info, False, False, 0)

        # Big Save Button at bottom
        self.btn_bottom_save = Gtk.Button(label="💾 Save All Changes to File")
        self.btn_bottom_save.get_style_context().add_class("suggested-action")
        self.btn_bottom_save.connect("clicked", self._on_save_clicked)
        footer.pack_end(self.btn_bottom_save, False, False, 0)

        return footer

    # --------------------------------------------------------------------------
    # Data Loading and Refreshing
    # --------------------------------------------------------------------------

    def _load_file(self, path: str):
        ok, msg = self.env_file.load(path)
        self.header_bar.props.subtitle = self.env_file.file_path
        self.lbl_file_info.set_text(f"File: {self.env_file.file_path}")

        if ok:
            self._show_info(msg, Gtk.MessageType.INFO)
        else:
            self._show_info(msg, Gtk.MessageType.ERROR)

        self._refresh_store()
        self._update_dirty_state()

    def _refresh_store(self):
        self.store.clear()
        entries = self.env_file.get_entries()

        for idx, entry in enumerate(entries, 1):
            service_id, service_name, _ = detect_service(entry.key, entry.value)
            displayed_val = entry.value if self.reveal_secrets else self._mask_value(entry.value)
            status_text = entry.test_status or "⚪ Not Tested"

            self.store.append([
                str(idx),
                entry.key,
                displayed_val,
                entry.value,
                service_name,
                status_text,
                service_id,
            ])

        count = len(entries)
        self.lbl_count.set_text(f"{count} variable{'s' if count != 1 else ''}")

    def _mask_value(self, val: str) -> str:
        if len(val) <= 6:
            return "••••••"
        return val[:4] + "••••••••" + val[-4:]

    def _update_dirty_state(self):
        if self.env_file.is_dirty:
            self.lbl_unsaved.set_markup("<span color='#f59e0b'><b>● Unsaved Changes</b></span>")
            self.btn_save.set_sensitive(True)
            self.btn_bottom_save.set_sensitive(True)
        else:
            self.lbl_unsaved.set_markup("<span color='#10b981'>✓ Saved</span>")
            self.btn_save.set_sensitive(False)
            self.btn_bottom_save.set_sensitive(False)

    def _show_info(self, text: str, msg_type: Gtk.MessageType = Gtk.MessageType.INFO):
        self.info_bar.set_message_type(msg_type)
        self.lbl_infobar.set_text(text)
        self.info_bar.show_all()

    # --------------------------------------------------------------------------
    # Event Handlers
    # --------------------------------------------------------------------------

    def _on_name_changed(self, entry):
        name = entry.get_text().strip()
        val = self.entry_value.get_text().strip()
        service_id, service_name, _ = detect_service(name, val)
        self.lbl_detected_service.set_text(f"Provider: {service_name}")

    def _on_preset_selected(self, combo):
        selected_text = combo.get_active_text()
        if selected_text and selected_text in self.preset_map:
            key_name = self.preset_map[selected_text]
            self.entry_name.set_text(key_name)
            self.entry_value.grab_focus()

    def _on_toggle_entry_visibility(self, btn):
        current = self.entry_value.get_visibility()
        self.entry_value.set_visibility(not current)
        btn.set_label("🙈 Hide" if not current else "👁️ Show")

    def _on_toggle_all_secrets(self, btn):
        self.reveal_secrets = not self.reveal_secrets
        btn.set_label("🙈 Hide All Values" if self.reveal_secrets else "👁️ Reveal All Values")
        self._refresh_store()

    def _on_paste_clicked(self, btn):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        text = clipboard.wait_for_text()
        if text:
            self.entry_value.set_text(text.strip())

    def _on_clear_clicked(self, btn):
        self.entry_name.set_text("")
        self.entry_value.set_text("")
        self.combo_presets.set_active(0)
        self.btn_add_update.set_label("➕ Add / Update Variable")

    def _on_search_changed(self, entry):
        self.current_filter_text = entry.get_text().lower().strip()
        self.filter_model.refilter()

    def _filter_func(self, model, iter, data):
        if not self.current_filter_text:
            return True
        key = model.get_value(iter, 1).lower()
        val = model.get_value(iter, 3).lower()
        service = model.get_value(iter, 4).lower()
        return (
            self.current_filter_text in key
            or self.current_filter_text in val
            or self.current_filter_text in service
        )

    def _on_add_or_update_clicked(self, btn):
        key = self.entry_name.get_text().strip()
        val = self.entry_value.get_text().strip()

        if not key:
            self._show_info("Please enter a variable name.", Gtk.MessageType.WARNING)
            self.entry_name.grab_focus()
            return

        # Validate name
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            self._show_info(
                f"Invalid name '{key}'. Variable names must start with a letter/underscore and contain only letters, numbers, and underscores.",
                Gtk.MessageType.ERROR,
            )
            return

        try:
            self.env_file.set_entry(key, val)
            self._refresh_store()
            self._update_dirty_state()
            self._show_info(f"Updated variable '{key}'. Click 'Save to File' to write changes.", Gtk.MessageType.INFO)
            self._on_clear_clicked(None)
        except Exception as e:
            self._show_info(f"Error adding variable: {e}", Gtk.MessageType.ERROR)

    def _on_save_clicked(self, btn):
        if not self.is_admin and os.geteuid() != 0 and self.env_file.file_path == "/etc/environment":
            self._show_info("Cannot save: Root/admin permissions required to modify /etc/environment.", Gtk.MessageType.ERROR)
            return

        ok, msg, backup_path = self.env_file.save()
        if ok:
            backup_note = f" (Safety backup created: {os.path.basename(backup_path)})" if backup_path else ""
            self._show_info(f"✅ {msg}{backup_note}", Gtk.MessageType.INFO)
            self._update_dirty_state()
        else:
            self._show_info(f"❌ {msg}", Gtk.MessageType.ERROR)

    def _switch_to_file(self, path: str):
        if self.env_file.is_dirty:
            if not self._confirm_unsaved():
                return
        self._load_file(path)

    def _on_choose_custom_file(self):
        if self.env_file.is_dirty:
            if not self._confirm_unsaved():
                return

        dialog = Gtk.FileChooserDialog(
            title="Open Environment (.env) File",
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
        )

        filter_env = Gtk.FileFilter()
        filter_env.set_name("Environment Files (.env, environment)")
        filter_env.add_pattern("*.env")
        filter_env.add_pattern(".env*")
        filter_env.add_pattern("environment*")
        dialog.add_filter(filter_env)

        filter_all = Gtk.FileFilter()
        filter_all.set_name("All Files")
        filter_all.add_pattern("*")
        dialog.add_filter(filter_all)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filename = dialog.get_filename()
            dialog.destroy()
            self._load_file(filename)
        else:
            dialog.destroy()

    def _confirm_unsaved(self) -> bool:
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text="You have unsaved changes!",
        )
        dialog.format_secondary_text("Discard unsaved changes and continue?")
        resp = dialog.run()
        dialog.destroy()
        return resp == Gtk.ResponseType.YES

    def _on_window_delete(self, widget, event):
        if self.env_file.is_dirty:
            if not self._confirm_unsaved():
                return True  # Prevent closing
        return False

    # --------------------------------------------------------------------------
    # Selected Row Actions
    # --------------------------------------------------------------------------

    def _get_selected_row_data(self) -> Optional[Tuple[str, str, str, str, str]]:
        """Returns (key, raw_val, service_name, test_status, service_id) or None."""
        selection = self.tree.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter:
            # model is filter_model
            key = model.get_value(tree_iter, 1)
            raw_val = model.get_value(tree_iter, 3)
            service_name = model.get_value(tree_iter, 4)
            test_status = model.get_value(tree_iter, 5)
            service_id = model.get_value(tree_iter, 6)
            return key, raw_val, service_name, test_status, service_id
        return None

    def _on_row_double_click(self, tree, path, column):
        self._on_table_edit_clicked(None)

    def _on_table_edit_clicked(self, btn):
        data = self._get_selected_row_data()
        if not data:
            self._show_info("Please select a variable in the table first.", Gtk.MessageType.INFO)
            return
        key, raw_val, _, _, _ = data
        self.entry_name.set_text(key)
        self.entry_value.set_text(raw_val)
        self.btn_add_update.set_label(f"💾 Update '{key}'")
        self.entry_value.grab_focus()

    def _on_table_copy_clicked(self, btn):
        data = self._get_selected_row_data()
        if not data:
            self._show_info("Please select a variable in the table first.", Gtk.MessageType.INFO)
            return
        key, raw_val, _, _, _ = data
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(raw_val, -1)
        self._show_info(f"Copied value for '{key}' to clipboard.", Gtk.MessageType.INFO)

    def _on_table_delete_clicked(self, btn):
        data = self._get_selected_row_data()
        if not data:
            self._show_info("Please select a variable to delete.", Gtk.MessageType.INFO)
            return
        key, _, _, _, _ = data

        if key == "PATH":
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.YES_NO,
                text=f"Warning: Deleting critical system variable '{key}'",
            )
            dialog.format_secondary_text("Deleting PATH will break system commands and binaries! Are you completely sure?")
            resp = dialog.run()
            dialog.destroy()
            if resp != Gtk.ResponseType.YES:
                return

        self.env_file.remove_entry(key)
        self._refresh_store()
        self._update_dirty_state()
        self._show_info(f"Removed '{key}'. Remember to click 'Save to File'.", Gtk.MessageType.INFO)

    # --------------------------------------------------------------------------
    # API Key Verification Dialog & Background Testing
    # --------------------------------------------------------------------------

    def _on_test_current_clicked(self, btn):
        key = self.entry_name.get_text().strip()
        val = self.entry_value.get_text().strip()
        if not val:
            self._show_info("Please enter a value/key before testing.", Gtk.MessageType.WARNING)
            self.entry_value.grab_focus()
            return
        self._open_test_dialog(key or "VARIABLE", val)

    def _on_table_test_clicked(self, btn):
        data = self._get_selected_row_data()
        if not data:
            self._show_info("Please select a variable in the table to test.", Gtk.MessageType.INFO)
            return
        key, val, _, _, _ = data
        if not val:
            self._show_info(f"Variable '{key}' has an empty value.", Gtk.MessageType.WARNING)
            return
        self._open_test_dialog(key, val)

    def _open_test_dialog(self, var_name: str, var_val: str):
        dialog = Gtk.Dialog(
            title="API Key Verification Test",
            transient_for=self,
            flags=Gtk.DialogFlags.MODAL,
        )
        dialog.set_default_size(560, 420)
        dialog.set_border_width(12)

        content = dialog.get_content_area()
        content.set_spacing(10)

        # Header Info Card
        header_card = Gtk.Frame()
        header_card.get_style_context().add_class("card-frame")
        h_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        h_box.set_border_width(8)
        header_card.add(h_box)

        lbl_vname = Gtk.Label(xalign=0)
        lbl_vname.set_markup(f"<b>Testing Variable:</b> <code>{var_name}</code>")
        h_box.pack_start(lbl_vname, False, False, 0)

        masked_val = self._mask_value(var_val)
        lbl_vval = Gtk.Label(xalign=0)
        lbl_vval.set_markup(f"<b>Key:</b> <code>{masked_val}</code>")
        h_box.pack_start(lbl_vval, False, False, 0)

        content.pack_start(header_card, False, False, 0)

        # Provider Selector
        prov_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_prov = Gtk.Label(label="Provider Service:")
        prov_box.pack_start(lbl_prov, False, False, 0)

        combo_service = Gtk.ComboBoxText()
        detected_id, detected_name, _ = detect_service(var_name, var_val)
        active_idx = 0

        for i, (sid, sname) in enumerate(SERVICES_CATALOG):
            combo_service.append_text(sname)
            if sid == detected_id:
                active_idx = i

        combo_service.set_active(active_idx)
        prov_box.pack_start(combo_service, True, True, 0)
        content.pack_start(prov_box, False, False, 0)

        # Custom URL Box (revealed if custom selected)
        custom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl_url = Gtk.Label(label="Custom URL:")
        entry_custom_url = Gtk.Entry()
        entry_custom_url.set_placeholder_text("https://api.example.com/v1/user")
        entry_custom_url.set_hexpand(True)
        custom_box.pack_start(lbl_url, False, False, 0)
        custom_box.pack_start(entry_custom_url, True, True, 0)
        custom_box.set_no_show_all(True)
        content.pack_start(custom_box, False, False, 0)

        def on_service_combo_changed(cb):
            sel_text = cb.get_active_text()
            if sel_text and "Custom HTTP" in sel_text:
                custom_box.show_all()
            else:
                custom_box.hide()

        combo_service.connect("changed", on_service_combo_changed)
        on_service_combo_changed(combo_service)

        # Progress / Status Box
        progress_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        spinner = Gtk.Spinner()
        lbl_progress = Gtk.Label(label="Ready to test.")
        progress_box.pack_start(spinner, False, False, 0)
        progress_box.pack_start(lbl_progress, False, False, 0)
        content.pack_start(progress_box, False, False, 0)

        # Results Container
        results_frame = Gtk.Frame(label=" Verification Result ")
        results_frame.get_style_context().add_class("card-frame")
        results_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        results_vbox.set_border_width(10)
        results_frame.add(results_vbox)

        lbl_result_status = Gtk.Label(label="Click 'Run Test' below to verify key connectivity.", xalign=0)
        lbl_result_status.set_line_wrap(True)
        results_vbox.pack_start(lbl_result_status, False, False, 0)

        lbl_result_details = Gtk.Label(label="", xalign=0)
        lbl_result_details.set_line_wrap(True)
        results_vbox.pack_start(lbl_result_details, False, False, 0)

        content.pack_start(results_frame, True, True, 0)

        # Dialog Buttons
        btn_run = dialog.add_button("🚀 Run Verification Test", Gtk.ResponseType.APPLY)
        btn_run.get_style_context().add_class("test-btn")
        btn_close = dialog.add_button("Close", Gtk.ResponseType.CLOSE)

        # Testing logic
        def run_test_thread():
            sel_idx = combo_service.get_active()
            service_id = SERVICES_CATALOG[sel_idx][0] if 0 <= sel_idx < len(SERVICES_CATALOG) else "auto"
            custom_url = entry_custom_url.get_text().strip() if service_id == "custom" else None

            GLib.idle_add(spinner.start)
            GLib.idle_add(btn_run.set_sensitive, False)
            GLib.idle_add(lbl_progress.set_text, f"Testing key against service...")

            res = test_api_key(
                service_id=service_id,
                key=var_val,
                custom_url=custom_url,
                var_name=var_name,
            )

            def on_test_done():
                spinner.stop()
                btn_run.set_sensitive(True)
                lbl_progress.set_text(f"Completed in {res.latency_ms} ms")

                if res.success:
                    results_frame.get_style_context().remove_class("result-card-error")
                    results_frame.get_style_context().add_class("result-card-success")
                    status_markup = f"<span color='#10b981' size='large'><b>✅ Verification Successful! (HTTP {res.status_code or 200})</b></span>\n{res.summary}"
                else:
                    results_frame.get_style_context().remove_class("result-card-success")
                    results_frame.get_style_context().add_class("result-card-error")
                    status_markup = f"<span color='#ef4444' size='large'><b>❌ Verification Failed</b></span>\n{res.summary}"

                lbl_result_status.set_markup(status_markup)

                # Format account details
                detail_lines = []
                if res.account_info:
                    detail_lines.append("<b>Account Details:</b>")
                    for k, v in res.account_info.items():
                        detail_lines.append(f"  • <b>{k}:</b> {v}")
                if res.details:
                    detail_lines.append(f"\n<b>Diagnostics:</b>\n{res.details}")

                lbl_result_details.set_markup("\n".join(detail_lines))

                # Update the variable's status in the active EnvFile and table
                status_short = f"🟢 Valid ({res.service_name})" if res.success else f"🔴 Failed ({res.service_name})"
                entry_obj = self.env_file.get_entry(var_name)
                if entry_obj:
                    entry_obj.test_status = status_short
                    entry_obj.test_details = res.summary
                self._update_store_status(var_name, status_short)

            GLib.idle_add(on_test_done)

        def on_dialog_response(dlg, resp_id):
            if resp_id == Gtk.ResponseType.APPLY:
                threading.Thread(target=run_test_thread, daemon=True).start()
            else:
                dlg.destroy()

        dialog.connect("response", on_dialog_response)
        dialog.show_all()

        # Run test automatically upon opening dialog!
        threading.Thread(target=run_test_thread, daemon=True).start()

    def _update_store_status(self, var_name: str, status_text: str):
        for row in self.store:
            if row[1] == var_name:
                row[5] = status_text
                break
