"""
Interactive repository file and folder tree widget with filtering and icon support.
"""

import os
from pathlib import Path
from typing import Optional, Callable

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, Pango

from github_project_installer.core.git_inspector import FileNode, format_bytes


def get_icon_name(node: FileNode) -> str:
    """Returns standard FreeDesktop icon name based on file extension and type."""
    if node.is_dir:
        return "folder"

    ext = Path(node.name).suffix.lower()
    name_lower = node.name.lower()

    if ext in [".py", ".pyw"]:
        return "text-x-python"
    elif ext in [".sh", ".bash", ".zsh"]:
        return "application-x-executable"
    elif ext in [".js", ".jsx", ".ts", ".tsx"]:
        return "text-x-javascript"
    elif ext in [".c", ".h", ".cpp", ".hpp", ".cc"]:
        return "text-x-c"
    elif ext in [".rs"]:
        return "text-x-rust"
    elif ext in [".go"]:
        return "text-x-generic"
    elif ext in [".html", ".htm"]:
        return "text-html"
    elif ext in [".css", ".scss", ".sass"]:
        return "text-css"
    elif ext in [".json", ".yaml", ".yml", ".toml", ".ini", ".conf"]:
        return "text-x-script"
    elif ext in [".md", ".markdown", ".rst", ".txt"]:
        return "text-x-generic"
    elif ext in [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"]:
        return "image-x-generic"
    elif ext in [".zip", ".tar", ".gz", ".bz2", ".xz", ".deb"]:
        return "package-x-generic"
    elif name_lower in ["dockerfile", "makefile", "cmakelists.txt"]:
        return "text-x-script"

    return "text-x-generic"


class RepoTreeWidget(Gtk.Box):
    """File and folder tree viewer with search filtering."""

    def __init__(self, on_file_selected: Callable[[str, str], None]):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.on_file_selected = on_file_selected
        self.root_node: Optional[FileNode] = None

        # 1. Filter / Search Header
        filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        filter_box.set_margin_top(4)
        filter_box.set_margin_bottom(4)
        filter_box.set_margin_start(4)
        filter_box.set_margin_end(4)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Filter files...")
        self.search_entry.connect("search-changed", self._on_search_changed)
        filter_box.pack_start(self.search_entry, True, True, 0)

        # Expand / Collapse buttons
        btn_expand = Gtk.Button()
        btn_expand.set_tooltip_text("Expand All")
        btn_expand.set_image(Gtk.Image.new_from_icon_name("view-fullscreen-symbolic", Gtk.IconSize.BUTTON))
        btn_expand.connect("clicked", lambda b: self.tree_view.expand_all())
        filter_box.pack_start(btn_expand, False, False, 0)

        btn_collapse = Gtk.Button()
        btn_collapse.set_tooltip_text("Collapse All")
        btn_collapse.set_image(Gtk.Image.new_from_icon_name("view-restore-symbolic", Gtk.IconSize.BUTTON))
        btn_collapse.connect("clicked", lambda b: self.tree_view.collapse_all())
        filter_box.pack_start(btn_collapse, False, False, 0)

        self.pack_start(filter_box, False, False, 0)

        # 2. TreeStore Model:
        # Col 0: Icon Name (str)
        # Col 1: Display Name (str)
        # Col 2: Size Text (str)
        # Col 3: Absolute Path (str)
        # Col 4: Relative Path (str)
        # Col 5: Is Directory (bool)
        self.store = Gtk.TreeStore(str, str, str, str, str, bool)

        # TreeModelFilter for search
        self.filter_model = self.store.filter_new()
        self.filter_model.set_visible_func(self._filter_func)

        # TreeView
        self.tree_view = Gtk.TreeView(model=self.filter_model)
        self.tree_view.get_style_context().add_class("file-tree")
        self.tree_view.set_headers_visible(True)
        self.tree_view.set_enable_search(False)

        # Name Column (Icon + Text)
        col_name = Gtk.TreeViewColumn("Name")
        renderer_icon = Gtk.CellRendererPixbuf()
        col_name.pack_start(renderer_icon, False)
        col_name.add_attribute(renderer_icon, "icon-name", 0)

        renderer_text = Gtk.CellRendererText()
        renderer_text.set_property("ellipsize", Pango.EllipsizeMode.END)
        col_name.pack_start(renderer_text, True)
        col_name.add_attribute(renderer_text, "text", 1)
        col_name.set_expand(True)
        self.tree_view.append_column(col_name)

        # Size Column
        col_size = Gtk.TreeViewColumn("Size")
        renderer_size = Gtk.CellRendererText()
        renderer_size.set_property("xalign", 1.0)
        renderer_size.set_property("foreground", "#94a3b8")
        col_size.pack_start(renderer_size, False)
        col_size.add_attribute(renderer_size, "text", 2)
        col_size.set_min_width(70)
        self.tree_view.append_column(col_size)

        # Selection handler
        selection = self.tree_view.get_selection()
        selection.set_mode(Gtk.SelectionMode.SINGLE)
        selection.connect("changed", self._on_selection_changed)

        # Double click activates folder expansion or opens file
        self.tree_view.connect("row-activated", self._on_row_activated)

        # Scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self.tree_view)
        self.pack_start(scrolled, True, True, 0)

    def populate(self, root_node: FileNode):
        """Populates the tree store with nodes from root_node."""
        self.root_node = root_node
        self.store.clear()
        if not root_node:
            return

        def add_node(parent_iter, node: FileNode):
            icon = get_icon_name(node)
            size_str = "" if node.is_dir else format_bytes(node.size)
            current_iter = self.store.append(
                parent_iter,
                [icon, node.name, size_str, node.abs_path, node.rel_path, node.is_dir],
            )
            for child in node.children:
                add_node(current_iter, child)

        for child in root_node.children:
            add_node(None, child)

        # Auto-expand top level
        self.tree_view.expand_row(Gtk.TreePath.new_first(), False)

    def _filter_func(self, model, iter, data):
        query = self.search_entry.get_text().strip().lower()
        if not query:
            return True

        name = model.get_value(iter, 1) or ""
        rel = model.get_value(iter, 4) or ""
        is_dir = model.get_value(iter, 5)

        if query in name.lower() or query in rel.lower():
            return True

        # If directory has matching children, show directory
        if is_dir and model.iter_has_child(iter):
            child_iter = model.iter_children(iter)
            while child_iter:
                if self._filter_func(model, child_iter, data):
                    return True
                child_iter = model.iter_next(child_iter)

        return False

    def _on_search_changed(self, entry):
        self.filter_model.refilter()
        if entry.get_text().strip():
            self.tree_view.expand_all()

    def _on_selection_changed(self, selection):
        model, iter = selection.get_selected()
        if iter:
            is_dir = model.get_value(iter, 5)
            if not is_dir:
                abs_path = model.get_value(iter, 3)
                rel_path = model.get_value(iter, 4)
                if abs_path and self.on_file_selected:
                    self.on_file_selected(abs_path, rel_path)

    def _on_row_activated(self, tree_view, path, column):
        iter = self.filter_model.get_iter(path)
        if iter:
            is_dir = self.filter_model.get_value(iter, 5)
            if is_dir:
                if tree_view.row_expanded(path):
                    tree_view.collapse_row(path)
                else:
                    tree_view.expand_row(path, False)
            else:
                abs_path = self.filter_model.get_value(iter, 3)
                rel_path = self.filter_model.get_value(iter, 4)
                if abs_path and self.on_file_selected:
                    self.on_file_selected(abs_path, rel_path)
