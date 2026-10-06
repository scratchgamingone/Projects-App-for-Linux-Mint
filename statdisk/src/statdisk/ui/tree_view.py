"""
Organized hierarchical and tabular item view for StatDisk.
Provides sortable columns, visual percentage progress bar,
category filters, search filter, and file actions.
"""

import os
import subprocess
from typing import Optional, Callable, List
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, Pango

from statdisk.tree_model import FileNode, format_bytes


class StorageTreeView(Gtk.Box):
    """File and directory browser table with progress bars and search."""

    def __init__(self, on_navigate: Callable[[FileNode], None]):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.on_navigate = on_navigate
        self.current_node: Optional[FileNode] = None
        self.filter_category: str = 'All'
        self.filter_text: str = ''

        # Top filter bar
        filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        filter_box.set_margin_start(6)
        filter_box.set_margin_end(6)
        filter_box.set_margin_top(4)

        # Search Entry
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Filter current folder by name...")
        self.search_entry.connect('search-changed', self._on_search_changed)
        filter_box.pack_start(self.search_entry, True, True, 0)

        # Category Filter Dropdown
        self.combo_filter = Gtk.ComboBoxText()
        categories = ['All Items', 'Folders Only', 'Files Only', 'Datasets & Databases',
                      'Videos & Audio', 'Archives', 'Code & Config', 'Large Files (>100MB)']
        for cat in categories:
            self.combo_filter.append_text(cat)
        self.combo_filter.set_active(0)
        self.combo_filter.connect('changed', self._on_combo_changed)
        filter_box.pack_start(self.combo_filter, False, False, 0)

        self.pack_start(filter_box, False, False, 0)

        # Scrolled window
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.pack_start(self.scrolled, True, True, 0)

        # TreeStore / ListStore:
        # Col 0: icon_name (str)
        # Col 1: name (str)
        # Col 2: human_size (str)
        # Col 3: pct_float (int 0..100 for Progress Cell)
        # Col 4: pct_str (str)
        # Col 5: items_str (str)
        # Col 6: category (str)
        # Col 7: modified_str (str)
        # Col 8: raw_size (int64 for sorting)
        # Col 9: node (object)
        self.store = Gtk.ListStore(str, str, str, int, str, str, str, str, int, object)

        # TreeView
        self.tree_view = Gtk.TreeView(model=self.store)
        self.tree_view.set_rules_hint(True)
        self.tree_view.connect('row-activated', self._on_row_activated)
        self.tree_view.connect('button-press-event', self._on_button_press)

        self._setup_columns()
        self.scrolled.add(self.tree_view)

    def _setup_columns(self) -> None:
        # 1. Name Column (with Icon)
        col_name = Gtk.TreeViewColumn("Name")
        col_name.set_resizable(True)
        col_name.set_min_width(220)
        col_name.set_sort_column_id(1)

        rend_icon = Gtk.CellRendererPixbuf()
        col_name.pack_start(rend_icon, False)
        col_name.add_attribute(rend_icon, "icon_name", 0)

        rend_name = Gtk.CellRendererText()
        rend_name.set_property("ellipsize", Pango.EllipsizeMode.END)
        col_name.pack_start(rend_name, True)
        col_name.add_attribute(rend_name, "text", 1)
        self.tree_view.append_column(col_name)

        # 2. Size Column
        rend_size = Gtk.CellRendererText()
        rend_size.set_property("xalign", 1.0)
        col_size = Gtk.TreeViewColumn("Size", rend_size, text=2)
        col_size.set_sort_column_id(8)
        col_size.set_min_width(90)
        col_size.set_resizable(True)
        self.tree_view.append_column(col_size)

        # 3. Usage % Bar Column
        rend_progress = Gtk.CellRendererProgress()
        col_bar = Gtk.TreeViewColumn("Usage %", rend_progress, value=3, text=4)
        col_bar.set_sort_column_id(3)
        col_bar.set_min_width(120)
        col_bar.set_resizable(True)
        self.tree_view.append_column(col_bar)

        # 4. Items / Sub-items Column
        rend_items = Gtk.CellRendererText()
        col_items = Gtk.TreeViewColumn("Content", rend_items, text=5)
        col_items.set_sort_column_id(5)
        col_items.set_min_width(100)
        col_items.set_resizable(True)
        self.tree_view.append_column(col_items)

        # 5. Category Column
        rend_cat = Gtk.CellRendererText()
        col_cat = Gtk.TreeViewColumn("Type", rend_cat, text=6)
        col_cat.set_sort_column_id(6)
        col_cat.set_min_width(90)
        col_cat.set_resizable(True)
        self.tree_view.append_column(col_cat)

        # 6. Modified Date Column
        rend_mtime = Gtk.CellRendererText()
        col_mtime = Gtk.TreeViewColumn("Modified", rend_mtime, text=7)
        col_mtime.set_sort_column_id(7)
        col_mtime.set_min_width(140)
        col_mtime.set_resizable(True)
        self.tree_view.append_column(col_mtime)

        # Default sort by size descending
        self.store.set_sort_column_id(8, Gtk.SortType.DESCENDING)

    def set_node(self, node: Optional[FileNode]) -> None:
        """Display children of the given node."""
        self.current_node = node
        self.refresh()

    def refresh(self) -> None:
        self.store.clear()
        if not self.current_node:
            return

        tot_size = float(self.current_node.size) if self.current_node.size > 0 else 1.0
        query = self.filter_text.lower()
        active_cat = self.combo_filter.get_active_text() or 'All Items'

        for child in self.current_node.children:
            # Filter by text search
            if query and query not in child.name.lower():
                continue

            # Filter by category
            if active_cat == 'Folders Only' and not child.is_dir:
                continue
            elif active_cat == 'Files Only' and child.is_dir:
                continue
            elif active_cat == 'Datasets & Databases' and child.category not in ('Dataset', 'Database'):
                continue
            elif active_cat == 'Videos & Audio' and child.category not in ('Video', 'Audio'):
                continue
            elif active_cat == 'Archives' and child.category != 'Archive':
                continue
            elif active_cat == 'Code & Config' and child.category not in ('Code', 'Config'):
                continue
            elif active_cat == 'Large Files (>100MB)' and child.size < 100 * 1024 * 1024:
                continue

            # Icon
            if child.is_dir:
                icon = "folder"
            elif child.category == 'Video':
                icon = "video-x-generic"
            elif child.category == 'Audio':
                icon = "audio-x-generic"
            elif child.category == 'Image':
                icon = "image-x-generic"
            elif child.category in ('Dataset', 'Database'):
                icon = "x-office-spreadsheet"
            elif child.category == 'Archive':
                icon = "package-x-generic"
            elif child.category == 'Code':
                icon = "text-x-script"
            else:
                icon = "text-x-generic"

            pct_val = (child.size / tot_size) * 100.0
            pct_int = int(min(100, max(0, round(pct_val))))
            pct_str = f"{pct_val:.1f}%"

            if child.is_dir:
                items_str = f"{child.file_count:,} files"
            else:
                items_str = child.extension or "[file]"

            self.store.append([
                icon,
                child.name,
                child.human_size,
                pct_int,
                pct_str,
                items_str,
                child.category,
                child.formatted_mtime,
                child.size,
                child
            ])

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        self.filter_text = entry.get_text()
        self.refresh()

    def _on_combo_changed(self, combo: Gtk.ComboBoxText) -> None:
        self.refresh()

    def _on_row_activated(self, tree: Gtk.TreeView, path: Gtk.TreePath, column: Gtk.TreeViewColumn) -> None:
        tree_iter = self.store.get_iter(path)
        if not tree_iter:
            return
        node: FileNode = self.store.get_value(tree_iter, 9)
        if node.is_dir:
            self.on_navigate(node)
        else:
            subprocess.Popen(['xdg-open', node.path])

    def _on_button_press(self, tree: Gtk.TreeView, event: Gdk.EventButton) -> bool:
        if event.button == 3:  # Right click
            pth = tree.get_path_at_pos(int(event.x), int(event.y))
            if pth:
                path, col, _, _ = pth
                tree_iter = self.store.get_iter(path)
                node: FileNode = self.store.get_value(tree_iter, 9)
                self._show_context_menu(node, event)
                return True
        return False

    def _show_context_menu(self, node: FileNode, event: Gdk.EventButton) -> None:
        menu = Gtk.Menu()
        item_open = Gtk.MenuItem(label=f"Open {'Folder' if node.is_dir else 'File'}")
        item_open.connect('activate', lambda _: subprocess.Popen(['xdg-open', node.path]))
        menu.append(item_open)

        item_fm = Gtk.MenuItem(label="Open Containing Folder")
        target_dir = node.path if node.is_dir else os.path.dirname(node.path)
        item_fm.connect('activate', lambda _: subprocess.Popen(['xdg-open', target_dir]))
        menu.append(item_fm)

        item_copy = Gtk.MenuItem(label="Copy Path")
        def copy_path(_):
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(node.path, -1)
        item_copy.connect('activate', copy_path)
        menu.append(item_copy)

        menu.append(Gtk.SeparatorMenuItem())

        item_trash = Gtk.MenuItem(label="Move to Trash")
        def trash_item(_):
            dialog = Gtk.MessageDialog(
                transient_for=self.get_toplevel(),
                flags=Gtk.DialogFlags.MODAL,
                type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK_CANCEL,
                message_format=f"Move '{node.name}' to Trash?"
            )
            dialog.format_secondary_text(f"Path: {node.path}\nSize: {node.human_size}")
            res = dialog.run()
            dialog.destroy()
            if res == Gtk.ResponseType.OK:
                subprocess.Popen(['gio', 'trash', node.path])
        item_trash.connect('activate', trash_item)
        menu.append(item_trash)

        menu.show_all()
        menu.popup_at_pointer(event)
