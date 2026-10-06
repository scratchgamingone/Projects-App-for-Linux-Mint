"""
Dialog windows for USBGuard Manager.
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

class AddRuleDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(
            title="Add Trusted USB Device Rule",
            transient_for=parent,
            flags=0
        )
        self.set_modal(True)
        self.set_default_size(440, 320)
        self.set_border_width(12)

        self.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        add_btn = self.add_button("Add Rule", Gtk.ResponseType.OK)
        add_btn.get_style_context().add_class("suggested-action")

        box = self.get_content_area()
        box.set_spacing(10)

        desc = Gtk.Label()
        desc.set_markup("<b>Create a permanent USB authorization rule</b>\nYou can whitelist a device by its Vendor:Product ID and optional serial number.")
        desc.set_line_wrap(True)
        desc.set_xalign(0)
        box.pack_start(desc, False, False, 4)

        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(10)
        grid.set_border_width(6)
        box.pack_start(grid, True, True, 0)

        # Rule Action
        lbl_target = Gtk.Label(label="Action:")
        lbl_target.set_xalign(1)
        grid.attach(lbl_target, 0, 0, 1, 1)

        self.combo_target = Gtk.ComboBoxText()
        self.combo_target.append("allow", "Allow (Trust Device)")
        self.combo_target.append("block", "Block (Reject Device)")
        self.combo_target.set_active(0)
        grid.attach(self.combo_target, 1, 0, 1, 1)

        # Device ID
        lbl_id = Gtk.Label(label="Device ID (VID:PID):")
        lbl_id.set_xalign(1)
        grid.attach(lbl_id, 0, 1, 1, 1)

        self.entry_id = Gtk.Entry()
        self.entry_id.set_placeholder_text("e.g. 0781:5583")
        grid.attach(self.entry_id, 1, 1, 1, 1)

        # Friendly Name
        lbl_name = Gtk.Label(label="Device Name / Label:")
        lbl_name.set_xalign(1)
        grid.attach(lbl_name, 0, 2, 1, 1)

        self.entry_name = Gtk.Entry()
        self.entry_name.set_placeholder_text("e.g. My Kingston Flash Drive")
        grid.attach(self.entry_name, 1, 2, 1, 1)

        # Serial
        lbl_serial = Gtk.Label(label="Serial Number (Optional):")
        lbl_serial.set_xalign(1)
        grid.attach(lbl_serial, 0, 3, 1, 1)

        self.entry_serial = Gtk.Entry()
        self.entry_serial.set_placeholder_text("Leave blank to match any serial")
        grid.attach(self.entry_serial, 1, 3, 1, 1)

        self.show_all()

    def get_rule_data(self):
        target = self.combo_target.get_active_id() or "allow"
        dev_id = self.entry_id.get_text().strip().lower()
        name = self.entry_name.get_text().strip()
        serial = self.entry_serial.get_text().strip()
        return target, dev_id, name, serial


def show_confirm_baseline_dialog(parent) -> bool:
    dialog = Gtk.MessageDialog(
        transient_for=parent,
        flags=0,
        message_type=Gtk.MessageType.QUESTION,
        buttons=Gtk.ButtonsType.NONE,
        text="Trust All Currently Connected Devices?"
    )
    dialog.format_secondary_text(
        "This will generate permanent allow rules for all currently connected USB devices "
        "(including your keyboard, mouse, webcams, and USB hubs) and add them to the trusted whitelist.\n\n"
        "This is strongly recommended during initial setup so your existing peripherals continue to work without interruption."
    )
    dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
    trust_btn = dialog.add_button("Trust All Connected", Gtk.ResponseType.OK)
    trust_btn.get_style_context().add_class("suggested-action")

    resp = dialog.run()
    dialog.destroy()
    return resp == Gtk.ResponseType.OK


def show_about_dialog(parent):
    about = Gtk.AboutDialog(transient_for=parent, modal=True)
    about.set_program_name("USB Guard")
    about.set_version("1.0.0")
    about.set_comments("USB Device Authorization & BadUSB Protection for Linux")
    about.set_website("https://usbguard.github.io/")
    about.set_website_label("USBGuard Project Website")
    about.set_authors(["Antigravity"])
    about.set_logo_icon_name("usbguard-manager")
    about.run()
    about.destroy()
