import threading
from typing import List

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Pango

from .cleaner import CleanTarget, get_all_cleaners, format_size

class CleanerRow(Gtk.ListBoxRow):
    def __init__(self, target: CleanTarget, on_toggle_callback):
        super().__init__()
        self.target = target
        self.on_toggle_callback = on_toggle_callback

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_border_width(12)

        # Checkbox
        self.check = Gtk.CheckButton()
        self.check.set_active(self.target.enabled)
        self.check.connect("toggled", self._on_toggled)
        box.pack_start(self.check, False, False, 0)

        # Info Box (Title + Description)
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        
        # Name row with optional Root badge
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.label_name = Gtk.Label(xalign=0)
        self.label_name.set_markup(f"<b>{self.target.name}</b>")
        title_box.pack_start(self.label_name, False, False, 0)

        if self.target.requires_root:
            badge = Gtk.Label()
            badge.set_markup("<span size='small' foreground='#ffffff' background='#e06c75'><b> ADMIN </b></span>")
            title_box.pack_start(badge, False, False, 0)

        info_box.pack_start(title_box, False, False, 0)

        self.label_desc = Gtk.Label(label=self.target.description, xalign=0)
        self.label_desc.get_style_context().add_class("dim-label")
        self.label_desc.set_ellipsize(Pango.EllipsizeMode.END)
        info_box.pack_start(self.label_desc, False, False, 0)

        box.pack_start(info_box, True, True, 0)

        # Size Label
        self.label_size = Gtk.Label(label=format_size(self.target.size_bytes), xalign=1)
        self.label_size.get_style_context().add_class("size-label")
        box.pack_end(self.label_size, False, False, 0)

        self.add(box)
        self.show_all()

    def _on_toggled(self, button):
        self.target.enabled = button.get_active()
        if self.on_toggle_callback:
            self.on_toggle_callback()

    def update_display(self):
        self.check.set_sensitive(self.target.size_bytes > 0)
        if self.target.size_bytes == 0:
            self.check.set_active(False)
            self.target.enabled = False
        self.label_size.set_text(format_size(self.target.size_bytes))


class MainWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="MintSweep")
        self.set_default_size(650, 480)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.cleaners: List[CleanTarget] = get_all_cleaners()
        self.rows: List[CleanerRow] = []

        # Setup HeaderBar
        self.headerbar = Gtk.HeaderBar()
        self.headerbar.set_show_close_button(True)
        self.headerbar.set_title("MintSweep")
        self.headerbar.set_subtitle("System & Cache Cleaner")
        self.set_titlebar(self.headerbar)

        # Scan Button
        self.btn_scan = Gtk.Button(label="Scan")
        self.btn_scan.get_style_context().add_class("suggested-action")
        self.btn_scan.connect("clicked", self.on_scan_clicked)
        self.headerbar.pack_start(self.btn_scan)

        # Clean Button
        self.btn_clean = Gtk.Button(label="Clean Selected")
        self.btn_clean.get_style_context().add_class("destructive-action")
        self.btn_clean.set_sensitive(False)
        self.btn_clean.connect("clicked", self.on_clean_clicked)
        self.headerbar.pack_end(self.btn_clean)

        # Main Layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(main_box)

        # Top Summary Card
        self.summary_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.summary_box.set_border_width(18)
        
        self.total_size_label = Gtk.Label()
        self.total_size_label.set_markup("<span size='xx-large' weight='bold'>0 B</span>")
        self.summary_box.pack_start(self.total_size_label, False, False, 0)

        self.summary_sub_label = Gtk.Label(label="Press 'Scan' to analyze reclaimable disk space.")
        self.summary_sub_label.get_style_context().add_class("dim-label")
        self.summary_box.pack_start(self.summary_sub_label, False, False, 0)

        main_box.pack_start(self.summary_box, False, False, 0)
        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        # Scrolled List Box
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)

        for target in self.cleaners:
            row = CleanerRow(target, self.recalculate_totals)
            self.rows.append(row)
            self.listbox.add(row)

        scrolled.add(self.listbox)
        main_box.pack_start(scrolled, True, True, 0)

        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        # Bottom Status Bar
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        status_box.set_border_width(8)

        self.spinner = Gtk.Spinner()
        status_box.pack_start(self.spinner, False, False, 4)

        self.status_label = Gtk.Label(label="Ready", xalign=0)
        status_box.pack_start(self.status_label, True, True, 0)

        main_box.pack_start(status_box, False, False, 0)

        # Automatically start initial scan
        GLib.idle_add(self.start_scan)

    def set_busy(self, is_busy: bool, message: str = ""):
        self.btn_scan.set_sensitive(not is_busy)
        self.btn_clean.set_sensitive((not is_busy) and (self.get_selected_reclaimable() > 0))
        if is_busy:
            self.spinner.start()
            self.spinner.show()
        else:
            self.spinner.stop()
            self.spinner.hide()
        if message:
            self.status_label.set_text(message)

    def get_selected_reclaimable(self) -> int:
        return sum(c.size_bytes for c in self.cleaners if c.enabled)

    def recalculate_totals(self):
        total_selected = self.get_selected_reclaimable()
        self.total_size_label.set_markup(f"<span size='xx-large' weight='bold'>{format_size(total_selected)}</span>")
        if total_selected > 0:
            self.summary_sub_label.set_text("Reclaimable disk space selected for cleaning.")
            self.btn_clean.set_sensitive(True)
        else:
            self.summary_sub_label.set_text("No items selected or no reclaimable space found.")
            self.btn_clean.set_sensitive(False)

    def on_scan_clicked(self, button):
        self.start_scan()

    def start_scan(self):
        self.set_busy(True, "Scanning system caches and junk files...")

        def worker():
            for target in self.cleaners:
                GLib.idle_add(self.status_label.set_text, f"Scanning {target.name}...")
                target.scan()

            def finish():
                for row in self.rows:
                    row.update_display()
                self.recalculate_totals()
                self.set_busy(False, "Scan complete.")

            GLib.idle_add(finish)

        threading.Thread(target=worker, daemon=True).start()

    def on_clean_clicked(self, button):
        selected_targets = [c for c in self.cleaners if c.enabled and c.size_bytes > 0]
        if not selected_targets:
            return

        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text="Clean Selected Items?"
        )
        total_str = format_size(self.get_selected_reclaimable())
        dialog.format_secondary_text(
            f"This will free approximately {total_str} of disk space.\n"
            "System items may prompt for your administrator password."
        )
        response = dialog.run()
        dialog.destroy()

        if response != Gtk.ResponseType.OK:
            return

        self.start_clean(selected_targets)

    def start_clean(self, targets: List[CleanTarget]):
        self.set_busy(True, "Cleaning in progress...")

        def worker():
            total_freed = 0
            errors = []
            for target in targets:
                GLib.idle_add(self.status_label.set_text, f"Cleaning {target.name}...")
                freed, err = target.clean()
                total_freed += freed
                if err:
                    errors.append(f"{target.name}: {err}")
                # Re-scan cleaned target
                target.scan()

            def finish():
                for row in self.rows:
                    row.update_display()
                self.recalculate_totals()
                msg = f"Cleaned successfully! Freed {format_size(total_freed)}."
                if errors:
                    msg += f" ({len(errors)} warnings)"
                self.set_busy(False, msg)

            GLib.idle_add(finish)

        threading.Thread(target=worker, daemon=True).start()
