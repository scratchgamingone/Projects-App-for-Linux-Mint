"""
Interactive breadcrumbs navigation widget for StatDisk.
Displays current path as clickable button segments.
"""

import os
from typing import Callable, Optional, List
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

from statdisk.tree_model import FileNode


class BreadcrumbsBar(Gtk.Box):
    """Breadcrumb bar allowing instant navigation to any parent directory."""

    def __init__(self, on_navigate: Callable[[FileNode], None]):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.on_navigate = on_navigate
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(4)
        self.set_margin_bottom(4)

        # Scrolled container in case of very deep paths
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.scrolled.set_shadow_type(Gtk.ShadowType.NONE)

        self.inner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self.scrolled.add(self.inner_box)
        self.pack_start(self.scrolled, True, True, 0)

    def set_current_node(self, node: Optional[FileNode]) -> None:
        """Update breadcrumbs based on the currently displayed node."""
        for child in self.inner_box.get_children():
            self.inner_box.remove(child)

        if not node:
            return

        ancestors = node.get_ancestors()
        for i, ancestor in enumerate(ancestors):
            is_last = (i == len(ancestors) - 1)
            btn = Gtk.Button()
            btn.get_style_context().add_class('breadcrumb-btn')
            if is_last:
                btn.get_style_context().add_class('breadcrumb-active')

            display_name = ancestor.name if ancestor.name else "/"
            btn.set_label(display_name)
            btn.set_tooltip_text(ancestor.path)

            if not is_last:
                btn.connect('clicked', lambda b, target=ancestor: self.on_navigate(target))

            self.inner_box.pack_start(btn, False, False, 0)

            if not is_last:
                sep = Gtk.Label(label="›")
                sep.get_style_context().add_class('breadcrumb-sep')
                self.inner_box.pack_start(sep, False, False, 2)

        self.show_all()
        # Scroll to end
        adj = self.scrolled.get_hadjustment()
        GLib = gi.repository.GLib
        GLib.idle_add(lambda: adj.set_value(adj.get_upper() - adj.get_page_size()))
