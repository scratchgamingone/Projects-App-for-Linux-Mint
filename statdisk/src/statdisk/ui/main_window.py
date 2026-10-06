"""
Main Application Window for StatDisk.
Harmonizes SquirrelDisk-inspired visual navigation with rigorous statistical modeling.
"""

import os
import subprocess
from typing import Optional
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

from statdisk.tree_model import FileNode, format_bytes
from statdisk.scanner import DirectoryScanner, ScanStats
from statdisk.stats_engine import StatsEngine, StatisticalReport
from statdisk.ui.breadcrumbs import BreadcrumbsBar
from statdisk.ui.sunburst_view import SunburstView
from statdisk.ui.treemap_view import TreemapView
from statdisk.ui.tree_view import StorageTreeView
from statdisk.ui.stats_panel import StatsPanel
from statdisk.ui.export_dialog import ExportDialog


class MainWindow(Gtk.ApplicationWindow):
    """Main StatDisk application window."""

    def __init__(self, application: Gtk.Application):
        super().__init__(application=application, title="StatDisk - Storage & Statistical Analyzer")
        self.set_default_size(1180, 780)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.root_node: Optional[FileNode] = None
        self.current_node: Optional[FileNode] = None
        self.stats_report: Optional[StatisticalReport] = None
        self.scanner: Optional[DirectoryScanner] = None
        self.current_scan_path: str = os.path.expanduser("~")

        self._setup_headerbar()
        self._setup_ui()
        self._setup_statusbar()

    def _setup_headerbar(self) -> None:
        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(True)
        self.header.set_title("StatDisk")
        self.header.set_subtitle("Statistical Disk Space Analyzer")
        self.set_titlebar(self.header)

        # Scan Folder Button
        btn_scan = Gtk.Button()
        box_scan = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        icon_scan = Gtk.Image.new_from_icon_name("folder-open", Gtk.IconSize.BUTTON)
        lbl_scan = Gtk.Label(label="Scan Folder")
        box_scan.pack_start(icon_scan, False, False, 0)
        box_scan.pack_start(lbl_scan, False, False, 0)
        btn_scan.add(box_scan)
        btn_scan.get_style_context().add_class('suggested-action')
        btn_scan.connect('clicked', self._on_choose_folder_clicked)
        self.header.pack_start(btn_scan)

        # Scan Home Button
        btn_home = Gtk.Button()
        box_home = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        icon_home = Gtk.Image.new_from_icon_name("user-home", Gtk.IconSize.BUTTON)
        lbl_home = Gtk.Label(label="Home")
        box_home.pack_start(icon_home, False, False, 0)
        box_home.pack_start(lbl_home, False, False, 0)
        btn_home.add(box_home)
        btn_home.set_tooltip_text("Quick scan Home directory")
        btn_home.connect('clicked', lambda _: self.start_scan(os.path.expanduser("~")))
        self.header.pack_start(btn_home)

        # Refresh / Rescan Button
        self.btn_refresh = Gtk.Button()
        self.btn_refresh.set_image(Gtk.Image.new_from_icon_name("view-refresh", Gtk.IconSize.BUTTON))
        self.btn_refresh.set_tooltip_text("Rescan current directory")
        self.btn_refresh.connect('clicked', lambda _: self.start_scan(self.current_scan_path))
        self.header.pack_start(self.btn_refresh)

        # Progress Spinner & Cancel Button
        self.spinner = Gtk.Spinner()
        self.header.pack_start(self.spinner)

        self.btn_cancel = Gtk.Button(label="Cancel")
        self.btn_cancel.get_style_context().add_class('destructive-action')
        self.btn_cancel.connect('clicked', self._on_cancel_clicked)
        self.btn_cancel.set_no_show_all(True)
        self.header.pack_start(self.btn_cancel)

        # Right side actions
        # Export Report Button
        self.btn_export = Gtk.Button()
        box_exp = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        icon_exp = Gtk.Image.new_from_icon_name("document-save", Gtk.IconSize.BUTTON)
        lbl_exp = Gtk.Label(label="Export Report")
        box_exp.pack_start(icon_exp, False, False, 0)
        box_exp.pack_start(lbl_exp, False, False, 0)
        btn_exp_widget = Gtk.Button()
        btn_exp_widget.add(box_exp)
        btn_exp_widget.set_tooltip_text("Export LaTeX, Markdown, CSV, or JSON analysis")
        btn_exp_widget.connect('clicked', self._on_export_clicked)
        self.header.pack_end(btn_exp_widget)

        # View Stack Switcher
        self.stack_switcher = Gtk.StackSwitcher()
        self.header.set_custom_title(self.stack_switcher)

    def _setup_ui(self) -> None:
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(main_vbox)

        # Breadcrumbs bar
        self.breadcrumbs = BreadcrumbsBar(on_navigate=self.navigate_to_node)
        main_vbox.pack_start(self.breadcrumbs, False, False, 0)
        main_vbox.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        # Stack container
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(200)
        self.stack_switcher.set_stack(self.stack)

        # 1. Sunburst Visual Map View (Split with Table)
        self.paned_sunburst = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.sunburst_view = SunburstView(on_navigate=self.navigate_to_node)
        self.sunburst_tree = StorageTreeView(on_navigate=self.navigate_to_node)
        self.paned_sunburst.pack1(self.sunburst_view, resize=True, shrink=False)
        self.paned_sunburst.pack2(self.sunburst_tree, resize=True, shrink=False)
        self.paned_sunburst.set_position(580)
        self.stack.add_titled(self.paned_sunburst, "sunburst", "☀️ Sunburst Map")

        # 2. Treemap View (Split with Table)
        self.paned_treemap = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.treemap_view = TreemapView(on_navigate=self.navigate_to_node)
        self.treemap_tree = StorageTreeView(on_navigate=self.navigate_to_node)
        self.paned_treemap.pack1(self.treemap_view, resize=True, shrink=False)
        self.paned_treemap.pack2(self.treemap_tree, resize=True, shrink=False)
        self.paned_treemap.set_position(580)
        self.stack.add_titled(self.paned_treemap, "treemap", "🗂️ Treemap")

        # 3. Dedicated Organized Table View
        self.full_tree_view = StorageTreeView(on_navigate=self.navigate_to_node)
        self.stack.add_titled(self.full_tree_view, "table", "📋 File Browser")

        # 4. Statistical Analysis Notebook
        self.stats_panel = StatsPanel()
        self.stack.add_titled(self.stats_panel, "statistics", "📈 Statistical Analysis")

        main_vbox.pack_start(self.stack, True, True, 0)

    def _setup_statusbar(self) -> None:
        self.status_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.status_bar.set_margin_start(12)
        self.status_bar.set_margin_end(12)
        self.status_bar.set_margin_top(4)
        self.status_bar.set_margin_bottom(4)
        self.status_bar.get_style_context().add_class('app-statusbar')

        self.lbl_status = Gtk.Label(label="Ready. Choose a folder to analyze.")
        self.lbl_status.set_xalign(0.0)
        self.status_bar.pack_start(self.lbl_status, True, True, 0)

        self.lbl_quickstats = Gtk.Label(label="")
        self.lbl_quickstats.set_xalign(1.0)
        self.status_bar.pack_end(self.lbl_quickstats, False, False, 0)

        self.get_children()[0].pack_end(self.status_bar, False, False, 0)

    def _on_choose_folder_clicked(self, button: Gtk.Button) -> None:
        dialog = Gtk.FileChooserDialog(
            title="Select Folder to Analyze",
            parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        dialog.add_button("Analyze This Folder", Gtk.ResponseType.OK)
        dialog.set_default_size(650, 400)
        dialog.set_current_folder(self.current_scan_path)

        res = dialog.run()
        if res == Gtk.ResponseType.OK:
            target = dialog.get_filename()
            dialog.destroy()
            if target:
                self.start_scan(target)
        else:
            dialog.destroy()

    def start_scan(self, path: str) -> None:
        if self.scanner and self.scanner.is_running():
            self.scanner.cancel()

        self.current_scan_path = path
        self.header.set_subtitle(f"Scanning: {path}...")
        self.spinner.start()
        self.btn_cancel.show()
        self.lbl_status.set_text(f"Scanning {path}...")
        self.lbl_quickstats.set_text("")

        self.scanner = DirectoryScanner(
            root_path=path,
            on_progress=self._on_scan_progress,
            on_finished=self._on_scan_finished,
            on_error=self._on_scan_error
        )
        self.scanner.start()

    def _on_cancel_clicked(self, button: Gtk.Button) -> None:
        if self.scanner:
            self.scanner.cancel()
        self.spinner.stop()
        self.btn_cancel.hide()
        self.lbl_status.set_text("Scan cancelled by user.")

    def _on_scan_progress(self, files: int, dirs: int, total_b: int, current_path: str) -> None:
        short_p = current_path if len(current_path) < 45 else ("…" + current_path[-42:])
        self.lbl_status.set_text(f"Scanning: {short_p}")
        self.lbl_quickstats.set_text(f"{files:,} files | {format_bytes(total_b)}")

    def _on_scan_finished(self, root: FileNode, stats: ScanStats) -> None:
        self.spinner.stop()
        self.btn_cancel.hide()
        self.root_node = root
        self.header.set_subtitle(f"{root.name} - {format_bytes(root.size)} ({stats.total_files:,} files)")

        # Compute full statistical analysis
        self.stats_report = StatsEngine.analyze(
            sizes_list=stats.file_sizes,
            mtimes_list=stats.file_mtimes,
            extensions_list=stats.file_extensions,
            paths_list=stats.file_paths,
            total_dirs=stats.total_dirs,
            scan_duration=stats.scan_duration
        )

        # Update statistical panel
        self.stats_panel.update_report(self.stats_report)

        # Navigate views to root
        self.navigate_to_node(root)

        # Update status bar
        self.lbl_status.set_text(
            f"Analysis complete in {stats.scan_duration:.2f}s: {stats.total_files:,} files in {stats.total_dirs:,} folders."
        )
        self.lbl_quickstats.set_text(
            f"Total: {format_bytes(root.size)} | Gini Index: {self.stats_report.gini_coefficient:.3f}"
        )

    def _on_scan_error(self, err_msg: str) -> None:
        self.spinner.stop()
        self.btn_cancel.hide()
        self.lbl_status.set_text(f"Error scanning: {err_msg}")
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            message_format=f"Failed to scan path:\n{err_msg}"
        )
        dialog.run()
        dialog.destroy()

    def navigate_to_node(self, node: FileNode) -> None:
        self.current_node = node
        self.breadcrumbs.set_current_node(node)
        self.sunburst_view.set_node(node)
        self.sunburst_tree.set_node(node)
        self.treemap_view.set_node(node)
        self.treemap_tree.set_node(node)
        self.full_tree_view.set_node(node)

    def _on_export_clicked(self, button: Gtk.Button) -> None:
        if not self.stats_report:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=Gtk.DialogFlags.MODAL,
                type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                message_format="No statistical data to export. Please scan a folder first."
            )
            dialog.run()
            dialog.destroy()
            return

        export_dlg = ExportDialog(self, self.stats_report, self.current_scan_path)
        res = export_dlg.run()
        if res == Gtk.ResponseType.OK:
            saved_file = export_dlg.execute_export()
            export_dlg.destroy()
            if saved_file:
                info_dlg = Gtk.MessageDialog(
                    transient_for=self,
                    flags=Gtk.DialogFlags.MODAL,
                    type=Gtk.MessageType.INFO,
                    buttons=Gtk.ButtonsType.OK,
                    message_format="Report Exported Successfully!"
                )
                info_dlg.format_secondary_text(f"File saved to:\n{saved_file}")
                info_dlg.run()
                info_dlg.destroy()
        else:
            export_dlg.destroy()
