"""
Main Window and UI Components for USBGuard Manager.
"""

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango, GdkPixbuf

from models import USBDevice, USBRule
from dialogs import AddRuleDialog, show_confirm_baseline_dialog, show_about_dialog

CSS_STYLE = b"""
.status-pill {
    font-size: 11px;
    font-weight: bold;
    border-radius: 12px;
    padding: 4px 10px;
    color: white;
}
.pill-blocked {
    background-color: #dc2626;
}
.pill-allowed {
    background-color: #16a34a;
}
.pill-warning {
    background-color: #d97706;
}
.pill-info {
    background-color: #2563eb;
}
.big-badge {
    font-size: 13px;
    font-weight: bold;
    border-radius: 6px;
    padding: 6px 14px;
}
.success-button {
    background-image: none;
    background-color: #16a34a;
    color: white;
    font-weight: bold;
}
.success-button:hover {
    background-color: #15803d;
}
.danger-button {
    background-image: none;
    background-color: #dc2626;
    color: white;
    font-weight: bold;
}
.danger-button:hover {
    background-color: #b91c1c;
}
.sidebar-box {
    background-color: alpha(@theme_base_color, 0.5);
    border-left: 1px solid alpha(@borders, 0.6);
    padding: 16px;
}
"""

class MainWindow(Gtk.Window):
    def __init__(self, backend, watcher):
        super().__init__(title="USB Guard")
        self.backend = backend
        self.watcher = watcher
        self.selected_device: USBDevice = None
        self.selected_rule: USBRule = None
        self.devices = []
        self.rules = []
        self.search_query = ""

        self.set_default_size(940, 640)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_icon_name("usbguard-manager")

        self._apply_css()
        self._build_headerbar()
        self._build_ui()

        # Connect window destroy
        self.connect("destroy", self._on_window_destroy)

        # Initial refresh
        self.refresh_all()

    def _apply_css(self):
        screen = Gdk.Screen.get_default()
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(CSS_STYLE)
        Gtk.StyleContext.add_provider_for_screen(
            screen,
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_headerbar(self):
        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(True)
        self.header.props.title = "USB Guard"
        self.header.props.subtitle = "USB Device Authorization & Security"
        self.set_titlebar(self.header)

        # Protection Mode Pill
        self.pill_status = Gtk.Label(label="Checking...")
        self.pill_status.get_style_context().add_class("status-pill")
        self.header.pack_start(self.pill_status)

        # Search Entry
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Filter devices...")
        self.search_entry.set_width_chars(18)
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.header.pack_end(self.search_entry)

        # Refresh Button
        btn_refresh = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        btn_refresh.set_tooltip_text("Refresh Devices & Rules")
        btn_refresh.connect("clicked", lambda b: self.refresh_all())
        self.header.pack_end(btn_refresh)

        # Hamburger Menu
        btn_menu = Gtk.MenuButton.new()
        btn_menu.set_image(Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON))
        menu = Gtk.Menu()

        item_baseline = Gtk.MenuItem(label="Trust All Currently Connected Devices")
        item_baseline.connect("activate", self._on_action_baseline)
        menu.append(item_baseline)

        item_fix_perms = Gtk.MenuItem(label="Configure User Permissions")
        item_fix_perms.connect("activate", self._on_action_fix_permissions)
        menu.append(item_fix_perms)

        item_restart = Gtk.MenuItem(label="Restart USBGuard Service")
        item_restart.connect("activate", self._on_action_restart_service)
        menu.append(item_restart)

        menu.append(Gtk.SeparatorMenuItem())

        item_about = Gtk.MenuItem(label="About USB Guard")
        item_about.connect("activate", lambda i: show_about_dialog(self))
        menu.append(item_about)

        menu.show_all()
        btn_menu.set_popup(menu)
        self.header.pack_end(btn_menu)

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(main_box)

        # InfoBar for alerts (Daemon stopped, etc.)
        self.infobar = Gtk.InfoBar()
        self.infobar.set_show_close_button(False)
        self.infobar_label = Gtk.Label()
        self.infobar_label.set_xalign(0)
        self.infobar_action_btn = Gtk.Button(label="Action")
        self.infobar.get_content_area().pack_start(self.infobar_label, True, True, 6)
        self.infobar.get_action_area().pack_start(self.infobar_action_btn, False, False, 0)
        self.infobar.set_no_show_all(True)
        main_box.pack_start(self.infobar, False, False, 0)

        # Stack Switcher Bar
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(150)

        switcher_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        switcher_box.set_border_width(8)
        switcher = Gtk.StackSwitcher()
        switcher.set_stack(self.stack)
        switcher_box.pack_start(switcher, False, False, 4)

        self.lbl_device_count = Gtk.Label()
        self.lbl_device_count.set_xalign(1)
        switcher_box.pack_end(self.lbl_device_count, False, False, 8)
        main_box.pack_start(switcher_box, False, False, 0)

        main_box.pack_start(self.stack, True, True, 0)

        # Tab 1: Connected Devices
        tab_devices = self._build_devices_tab()
        self.stack.add_titled(tab_devices, "devices", "Connected Devices")

        # Tab 2: Trusted Rules
        tab_rules = self._build_rules_tab()
        self.stack.add_titled(tab_rules, "rules", "Trusted Whitelist")

        # Tab 3: Settings & Protection
        tab_settings = self._build_settings_tab()
        self.stack.add_titled(tab_settings, "settings", "Settings & Protection")

    def _build_devices_tab(self) -> Gtk.Widget:
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(560)

        # Left: Device TreeView
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        left_box.set_border_width(8)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        # Model: [icon_name, name_markup, dev_id, status_markup, port, device_obj]
        self.dev_store = Gtk.ListStore(str, str, str, str, str, object)
        self.dev_tree = Gtk.TreeView(model=self.dev_store)
        self.dev_tree.set_rules_hint(True)
        self.dev_tree.get_selection().connect("changed", self._on_device_selection_changed)

        # Column 0: Status Icon
        r_icon = Gtk.CellRendererPixbuf()
        col_icon = Gtk.TreeViewColumn("", r_icon, icon_name=0)
        col_icon.set_fixed_width(40)
        self.dev_tree.append_column(col_icon)

        # Column 1: Device Name
        r_name = Gtk.CellRendererText()
        col_name = Gtk.TreeViewColumn("Device Name", r_name, markup=1)
        col_name.set_expand(True)
        col_name.set_sort_column_id(1)
        self.dev_tree.append_column(col_name)

        # Column 2: Device ID
        r_id = Gtk.CellRendererText()
        col_id = Gtk.TreeViewColumn("ID", r_id, text=2)
        col_id.set_sort_column_id(2)
        self.dev_tree.append_column(col_id)

        # Column 3: Trust Status
        r_status = Gtk.CellRendererText()
        col_status = Gtk.TreeViewColumn("Status", r_status, markup=3)
        col_status.set_sort_column_id(3)
        self.dev_tree.append_column(col_status)

        # Column 4: Port
        r_port = Gtk.CellRendererText()
        col_port = Gtk.TreeViewColumn("Port", r_port, text=4)
        col_port.set_sort_column_id(4)
        self.dev_tree.append_column(col_port)

        scrolled.add(self.dev_tree)
        left_box.pack_start(scrolled, True, True, 0)
        paned.pack1(left_box, resize=True, shrink=False)

        # Right: Detail & Action Pane
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        right_box.get_style_context().add_class("sidebar-box")
        right_box.set_size_request(340, -1)

        # Title
        self.detail_name = Gtk.Label()
        self.detail_name.set_line_wrap(True)
        self.detail_name.set_xalign(0)
        self.detail_name.set_markup("<b>No device selected</b>")
        right_box.pack_start(self.detail_name, False, False, 0)

        # Status badge
        self.detail_badge = Gtk.Label(label="")
        self.detail_badge.set_xalign(0)
        self.detail_badge.get_style_context().add_class("big-badge")
        right_box.pack_start(self.detail_badge, False, False, 0)

        # Grid of properties
        grid = Gtk.Grid()
        grid.set_column_spacing(10)
        grid.set_row_spacing(8)

        def add_prop(row, label_text):
            lbl = Gtk.Label()
            lbl.set_markup(f"<span color='#888888'>{label_text}:</span>")
            lbl.set_xalign(1)
            val = Gtk.Label(label="—")
            val.set_xalign(0)
            val.set_selectable(True)
            val.set_line_wrap(True)
            grid.attach(lbl, 0, row, 1, 1)
            grid.attach(val, 1, row, 1, 1)
            return val

        self.prop_id = add_prop(0, "Device ID")
        self.prop_serial = add_prop(1, "Serial")
        self.prop_port = add_prop(2, "Port")
        self.prop_type = add_prop(3, "Type")
        self.prop_rule_id = add_prop(4, "Rule ID")

        right_box.pack_start(grid, False, False, 4)

        right_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 4)

        # Action Buttons
        lbl_actions = Gtk.Label()
        lbl_actions.set_markup("<b>Device Actions</b>")
        lbl_actions.set_xalign(0)
        right_box.pack_start(lbl_actions, False, False, 0)

        # Trust & Allow Button (Permanent Whitelist)
        self.btn_trust = Gtk.Button.new_with_label("🛡️ Trust & Allow Device")
        self.btn_trust.get_style_context().add_class("success-button")
        self.btn_trust.set_tooltip_text("Permanently allow this device. It will be trusted automatically whenever plugged in.")
        self.btn_trust.connect("clicked", self._on_trust_clicked)
        right_box.pack_start(self.btn_trust, False, False, 2)

        # Allow Once (Temporary)
        self.btn_allow_temp = Gtk.Button.new_with_label("⏱️ Allow Temporarily")
        self.btn_allow_temp.set_tooltip_text("Authorize for the current session only. It will be blocked again if unplugged.")
        self.btn_allow_temp.connect("clicked", self._on_allow_temp_clicked)
        right_box.pack_start(self.btn_allow_temp, False, False, 2)

        # Block Device
        self.btn_block = Gtk.Button.new_with_label("🛑 Block Device")
        self.btn_block.get_style_context().add_class("danger-button")
        self.btn_block.set_tooltip_text("Immediately deauthorize and block this USB device.")
        self.btn_block.connect("clicked", self._on_block_clicked)
        right_box.pack_start(self.btn_block, False, False, 2)

        # Remove from Whitelist
        self.btn_untrust = Gtk.Button.new_with_label("Remove from Trusted")
        self.btn_untrust.set_tooltip_text("Remove this device from the permanent trusted whitelist.")
        self.btn_untrust.connect("clicked", self._on_untrust_clicked)
        right_box.pack_start(self.btn_untrust, False, False, 2)

        self._update_action_buttons(None)

        paned.pack2(right_box, resize=False, shrink=False)
        return paned

    def _build_rules_tab(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_border_width(10)

        # Toolbar
        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        btn_add_rule = Gtk.Button.new_with_label("+ Add Trusted Device Rule...")
        btn_add_rule.get_style_context().add_class("suggested-action")
        btn_add_rule.connect("clicked", self._on_add_rule_dialog)
        tb.pack_start(btn_add_rule, False, False, 0)

        self.btn_del_rule = Gtk.Button.new_with_label("Delete Rule")
        self.btn_del_rule.set_sensitive(False)
        self.btn_del_rule.connect("clicked", self._on_delete_rule)
        tb.pack_start(self.btn_del_rule, False, False, 0)

        btn_baseline = Gtk.Button.new_with_label("Trust All Connected (Baseline)")
        btn_baseline.set_tooltip_text("Generate trusted rules for all currently plugged-in devices")
        btn_baseline.connect("clicked", self._on_action_baseline)
        tb.pack_start(btn_baseline, False, False, 0)

        box.pack_start(tb, False, False, 0)

        # Rules TreeView
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        # Model: [rule_id, action_markup, dev_id, name, serial, rule_obj]
        self.rules_store = Gtk.ListStore(int, str, str, str, str, object)
        self.rules_tree = Gtk.TreeView(model=self.rules_store)
        self.rules_tree.set_rules_hint(True)
        self.rules_tree.get_selection().connect("changed", self._on_rule_selection_changed)

        # Columns
        col_id = Gtk.TreeViewColumn("Rule #", Gtk.CellRendererText(), text=0)
        col_id.set_sort_column_id(0)
        self.rules_tree.append_column(col_id)

        col_act = Gtk.TreeViewColumn("Action", Gtk.CellRendererText(), markup=1)
        col_act.set_sort_column_id(1)
        self.rules_tree.append_column(col_act)

        col_dev = Gtk.TreeViewColumn("Device ID", Gtk.CellRendererText(), text=2)
        col_dev.set_sort_column_id(2)
        self.rules_tree.append_column(col_dev)

        col_nm = Gtk.TreeViewColumn("Label / Name", Gtk.CellRendererText(), text=3)
        col_nm.set_expand(True)
        col_nm.set_sort_column_id(3)
        self.rules_tree.append_column(col_nm)

        col_ser = Gtk.TreeViewColumn("Serial Number", Gtk.CellRendererText(), text=4)
        col_ser.set_sort_column_id(4)
        self.rules_tree.append_column(col_ser)

        scrolled.add(self.rules_tree)
        box.pack_start(scrolled, True, True, 0)
        return box

    def _build_settings_tab(self) -> Gtk.Widget:
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_border_width(16)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        scrolled.add(vbox)

        # Section 1: Security Policy
        grp_sec = Gtk.Frame(label=" USB Protection Policy ")
        grp_sec_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        grp_sec_box.set_border_width(14)
        grp_sec.add(grp_sec_box)

        row_block = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        vbox_block_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        lbl_block_title = Gtk.Label()
        lbl_block_title.set_markup("<b>Block unknown USB devices by default (Recommended)</b>")
        lbl_block_title.set_xalign(0)
        lbl_block_sub = Gtk.Label(label="Any newly inserted USB device will be blocked immediately until you authorize or trust it.")
        lbl_block_sub.set_xalign(0)
        lbl_block_sub.get_style_context().add_class("dim-label")
        vbox_block_text.pack_start(lbl_block_title, False, False, 0)
        vbox_block_text.pack_start(lbl_block_sub, False, False, 0)
        row_block.pack_start(vbox_block_text, True, True, 0)

        self.switch_block_default = Gtk.Switch()
        self.switch_block_default.set_valign(Gtk.Align.CENTER)
        self.switch_block_default.connect("state-set", self._on_switch_block_toggled)
        row_block.pack_end(self.switch_block_default, False, False, 0)
        grp_sec_box.pack_start(row_block, False, False, 0)

        vbox.pack_start(grp_sec, False, False, 0)

        # Section 2: Notifications
        grp_notif = Gtk.Frame(label=" Desktop Notifications ")
        grp_notif_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        grp_notif_box.set_border_width(14)
        grp_notif.add(grp_notif_box)

        row_notif = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        vbox_notif_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        lbl_notif_title = Gtk.Label()
        lbl_notif_title.set_markup("<b>Notify when untrusted USB is blocked</b>")
        lbl_notif_title.set_xalign(0)
        lbl_notif_sub = Gtk.Label(label="Displays a popup alert immediately when an unrecognized USB device is plugged in.")
        lbl_notif_sub.set_xalign(0)
        vbox_notif_text.pack_start(lbl_notif_title, False, False, 0)
        vbox_notif_text.pack_start(lbl_notif_sub, False, False, 0)
        row_notif.pack_start(vbox_notif_text, True, True, 0)

        self.switch_notif = Gtk.Switch()
        self.switch_notif.set_active(True)
        self.switch_notif.set_valign(Gtk.Align.CENTER)
        self.switch_notif.connect("state-set", self._on_switch_notif_toggled)
        row_notif.pack_end(self.switch_notif, False, False, 0)
        grp_notif_box.pack_start(row_notif, False, False, 0)

        vbox.pack_start(grp_notif, False, False, 0)

        # Section 3: Daemon & Permissions
        grp_daemon = Gtk.Frame(label=" Daemon & Service Status ")
        grp_daemon_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        grp_daemon_box.set_border_width(14)
        grp_daemon.add(grp_daemon_box)

        row_status = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lbl_svc = Gtk.Label(label="USBGuard Service:")
        lbl_svc.set_xalign(0)
        self.lbl_svc_status = Gtk.Label(label="Checking...")
        self.lbl_svc_status.set_xalign(0)
        row_status.pack_start(lbl_svc, False, False, 0)
        row_status.pack_start(self.lbl_svc_status, True, True, 0)

        btn_svc_restart = Gtk.Button.new_with_label("Restart Service")
        btn_svc_restart.connect("clicked", self._on_action_restart_service)
        row_status.pack_end(btn_svc_restart, False, False, 0)
        grp_daemon_box.pack_start(row_status, False, False, 0)

        row_perm = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lbl_perm_desc = Gtk.Label(label="Configure IPC access so desktop users can manage USB rules without passwords.")
        lbl_perm_desc.set_xalign(0)
        row_perm.pack_start(lbl_perm_desc, True, True, 0)
        btn_fix_perm = Gtk.Button.new_with_label("Configure Permissions")
        btn_fix_perm.connect("clicked", self._on_action_fix_permissions)
        row_perm.pack_end(btn_fix_perm, False, False, 0)
        grp_daemon_box.pack_start(row_perm, False, False, 0)

        vbox.pack_start(grp_daemon, False, False, 0)

        return scrolled

    def refresh_all(self):
        """Reloads status, devices, and rules from backend."""
        is_installed = self.backend.is_installed()
        is_active = self.backend.is_service_active()
        implicit_policy = self.backend.get_implicit_policy()

        # Update HeaderBar pill
        ctx = self.pill_status.get_style_context()
        ctx.remove_class("pill-blocked")
        ctx.remove_class("pill-allowed")
        ctx.remove_class("pill-warning")

        if not is_installed:
            self.pill_status.set_text("⚠️ USBGuard Not Installed")
            ctx.add_class("pill-warning")
            self._show_infobar("USBGuard package is not installed. Please install 'usbguard' to activate hardware enforcement.", "Install USBGuard")
        elif not is_active:
            self.pill_status.set_text("🛑 Service Inactive")
            ctx.add_class("pill-blocked")
            self._show_infobar("USBGuard service is not running. USB device protection is currently inactive.", "Start Service")
        elif implicit_policy == "block":
            self.pill_status.set_text("🛡️ Active (Block Untrusted USBs)")
            ctx.add_class("pill-allowed")
            self._hide_infobar()
        else:
            self.pill_status.set_text("⚠️ Permissive (Allow All USBs)")
            ctx.add_class("pill-warning")
            self._show_infobar("Default policy is set to ALLOW. Any plugged-in USB is currently authorized automatically.", "Set to Block")

        # Update Settings Switch without firing callback
        self.switch_block_default.handler_block_by_func(self._on_switch_block_toggled)
        self.switch_block_default.set_active(implicit_policy == "block")
        self.switch_block_default.handler_unblock_by_func(self._on_switch_block_toggled)

        self.lbl_svc_status.set_markup("<b><span color='#16a34a'>Running</span></b>" if is_active else "<b><span color='#dc2626'>Stopped</span></b>")

        # Load devices & rules
        self.devices = self.backend.list_devices()
        self.rules = self.backend.list_rules()

        self._populate_device_tree()
        self._populate_rules_tree()

    def _show_infobar(self, message: str, button_label: str):
        self.infobar_label.set_text(message)
        self.infobar_action_btn.set_label(button_label)
        try:
            self.infobar_action_btn.disconnect_by_func(self._on_infobar_action)
        except Exception:
            pass
        self.infobar_action_btn.connect("clicked", self._on_infobar_action)
        self.infobar.show_all()

    def _hide_infobar(self):
        self.infobar.hide()

    def _on_infobar_action(self, btn):
        label = btn.get_label()
        if label == "Start Service":
            self._on_action_restart_service(None)
        elif label == "Set to Block":
            self._set_policy_block()

    def _populate_device_tree(self):
        self.dev_store.clear()
        total_blocked = 0
        total_allowed = 0

        filter_q = self.search_query.lower()

        for dev in self.devices:
            if dev.is_blocked:
                total_blocked += 1
            else:
                total_allowed += 1

            if filter_q:
                haystack = f"{dev.name} {dev.device_id} {dev.serial} {dev.via_port}".lower()
                if filter_q not in haystack:
                    continue

            if dev.is_blocked:
                icon_name = "dialog-error-symbolic"
                status_markup = "<span color='#dc2626' weight='bold'>BLOCKED</span>"
            elif dev.is_trusted:
                icon_name = "emblem-default-symbolic"
                status_markup = "<span color='#16a34a' weight='bold'>TRUSTED</span>"
            else:
                icon_name = "emblem-ok-symbolic"
                status_markup = "<span color='#2563eb'>Allowed (Temp)</span>"

            name_markup = f"<b>{GLIB_escape(dev.display_name)}</b>"

            self.dev_store.append([
                icon_name,
                name_markup,
                dev.device_id,
                status_markup,
                dev.via_port,
                dev
            ])

        self.lbl_device_count.set_text(f"Total: {len(self.devices)} | Blocked: {total_blocked} | Allowed: {total_allowed}")

    def _populate_rules_tree(self):
        self.rules_store.clear()
        for r in self.rules:
            act_markup = "<span color='#16a34a' weight='bold'>ALLOW</span>" if r.is_allow else "<span color='#dc2626' weight='bold'>BLOCK</span>"
            self.rules_store.append([
                r.rule_id,
                act_markup,
                r.device_id,
                r.name or "—",
                r.serial or "—",
                r
            ])

    def _on_device_selection_changed(self, selection):
        model, treeiter = selection.get_selected()
        if not treeiter:
            self.selected_device = None
            self._update_action_buttons(None)
            return

        dev: USBDevice = model[treeiter][5]
        self.selected_device = dev
        self._update_action_buttons(dev)

    def _update_action_buttons(self, dev: USBDevice):
        if not dev:
            self.detail_name.set_markup("<i>Select a device to view details and authorization options.</i>")
            self.detail_badge.set_text("")
            self.detail_badge.hide()
            self.prop_id.set_text("—")
            self.prop_serial.set_text("—")
            self.prop_port.set_text("—")
            self.prop_type.set_text("—")
            self.prop_rule_id.set_text("—")

            self.btn_trust.set_sensitive(False)
            self.btn_allow_temp.set_sensitive(False)
            self.btn_block.set_sensitive(False)
            self.btn_untrust.set_sensitive(False)
            return

        self.detail_name.set_markup(f"<b>{GLIB_escape(dev.display_name)}</b>")
        self.prop_id.set_text(dev.device_id or "Unknown")
        self.prop_serial.set_text(dev.serial or "None")
        self.prop_port.set_text(dev.via_port or "Unknown")
        self.prop_type.set_text(dev.interface_desc or "Unknown")
        self.prop_rule_id.set_text(str(dev.rule_id))

        badge_ctx = self.detail_badge.get_style_context()
        badge_ctx.remove_class("pill-blocked")
        badge_ctx.remove_class("pill-allowed")
        badge_ctx.remove_class("pill-info")

        if dev.is_blocked:
            self.detail_badge.set_text("STATUS: BLOCKED BY DEFAULT POLICY")
            badge_ctx.add_class("pill-blocked")
            self.btn_trust.set_sensitive(True)
            self.btn_allow_temp.set_sensitive(True)
            self.btn_block.set_sensitive(False)
            self.btn_untrust.set_sensitive(False)
        else:
            if dev.is_trusted:
                self.detail_badge.set_text("STATUS: PERMANENTLY TRUSTED")
                badge_ctx.add_class("pill-allowed")
                self.btn_trust.set_sensitive(False)
                self.btn_allow_temp.set_sensitive(False)
                self.btn_block.set_sensitive(True)
                self.btn_untrust.set_sensitive(True)
            else:
                self.detail_badge.set_text("STATUS: ALLOWED (TEMPORARY)")
                badge_ctx.add_class("pill-info")
                self.btn_trust.set_sensitive(True)
                self.btn_allow_temp.set_sensitive(False)
                self.btn_block.set_sensitive(True)
                self.btn_untrust.set_sensitive(False)

        self.detail_badge.show()

    def _on_trust_clicked(self, btn):
        if not self.selected_device:
            return
        success, msg = self.backend.allow_device(self.selected_device.rule_id, permanent=True)
        self._show_toast(msg, success)
        self.refresh_all()

    def _on_allow_temp_clicked(self, btn):
        if not self.selected_device:
            return
        success, msg = self.backend.allow_device(self.selected_device.rule_id, permanent=False)
        self._show_toast(msg, success)
        self.refresh_all()

    def _on_block_clicked(self, btn):
        if not self.selected_device:
            return
        success, msg = self.backend.block_device(self.selected_device.rule_id, permanent=False)
        self._show_toast(msg, success)
        self.refresh_all()

    def _on_untrust_clicked(self, btn):
        if not self.selected_device:
            return
        # Find matching rule in rules list
        matched_rule = None
        for r in self.rules:
            if r.device_id and r.device_id == self.selected_device.device_id:
                matched_rule = r
                break
        if matched_rule:
            success, msg = self.backend.remove_rule(matched_rule.rule_id)
            self._show_toast(msg, success)
            self.refresh_all()
        else:
            self._show_toast("No direct rule ID found for this device in policy.", False)

    def _on_rule_selection_changed(self, selection):
        model, treeiter = selection.get_selected()
        if not treeiter:
            self.selected_rule = None
            self.btn_del_rule.set_sensitive(False)
            return
        self.selected_rule = model[treeiter][5]
        self.btn_del_rule.set_sensitive(True)

    def _on_delete_rule(self, btn):
        if not self.selected_rule:
            return
        success, msg = self.backend.remove_rule(self.selected_rule.rule_id)
        self._show_toast(msg, success)
        self.refresh_all()

    def _on_add_rule_dialog(self, btn):
        dlg = AddRuleDialog(self)
        resp = dlg.run()
        if resp == Gtk.ResponseType.OK:
            target, dev_id, name, serial = dlg.get_rule_data()
            if not dev_id:
                self._show_toast("Device ID (VID:PID) is required.", False)
            else:
                success, msg = self.backend.append_rule(target, dev_id, name, serial)
                self._show_toast(msg, success)
                self.refresh_all()
        dlg.destroy()

    def _on_action_baseline(self, widget):
        if show_confirm_baseline_dialog(self):
            success, msg = self.backend.trust_all_current_baseline()
            self._show_toast(msg, success)
            self.refresh_all()

    def _on_action_fix_permissions(self, widget):
        success, msg = self.backend.fix_permissions()
        self._show_toast(msg, success)
        self.refresh_all()

    def _on_action_restart_service(self, widget):
        success, msg = self.backend.restart_service()
        self._show_toast(msg, success)
        self.refresh_all()

    def _on_switch_block_toggled(self, switch, state):
        target = "block" if state else "allow"
        success, msg = self.backend.set_implicit_policy(target)
        self._show_toast(msg, success)
        GLib.idle_add(self.refresh_all)
        return True

    def _set_policy_block(self):
        success, msg = self.backend.set_implicit_policy("block")
        self._show_toast(msg, success)
        self.refresh_all()

    def _on_switch_notif_toggled(self, switch, state):
        self.watcher.notifications_enabled = state
        return True

    def _on_search_changed(self, entry):
        self.search_query = entry.get_text().strip()
        self._populate_device_tree()

    def _show_toast(self, message: str, success: bool):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO if success else Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text=message
        )
        dialog.run()
        dialog.destroy()

    def _on_window_destroy(self, window):
        self.watcher.stop()
        Gtk.main_quit()


def GLIB_escape(text: str) -> str:
    return GLib.markup_escape_text(text)
