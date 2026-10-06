#!/usr/bin/env python3
"""
main.py - Modern GTK3 Graphical Interface for OmniBoot USB.
Features:
- Multi-ISO (Ventoy) vs Single-ISO (Direct Flash) mode selection
- Safe USB drive detection (protects OS / root / swap)
- ISO inspection (Linux vs Windows)
- Pre-flight storage calculation (drive capacity vs ISO size)
- Real-time progress bar, speed, ETA, and pkexec integration
"""

import os
import sys
import json
import time
import threading
import subprocess

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Pango

# Import detector
from detector import get_storage_devices, inspect_iso, format_bytes

APP_TITLE = "OmniBoot USB"
APP_SUBTITLE = "Multi-ISO & Single OS Bootable USB Creator"

# Custom CSS for modern styling
CSS_DATA = b"""
window {
    background-color: #f6f7f9;
}
.main-card {
    background-color: #ffffff;
    border-radius: 8px;
    border: 1px solid #dcdfe4;
    padding: 14px;
    margin-bottom: 10px;
}
.card-title {
    font-size: 14px;
    font-weight: bold;
    color: #1f2328;
    margin-bottom: 6px;
}
.card-subtitle {
    font-size: 12px;
    color: #656d76;
}
.mode-radio {
    font-size: 13px;
    font-weight: 600;
}
.storage-box {
    background-color: #f1f5f9;
    border-radius: 6px;
    padding: 10px;
}
.badge-ok {
    background-color: #d1fae5;
    color: #065f46;
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: bold;
    font-size: 12px;
}
.badge-error {
    background-color: #fee2e2;
    color: #991b1b;
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: bold;
    font-size: 12px;
}
.action-btn {
    font-size: 15px;
    font-weight: bold;
    padding: 10px 20px;
    border-radius: 6px;
}
"""

class OmniBootApp(Gtk.Window):
    def __init__(self):
        super().__init__(title=APP_TITLE)
        self.set_default_size(780, 780)
        self.set_position(Gtk.WindowPosition.CENTER)

        # Set app icon if available
        for icon_path in [
            "/usr/share/icons/hicolor/scalable/apps/omniboot-usb.svg",
            os.path.join(os.path.dirname(__file__), "omniboot-usb.svg")
        ]:
            if os.path.exists(icon_path):
                self.set_icon_from_file(icon_path)
                break

        # Apply CSS
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(CSS_DATA)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # State
        self.devices = []
        self.selected_device = None
        self.single_iso_info = None
        self.multi_iso_list = []  # list of info dicts
        self.worker_thread = None
        self.is_running = False

        self._build_ui()
        self.refresh_devices()

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(main_box)

        # 1. Header Bar
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.props.title = APP_TITLE
        header.props.subtitle = APP_SUBTITLE
        self.set_titlebar(header)

        # Scrolled content container
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        main_box.pack_start(scrolled, True, True, 0)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(14)
        content.set_margin_bottom(14)
        scrolled.add(content)

        # ==============================================================
        # CARD 1: Mode Selection (Ventoy Multi-ISO vs Single Direct Flash)
        # ==============================================================
        card1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card1.get_style_context().add_class("main-card")

        lbl1 = Gtk.Label(label="1. Choose Installation Mode")
        lbl1.set_xalign(0)
        lbl1.get_style_context().add_class("card-title")
        card1.pack_start(lbl1, False, False, 0)

        # Mode A: Ventoy Multi-ISO
        self.radio_multi = Gtk.RadioButton.new_with_label(None, "🌟 Multiple ISOs on One USB (Ventoy Multi-Boot)")
        self.radio_multi.get_style_context().add_class("mode-radio")
        self.radio_multi.connect("toggled", self.on_mode_changed)
        card1.pack_start(self.radio_multi, False, False, 0)

        lbl_multi_desc = Gtk.Label(
            label="     Installs the Ventoy bootloader. Allows copying multiple Linux & Windows ISOs onto the\n"
                  "     drive. Boot and choose from a menu. You can drag & drop more ISOs anytime without reformatting!"
        )
        lbl_multi_desc.set_xalign(0)
        lbl_multi_desc.get_style_context().add_class("card-subtitle")
        card1.pack_start(lbl_multi_desc, False, False, 0)

        # Mode B: Single ISO Direct Flash
        self.radio_single = Gtk.RadioButton.new_with_label_from_widget(
            self.radio_multi, "⚡ Single Operating System (Dedicated Direct Flash)"
        )
        self.radio_single.get_style_context().add_class("mode-radio")
        card1.pack_start(self.radio_single, False, False, 0)

        lbl_single_desc = Gtk.Label(
            label="     Directly flashes and creates a dedicated bootable installer for a single OS (Linux hybrid\n"
                  "     write or dedicated Windows UEFI installer)."
        )
        lbl_single_desc.set_xalign(0)
        lbl_single_desc.get_style_context().add_class("card-subtitle")
        card1.pack_start(lbl_single_desc, False, False, 0)

        content.pack_start(card1, False, False, 0)

        # ==============================================================
        # CARD 2: USB Drive Selection
        # ==============================================================
        card2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card2.get_style_context().add_class("main-card")

        lbl2 = Gtk.Label(label="2. Target USB Drive")
        lbl2.set_xalign(0)
        lbl2.get_style_context().add_class("card-title")
        card2.pack_start(lbl2, False, False, 0)

        dev_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        self.dev_combo = Gtk.ComboBoxText()
        self.dev_combo.set_hexpand(True)
        self.dev_combo.connect("changed", self.on_device_changed)
        dev_box.pack_start(self.dev_combo, True, True, 0)

        btn_refresh = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        btn_refresh.set_tooltip_text("Refresh connected USB devices")
        btn_refresh.connect("clicked", lambda w: self.refresh_devices())
        dev_box.pack_start(btn_refresh, False, False, 0)

        card2.pack_start(dev_box, False, False, 0)

        self.lbl_dev_info = Gtk.Label(label="")
        self.lbl_dev_info.set_xalign(0)
        self.lbl_dev_info.get_style_context().add_class("card-subtitle")
        card2.pack_start(self.lbl_dev_info, False, False, 0)

        content.pack_start(card2, False, False, 0)

        # ==============================================================
        # CARD 3: ISO Selection
        # ==============================================================
        card3 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card3.get_style_context().add_class("main-card")

        self.lbl_iso_title = Gtk.Label(label="3. Select Operating System ISO Image")
        self.lbl_iso_title.set_xalign(0)
        self.lbl_iso_title.get_style_context().add_class("card-title")
        card3.pack_start(self.lbl_iso_title, False, False, 0)

        # Single ISO View
        self.box_single_iso = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        btn_browse_single = Gtk.Button(label="📁 Choose ISO Image File...")
        btn_browse_single.connect("clicked", self.on_browse_single_iso)
        self.box_single_iso.pack_start(btn_browse_single, False, False, 0)

        self.lbl_single_iso_details = Gtk.Label(label="No ISO selected yet.")
        self.lbl_single_iso_details.set_xalign(0)
        self.lbl_single_iso_details.set_line_wrap(True)
        self.box_single_iso.pack_start(self.lbl_single_iso_details, False, False, 0)

        card3.pack_start(self.box_single_iso, False, False, 0)

        # Multi ISO View (Ventoy)
        self.box_multi_iso = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        multi_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_add_iso = Gtk.Button(label="➕ Add ISO File...")
        btn_add_iso.connect("clicked", self.on_add_multi_iso)
        multi_btn_box.pack_start(btn_add_iso, False, False, 0)

        btn_clear_iso = Gtk.Button(label="🗑️ Clear All")
        btn_clear_iso.connect("clicked", self.on_clear_multi_iso)
        multi_btn_box.pack_start(btn_clear_iso, False, False, 0)

        self.box_multi_iso.pack_start(multi_btn_box, False, False, 0)

        # Scrolled tree view for selected ISOs
        self.iso_store = Gtk.ListStore(str, str, str, str) # Filename, OS, Size, Path
        self.iso_tree = Gtk.TreeView(model=self.iso_store)
        self.iso_tree.set_size_request(-1, 130)

        col_name = Gtk.TreeViewColumn("File Name", Gtk.CellRendererText(), text=0)
        col_name.set_expand(True)
        self.iso_tree.append_column(col_name)

        col_os = Gtk.TreeViewColumn("Detected OS", Gtk.CellRendererText(), text=1)
        self.iso_tree.append_column(col_os)

        col_sz = Gtk.TreeViewColumn("Size", Gtk.CellRendererText(), text=2)
        self.iso_tree.append_column(col_sz)

        iso_scroll = Gtk.ScrolledWindow()
        iso_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        iso_scroll.set_size_request(-1, 120)
        iso_scroll.add(self.iso_tree)
        self.box_multi_iso.pack_start(iso_scroll, False, False, 0)

        self.lbl_multi_summary = Gtk.Label(label="0 ISOs selected (You can also install Ventoy now and copy ISOs later).")
        self.lbl_multi_summary.set_xalign(0)
        self.lbl_multi_summary.get_style_context().add_class("card-subtitle")
        self.box_multi_iso.pack_start(self.lbl_multi_summary, False, False, 0)

        card3.pack_start(self.box_multi_iso, False, False, 0)

        content.pack_start(card3, False, False, 0)

        # ==============================================================
        # CARD 4: Storage Pre-Flight Check (Capacity vs ISO Size)
        # ==============================================================
        card4 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card4.get_style_context().add_class("main-card")

        lbl4 = Gtk.Label(label="4. Storage Pre-Flight Analysis")
        lbl4.set_xalign(0)
        lbl4.get_style_context().add_class("card-title")
        card4.pack_start(lbl4, False, False, 0)

        storage_grid = Gtk.Grid()
        storage_grid.set_column_spacing(20)
        storage_grid.set_row_spacing(6)

        lbl_cap_t = Gtk.Label(label="<b>USB Total Capacity:</b>", use_markup=True, xalign=0)
        self.lbl_cap_val = Gtk.Label(label="--", xalign=0)
        storage_grid.attach(lbl_cap_t, 0, 0, 1, 1)
        storage_grid.attach(self.lbl_cap_val, 1, 0, 1, 1)

        lbl_req_t = Gtk.Label(label="<b>Required Space (ISO):</b>", use_markup=True, xalign=0)
        self.lbl_req_val = Gtk.Label(label="--", xalign=0)
        storage_grid.attach(lbl_req_t, 0, 1, 1, 1)
        storage_grid.attach(self.lbl_req_val, 1, 1, 1, 1)

        lbl_rem_t = Gtk.Label(label="<b>Estimated Free Space:</b>", use_markup=True, xalign=0)
        self.lbl_rem_val = Gtk.Label(label="--", xalign=0)
        storage_grid.attach(lbl_rem_t, 0, 2, 1, 1)
        storage_grid.attach(self.lbl_rem_val, 1, 2, 1, 1)

        card4.pack_start(storage_grid, False, False, 0)

        # Storage visual progress bar
        self.storage_bar = Gtk.ProgressBar()
        self.storage_bar.set_fraction(0.0)
        self.storage_bar.set_show_text(True)
        self.storage_bar.set_text("0% Used")
        card4.pack_start(self.storage_bar, False, False, 0)

        # Status badge label
        self.lbl_storage_badge = Gtk.Label(label="Please select a drive and ISO.")
        self.lbl_storage_badge.set_xalign(0)
        self.lbl_storage_badge.set_line_wrap(True)
        card4.pack_start(self.lbl_storage_badge, False, False, 0)

        content.pack_start(card4, False, False, 0)

        # ==============================================================
        # CARD 5: Action & Execution Progress
        # ==============================================================
        card5 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card5.get_style_context().add_class("main-card")

        self.btn_flash = Gtk.Button(label="🚀 Install Ventoy & Prepare USB")
        self.btn_flash.get_style_context().add_class("action-btn")
        self.btn_flash.get_style_context().add_class("suggested-action")
        self.btn_flash.connect("clicked", self.on_flash_clicked)
        card5.pack_start(self.btn_flash, False, False, 0)

        # Progress elements
        self.progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        self.main_progress = Gtk.ProgressBar()
        self.main_progress.set_show_text(True)
        self.main_progress.set_text("Ready")
        self.progress_box.pack_start(self.main_progress, False, False, 0)

        info_h_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        self.lbl_progress_status = Gtk.Label(label="Ready to start.", xalign=0)
        self.lbl_progress_status.set_hexpand(True)
        info_h_box.pack_start(self.lbl_progress_status, True, True, 0)

        self.lbl_speed_eta = Gtk.Label(label="", xalign=1)
        info_h_box.pack_start(self.lbl_speed_eta, False, False, 0)

        self.progress_box.pack_start(info_h_box, False, False, 0)
        card5.pack_start(self.progress_box, False, False, 0)

        content.pack_start(card5, False, False, 0)

        # Initial mode view update
        self.on_mode_changed(None)

    def refresh_devices(self):
        """Scan and populate connected USB storage devices."""
        self.dev_combo.remove_all()
        self.devices = get_storage_devices()

        if not self.devices:
            self.dev_combo.append_text("⚠️ No removable USB drives detected")
            self.dev_combo.set_active(0)
            self.lbl_dev_info.set_text("Please connect a USB flash drive and click Refresh.")
            self.selected_device = None
        else:
            for idx, d in enumerate(self.devices):
                entry_text = f"{d['model']} ({d['path']}) — {d['size_str']}"
                self.dev_combo.append_text(entry_text)
            self.dev_combo.set_active(0)

        self.update_storage_analysis()

    def on_device_changed(self, combo):
        active_idx = combo.get_active()
        if 0 <= active_idx < len(self.devices):
            self.selected_device = self.devices[active_idx]
            d = self.selected_device
            part_info = f"{len(d['partitions'])} partition(s)" if d['partitions'] else "Unpartitioned"
            self.lbl_dev_info.set_text(f"Device: {d['path']} | Size: {d['size_str']} | {part_info}")
        else:
            self.selected_device = None
            self.lbl_dev_info.set_text("")
        self.update_storage_analysis()

    def on_mode_changed(self, radio):
        is_multi = self.radio_multi.get_active()
        if is_multi:
            self.box_single_iso.hide()
            self.box_multi_iso.show_all()
            self.lbl_iso_title.set_text("3. Choose ISO Images (Ventoy Multi-Boot)")
            self.btn_flash.set_label("🚀 Install Ventoy & Copy ISOs")
        else:
            self.box_multi_iso.hide()
            self.box_single_iso.show_all()
            self.lbl_iso_title.set_text("3. Choose Operating System ISO Image")
            self.btn_flash.set_label("⚡ Flash Dedicated Single OS Installer")

        self.update_storage_analysis()

    def on_browse_single_iso(self, btn):
        dialog = Gtk.FileChooserDialog(
            title="Select ISO Image", parent=self,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK
        )
        filter_iso = Gtk.FileFilter()
        filter_iso.set_name("Disk Images (*.iso, *.img)")
        filter_iso.add_pattern("*.iso")
        filter_iso.add_pattern("*.img")
        dialog.add_filter(filter_iso)

        filter_all = Gtk.FileFilter()
        filter_all.set_name("All Files")
        filter_all.add_pattern("*")
        dialog.add_filter(filter_all)

        res = dialog.run()
        if res == Gtk.ResponseType.OK:
            filename = dialog.get_filename()
            dialog.destroy()
            info = inspect_iso(filename)
            self.single_iso_info = info
            icon = "🐧" if info['os_type'] == 'linux' else ("🪟" if info['os_type'] == 'windows' else "💿")
            text = (f"<b>{icon} {info['distro_name']}</b>\n"
                    f"File: {info['filename']}\n"
                    f"Size: {info['size_str']}")
            if info['os_type'] == 'windows':
                text += "\n<small><i>Windows ISO detected: OmniBoot will configure dedicated UEFI auto-boot setup.</i></small>"
            self.lbl_single_iso_details.set_markup(text)
            self.update_storage_analysis()
        else:
            dialog.destroy()

    def on_add_multi_iso(self, btn):
        dialog = Gtk.FileChooserDialog(
            title="Add ISO Image(s) to Ventoy", parent=self,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.set_select_multiple(True)
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK
        )
        filter_iso = Gtk.FileFilter()
        filter_iso.set_name("Disk Images (*.iso, *.img)")
        filter_iso.add_pattern("*.iso")
        filter_iso.add_pattern("*.img")
        dialog.add_filter(filter_iso)

        res = dialog.run()
        if res == Gtk.ResponseType.OK:
            paths = dialog.get_filenames()
            dialog.destroy()
            for path in paths:
                # Avoid duplicates
                if any(x['path'] == path for x in self.multi_iso_list):
                    continue
                info = inspect_iso(path)
                if info.get('valid'):
                    self.multi_iso_list.append(info)
                    icon = "🐧" if info['os_type'] == 'linux' else ("🪟" if info['os_type'] == 'windows' else "💿")
                    self.iso_store.append([
                        info['filename'],
                        f"{icon} {info['distro_name']}",
                        info['size_str'],
                        info['path']
                    ])
            self.update_multi_summary()
            self.update_storage_analysis()
        else:
            dialog.destroy()

    def on_clear_multi_iso(self, btn):
        self.multi_iso_list.clear()
        self.iso_store.clear()
        self.update_multi_summary()
        self.update_storage_analysis()

    def update_multi_summary(self):
        count = len(self.multi_iso_list)
        total_sz = sum(x['size_bytes'] for x in self.multi_iso_list)
        if count == 0:
            self.lbl_multi_summary.set_text("0 ISOs selected (You can also install Ventoy now and copy ISOs later).")
        else:
            self.lbl_multi_summary.set_text(f"{count} ISO(s) selected | Total ISO Size: {format_bytes(total_sz)}")

    def update_storage_analysis(self):
        """Recalculate drive capacity vs required ISO size and update UI badges."""
        is_multi = self.radio_multi.get_active()

        # Target drive
        if not self.selected_device:
            self.lbl_cap_val.set_text("No USB drive selected")
            self.lbl_req_val.set_text("--")
            self.lbl_rem_val.set_text("--")
            self.storage_bar.set_fraction(0.0)
            self.storage_bar.set_text("No Drive")
            self.lbl_storage_badge.set_text("Please insert a USB drive.")
            self.btn_flash.set_sensitive(False)
            return

        drive_bytes = self.selected_device['size_bytes']
        self.lbl_cap_val.set_text(f"{self.selected_device['size_str']} ({drive_bytes:,} bytes)")

        # Required bytes
        if is_multi:
            req_bytes = sum(x['size_bytes'] for x in self.multi_iso_list)
            # Add 100MB buffer for Ventoy EFI boot partition
            req_bytes_with_overhead = req_bytes + (100 * 1024 * 1024 if req_bytes > 0 else 0)
        else:
            if not self.single_iso_info:
                self.lbl_req_val.set_text("No ISO selected")
                self.lbl_rem_val.set_text("--")
                self.storage_bar.set_fraction(0.0)
                self.storage_bar.set_text("0%")
                self.lbl_storage_badge.set_text("Please select an operating system ISO file above.")
                self.btn_flash.set_sensitive(False)
                return
            req_bytes = self.single_iso_info['size_bytes']
            req_bytes_with_overhead = req_bytes

        self.lbl_req_val.set_text(f"{format_bytes(req_bytes)} ({req_bytes:,} bytes)")

        # Comparison
        if drive_bytes <= 0:
            self.lbl_rem_val.set_text("0 B")
            self.btn_flash.set_sensitive(False)
            return

        fraction = req_bytes_with_overhead / drive_bytes if drive_bytes > 0 else 0.0

        if req_bytes_with_overhead > drive_bytes:
            # Insufficient storage
            self.lbl_rem_val.set_markup("<span color='#dc2626'><b>Insufficient space!</b></span>")
            self.storage_bar.set_fraction(1.0)
            self.storage_bar.set_text(f"Exceeds capacity! ({fraction*100:.1f}%)")
            diff = req_bytes_with_overhead - drive_bytes
            self.lbl_storage_badge.set_markup(
                f"<span color='#dc2626'><b>❌ ERROR: USB Drive is too small!</b> ISO requires {format_bytes(req_bytes)}, "
                f"but USB drive only has {self.selected_device['size_str']}. (Short by {format_bytes(diff)})</span>"
            )
            self.btn_flash.set_sensitive(False)
        else:
            # Sufficient storage
            remaining = drive_bytes - req_bytes_with_overhead
            self.lbl_rem_val.set_text(f"{format_bytes(remaining)} free")
            self.storage_bar.set_fraction(min(1.0, max(0.0, fraction)))
            self.storage_bar.set_text(f"{fraction*100:.1f}% Used ({format_bytes(remaining)} Free)")

            if is_multi and req_bytes == 0:
                self.lbl_storage_badge.set_markup(
                    f"<span color='#059669'><b>✓ Ready:</b> Will install Ventoy bootloader on {self.selected_device['size_str']} drive. "
                    f"You can copy ISOs directly to it later.</span>"
                )
            else:
                self.lbl_storage_badge.set_markup(
                    f"<span color='#059669'><b>✓ Storage Check Passed:</b> Drive has ample storage. "
                    f"{format_bytes(remaining)} will remain free.</span>"
                )

            self.btn_flash.set_sensitive(True)

    def on_flash_clicked(self, btn):
        if not self.selected_device:
            return

        is_multi = self.radio_multi.get_active()
        dev_path = self.selected_device['path']
        dev_name = self.selected_device['model']
        dev_size = self.selected_device['size_str']

        # Construct Confirmation Message
        if is_multi:
            mode_str = "🌟 Ventoy Multi-Boot Installation"
            iso_count = len(self.multi_iso_list)
            iso_desc = f"{iso_count} ISO image(s) to copy immediately." if iso_count > 0 else "Bootloader only (ISOs can be added later)."
        else:
            mode_str = "⚡ Dedicated Single OS Flash"
            if not self.single_iso_info:
                return
            iso_desc = f"{self.single_iso_info['distro_name']} ({self.single_iso_info['filename']})"

        msg = (
            f"<b>⚠️ WARNING: ALL EXISTING DATA ON THIS DRIVE WILL BE PERMANENTLY ERASED!</b>\n\n"
            f"<b>Target Device:</b> {dev_name} (<code>{dev_path}</code>)\n"
            f"<b>Capacity:</b> {dev_size}\n"
            f"<b>Operation:</b> {mode_str}\n"
            f"<b>Contents:</b> {iso_desc}\n\n"
            f"Are you sure you want to format <code>{dev_path}</code> and proceed?"
        )

        confirm_dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.NONE,
            text="Confirm USB Drive Formatting"
        )
        confirm_dialog.format_secondary_markup(msg)
        confirm_dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        destruct_btn = confirm_dialog.add_button("Yes, Format & Flash Drive", Gtk.ResponseType.OK)
        destruct_btn.get_style_context().add_class("destructive-action")

        res = confirm_dialog.run()
        confirm_dialog.destroy()

        if res == Gtk.ResponseType.OK:
            self.start_operation()

    def set_ui_busy(self, busy):
        self.is_running = busy
        self.radio_multi.set_sensitive(not busy)
        self.radio_single.set_sensitive(not busy)
        self.dev_combo.set_sensitive(not busy)
        self.box_single_iso.set_sensitive(not busy)
        self.box_multi_iso.set_sensitive(not busy)
        self.btn_flash.set_sensitive(not busy)

    def start_operation(self):
        self.set_ui_busy(True)
        self.main_progress.set_fraction(0.0)
        self.main_progress.set_text("Starting...")
        self.lbl_progress_status.set_text("Authorizing elevated permissions (PolicyKit)...")
        self.lbl_speed_eta.set_text("")

        is_multi = self.radio_multi.get_active()
        dev_path = self.selected_device['path']

        # Determine backend script path
        candidates = [
            "/usr/lib/omniboot-usb/backend.py",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend.py")
        ]
        backend_script = candidates[0] if os.path.exists(candidates[0]) else candidates[1]

        # Build command with pkexec
        cmd = ["pkexec", "python3", backend_script]

        if is_multi:
            cmd.extend(["ventoy", "--device", dev_path])
            for iso in self.multi_iso_list:
                cmd.extend(["--iso", iso['path']])
        else:
            iso_info = self.single_iso_info
            if iso_info['os_type'] == 'windows':
                # Configure Windows auto-boot dedicated setup
                cmd.extend(["ventoy", "--device", dev_path, "--single-auto", iso_info['path'], "--iso", iso_info['path']])
            else:
                # Raw hybrid direct block flash
                cmd.extend(["flash", "--device", dev_path, "--iso", iso_info['path']])

        # Launch worker thread
        self.worker_thread = threading.Thread(target=self._run_backend_worker, args=(cmd,), daemon=True)
        self.worker_thread.start()

    def _run_backend_worker(self, cmd):
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            # Read stdout line by line
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    GLib.idle_add(self._handle_backend_event, data)
                except json.JSONDecodeError:
                    GLib.idle_add(self.lbl_progress_status.set_text, line)

            proc.wait()
            stderr_out = proc.stderr.read()

            if proc.returncode != 0:
                if proc.returncode in (126, 127):
                    err_msg = "Administrative authorization was cancelled."
                else:
                    err_msg = stderr_out.strip() or f"Process exited with error code {proc.returncode}"
                GLib.idle_add(self._handle_backend_error, err_msg)

        except Exception as e:
            GLib.idle_add(self._handle_backend_error, str(e))

    def _handle_backend_event(self, data):
        msg_type = data.get("type")

        if msg_type == "log":
            self.lbl_progress_status.set_text(data.get("message", ""))

        elif msg_type == "progress":
            pct = data.get("percent", 0.0)
            self.main_progress.set_fraction(pct / 100.0)
            self.main_progress.set_text(f"{pct:.1f}%")
            self.lbl_progress_status.set_text(data.get("status", ""))
            speed = data.get("speed", "")
            eta = data.get("eta", "")
            self.lbl_speed_eta.set_text(f"⚡ {speed} | ⏳ ETA: {eta}" if (speed and eta) else speed)

        elif msg_type == "sync":
            self.main_progress.set_fraction(0.99)
            self.main_progress.set_text("Syncing...")
            self.lbl_progress_status.set_text(data.get("message", "Syncing to USB..."))
            self.lbl_speed_eta.set_text("Flushing cache...")

        elif msg_type == "success":
            self.main_progress.set_fraction(1.0)
            self.main_progress.set_text("100% Complete")
            self.lbl_progress_status.set_text(data.get("message", "Operation finished successfully!"))
            self.lbl_speed_eta.set_text("Done!")
            self.set_ui_busy(False)

            dialog = Gtk.MessageDialog(
                parent=self,
                flags=Gtk.DialogFlags.MODAL,
                type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Bootable USB Created Successfully!"
            )
            dialog.format_secondary_markup(
                f"<b>{data.get('message', 'Completed!')}</b>\n\n"
                f"Your USB drive is now ready to boot.\n"
                f"Plug it into your PC and press <b>F12, F11, or Del</b> at startup to boot."
            )
            dialog.run()
            dialog.destroy()

        elif msg_type == "error":
            self._handle_backend_error(data.get("message", "An unexpected error occurred."))

        return False

    def _handle_backend_error(self, err_msg):
        self.set_ui_busy(False)
        self.main_progress.set_fraction(0.0)
        self.main_progress.set_text("Failed")
        self.lbl_progress_status.set_text(f"Error: {err_msg}")
        self.lbl_speed_eta.set_text("")

        dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Operation Failed"
        )
        dialog.format_secondary_text(err_msg)
        dialog.run()
        dialog.destroy()
        return False

def main():
    app = OmniBootApp()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    # Ensure correct initial state for mode widgets
    app.on_mode_changed(None)
    Gtk.main()

if __name__ == '__main__':
    main()
