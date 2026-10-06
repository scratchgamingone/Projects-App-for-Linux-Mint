"""
MintStatLab - Main GTK3 Desktop Application
Linux Mint System Statistical Telemetry & Performance Lab
"""

import sys
import os
import time
import threading
from typing import Dict, List, Any, Optional

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Pango

import numpy as np
import matplotlib
matplotlib.use('GTK3Agg')
from matplotlib.backends.backend_gtk3agg import FigureCanvasGTK3Agg
from matplotlib.figure import Figure

# Import internal modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stats_engine
import data_collector
import plots
import exporter


class MintStatLabApp(Gtk.Window):
    def __init__(self):
        super().__init__(title="MintStatLab - Linux Mint Statistical Telemetry")
        self.set_default_size(1200, 800)
        self.set_position(Gtk.WindowPosition.CENTER)

        # Apply dark theme styling
        settings = Gtk.Settings.get_default()
        if settings:
            settings.set_property("gtk-application-prefer-dark-theme", True)

        self.apply_custom_css()

        # Telemetry State
        self.time_buffer = data_collector.SystemTimeSeriesBuffer(max_points=240)
        self.current_snapshot: Optional[data_collector.TelemetrySnapshot] = None
        self.moments_ram: Dict[str, float] = {}
        self.moments_cpu: Dict[str, float] = {}
        self.gini_ram = 0.0
        self.p_ram = np.array([0.0, 1.0])
        self.lorenz_ram = np.array([0.0, 1.0])
        self.shares_ram: Dict[str, float] = {}
        self.gini_cpu = 0.0
        self.p_cpu = np.array([0.0, 1.0])
        self.lorenz_cpu = np.array([0.0, 1.0])
        self.fit_info: Dict[str, Any] = {}
        self.km_user: Dict[str, Any] = {}
        self.km_daemon: Dict[str, Any] = {}
        self.point_res: Dict[str, Any] = {}
        self.reg_drift: Dict[str, Any] = {}

        self.auto_timer_id: Optional[int] = None
        self.is_collecting = False

        self.build_ui()

        # Initial collection
        self.trigger_refresh()

    def apply_custom_css(self):
        """Injects styling matching Linux Mint's dark teal design language."""
        css_provider = Gtk.CssProvider()
        css = b"""
        window {
            background-color: #16161e;
            color: #c0caf5;
        }
        headerbar {
            background-color: #1a1b26;
            border-bottom: 1px solid #292e42;
        }
        notebook tab {
            background-color: #1f2335;
            color: #a9b1d6;
            padding: 8px 16px;
            border-bottom: 2px solid transparent;
            font-weight: bold;
        }
        notebook tab:checked {
            background-color: #16161e;
            color: #7dcfff;
            border-bottom: 2px solid #73daca;
        }
        .stat-card {
            background-color: #1a1b26;
            border-radius: 6px;
            border: 1px solid #292e42;
            padding: 10px 14px;
        }
        .stat-value {
            font-size: 18px;
            font-weight: bold;
            color: #7dcfff;
        }
        .stat-label {
            font-size: 11px;
            color: #7f849c;
            text-transform: uppercase;
        }
        treeview {
            background-color: #1a1b26;
            color: #c0caf5;
            border: 1px solid #292e42;
        }
        treeview:selected {
            background-color: #292e42;
            color: #7dcfff;
        }
        """
        css_provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def build_ui(self):
        # HeaderBar
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title("MintStatLab")
        header.set_subtitle("Linux Mint Statistical Telemetry & Anomaly Lab")
        self.set_titlebar(header)

        # Refresh Button
        self.btn_refresh = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        self.btn_refresh.set_tooltip_text("Refresh Live Snapshot (F5)")
        self.btn_refresh.connect("clicked", lambda b: self.trigger_refresh())
        header.pack_start(self.btn_refresh)

        # Auto-Sampling Toggle
        box_auto = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl_auto = Gtk.Label(label="Live (2s):")
        self.switch_auto = Gtk.Switch()
        self.switch_auto.set_active(True)
        self.switch_auto.connect("notify::active", self.on_auto_switch_toggled)
        box_auto.pack_start(lbl_auto, False, False, 0)
        box_auto.pack_start(self.switch_auto, False, False, 0)
        header.pack_start(box_auto)

        # Export Menu Button
        btn_export = Gtk.MenuButton.new()
        btn_export.set_tooltip_text("Export Statistical Report / Dataset")
        btn_export.set_image(Gtk.Image.new_from_icon_name("document-save-symbolic", Gtk.IconSize.BUTTON))
        
        export_menu = Gtk.Menu()
        item_latex = Gtk.MenuItem(label="Export LaTeX Academic Report (.tex)")
        item_latex.connect("activate", lambda m: self.do_export("latex"))
        export_menu.append(item_latex)
        
        item_csv = Gtk.MenuItem(label="Export Process Telemetry (.csv)")
        item_csv.connect("activate", lambda m: self.do_export("csv"))
        export_menu.append(item_csv)
        
        item_json = Gtk.MenuItem(label="Export Full JSON Schema (.json)")
        item_json.connect("activate", lambda m: self.do_export("json"))
        export_menu.append(item_json)
        
        export_menu.show_all()
        btn_export.set_popup(export_menu)
        header.pack_end(btn_export)

        # Main Layout Container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_box.set_margin_top(8)
        main_box.set_margin_bottom(8)
        main_box.set_margin_start(10)
        main_box.set_margin_end(10)
        self.add(main_box)

        # Top Metric Cards HUD
        hud_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        main_box.pack_start(hud_box, False, False, 0)

        self.card_gini_ram = self.create_stat_card("RAM Gini Index", "0.000", "Resource Monopolization")
        self.card_gini_cpu = self.create_stat_card("CPU Gini Index", "0.000", "Core Load Inequality")
        self.card_procs = self.create_stat_card("Active Processes", "0", "User / Daemon / Kernel")
        self.card_lambda = self.create_stat_card("Arrival Rate λ", "0.00/s", "Journal Events Stream")
        self.card_drift = self.create_stat_card("Memory Drift β₁", "0.00 MiB/s", "Leak Severity: Normal")

        hud_box.pack_start(self.card_gini_ram[0], True, True, 0)
        hud_box.pack_start(self.card_gini_cpu[0], True, True, 0)
        hud_box.pack_start(self.card_procs[0], True, True, 0)
        hud_box.pack_start(self.card_lambda[0], True, True, 0)
        hud_box.pack_start(self.card_drift[0], True, True, 0)

        # Notebook (Tabs)
        self.notebook = Gtk.Notebook()
        main_box.pack_start(self.notebook, True, True, 0)

        # Tab 1: Inequality & Heavy Tails
        self.fig_ineq = Figure(figsize=(9, 5), dpi=90)
        self.canvas_ineq = FigureCanvasGTK3Agg(self.fig_ineq)
        tab1_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        tab1_box.pack_start(self.canvas_ineq, True, True, 0)
        self.notebook.append_page(tab1_box, Gtk.Label(label="📊 Resource Inequality & Heavy Tails"))

        # Tab 2: Kaplan-Meier Survival
        self.fig_km = Figure(figsize=(9, 5), dpi=90)
        self.canvas_km = FigureCanvasGTK3Agg(self.fig_km)
        tab2_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        tab2_box.pack_start(self.canvas_km, True, True, 0)
        self.notebook.append_page(tab2_box, Gtk.Label(label="⏳ Process Survival Analysis"))

        # Tab 3: Stochastic Point Process
        self.fig_point = Figure(figsize=(9, 5), dpi=90)
        self.canvas_point = FigureCanvasGTK3Agg(self.fig_point)
        tab3_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        tab3_box.pack_start(self.canvas_point, True, True, 0)
        self.notebook.append_page(tab3_box, Gtk.Label(label="🎲 Stochastic Event Arrivals"))

        # Tab 4: Temporal Drift & ACF
        self.fig_drift = Figure(figsize=(9, 5), dpi=90)
        self.canvas_drift = FigureCanvasGTK3Agg(self.fig_drift)
        tab4_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        tab4_box.pack_start(self.canvas_drift, True, True, 0)
        self.notebook.append_page(tab4_box, Gtk.Label(label="📈 Temporal Drift & Memory Leaks"))

        # Tab 5: Process Outlier Table
        tab5_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        # Filter Search Entry
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl_search = Gtk.Label(label="Filter Processes:")
        self.entry_filter = Gtk.SearchEntry()
        self.entry_filter.connect("search-changed", self.on_search_changed)
        search_box.pack_start(lbl_search, False, False, 0)
        search_box.pack_start(self.entry_filter, True, True, 0)
        tab5_box.pack_start(search_box, False, False, 0)

        # TreeView ListStore
        # Cols: PID (int), Name (str), Category (str), CPU% (str), RAM MB (str), Age (str), ModZ RSS (str), Outlier (str)
        self.liststore = Gtk.ListStore(int, str, str, str, str, str, str, str)
        self.filter_model = self.liststore.filter_new()
        self.filter_model.set_visible_func(self.filter_func)
        
        treeview = Gtk.TreeView(model=self.filter_model)
        for i, col_title in enumerate(["PID", "Name", "Category", "CPU %", "RAM (MiB)", "Lifespan", "Mod Z-Score (RAM)", "Outlier Status"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(col_title, renderer, text=i)
            column.set_sort_column_id(i)
            column.set_resizable(True)
            treeview.append_column(column)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(treeview)
        tab5_box.pack_start(scroll, True, True, 0)

        self.notebook.append_page(tab5_box, Gtk.Label(label="🎯 Outlier Process Matrix"))

        self.connect("key-press-event", self.on_key_press)
        self.show_all()

        # Start live timer if active
        if self.switch_auto.get_active():
            self.auto_timer_id = GLib.timeout_add_seconds(2, self.on_timer_tick)

    def create_stat_card(self, label: str, init_val: str, subtitle: str) -> Tuple[Gtk.Box, Gtk.Label, Gtk.Label]:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.get_style_context().add_class("stat-card")
        
        lbl_title = Gtk.Label(label=label)
        lbl_title.get_style_context().add_class("stat-label")
        lbl_title.set_xalign(0.0)
        
        lbl_val = Gtk.Label(label=init_val)
        lbl_val.get_style_context().add_class("stat-value")
        lbl_val.set_xalign(0.0)
        
        lbl_sub = Gtk.Label(label=subtitle)
        lbl_sub.set_xalign(0.0)
        lbl_sub.set_opacity(0.7)
        lbl_sub.modify_font(Pango.FontDescription("9"))

        box.pack_start(lbl_title, False, False, 0)
        box.pack_start(lbl_val, False, False, 0)
        box.pack_start(lbl_sub, False, False, 0)
        return box, lbl_val, lbl_sub

    def on_auto_switch_toggled(self, switch, gparam):
        if switch.get_active():
            if self.auto_timer_id is None:
                self.auto_timer_id = GLib.timeout_add_seconds(2, self.on_timer_tick)
        else:
            if self.auto_timer_id is not None:
                GLib.source_remove(self.auto_timer_id)
                self.auto_timer_id = None

    def on_timer_tick(self) -> bool:
        self.trigger_refresh()
        return True

    def on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_F5:
            self.trigger_refresh()
            return True
        return False

    def trigger_refresh(self):
        if self.is_collecting:
            return
        self.is_collecting = True
        threading.Thread(target=self.worker_collect, daemon=True).start()

    def worker_collect(self):
        try:
            snap = data_collector.collect_process_snapshot()
            events = data_collector.collect_system_events(max_events=250)

            # Process data arrays
            rss_arr = np.array([p.rss_mb for p in snap.processes], dtype=float)
            cpu_arr = np.array([p.cpu_pct for p in snap.processes], dtype=float)

            # Update rolling buffer
            self.time_buffer.append_sample(snap.total_rss_mb, snap.total_cpu_pct, len(snap.processes))

            # Statistical calculations
            moments_ram = stats_engine.compute_distribution_moments(rss_arr)
            moments_cpu = stats_engine.compute_distribution_moments(cpu_arr)
            gini_ram, p_ram, lorenz_ram, shares_ram = stats_engine.compute_inequality_metrics(rss_arr)
            gini_cpu, p_cpu, lorenz_cpu, shares_cpu = stats_engine.compute_inequality_metrics(cpu_arr)
            
            fit_info = stats_engine.fit_heavy_tail_models(rss_arr)

            # Kaplan-Meier survival for User vs Daemon
            u_times = np.array([p.age_seconds for p in snap.processes if p.category == "User Application"])
            d_times = np.array([p.age_seconds for p in snap.processes if p.category == "System Daemon"])
            km_user = stats_engine.compute_kaplan_meier(u_times)
            km_daemon = stats_engine.compute_kaplan_meier(d_times)

            # Point process arrivals
            point_res = stats_engine.analyze_point_process_arrivals(events)

            # Time series drift regression & ACF
            reg_drift = stats_engine.compute_drift_and_acf(self.time_buffer.get_ram_series())

            # Outlier detection
            mod_z = stats_engine.compute_modified_z_scores(rss_arr)
            q1, q3 = moments_ram.get("q1", 0.0), moments_ram.get("q3", 0.0)
            iqr = moments_ram.get("iqr", 0.0)
            tukey_thresh = q3 + 1.5 * iqr

            for i, p in enumerate(snap.processes):
                p.mod_z_rss = float(mod_z[i]) if i < len(mod_z) else 0.0
                if p.rss_mb > tukey_thresh or abs(p.mod_z_rss) > 3.5:
                    p.is_outlier = True

            # Schedule UI update on GTK main thread
            GLib.idle_add(
                self.update_ui_state,
                snap, moments_ram, moments_cpu, gini_ram, p_ram, lorenz_ram, shares_ram,
                gini_cpu, p_cpu, lorenz_cpu, fit_info, km_user, km_daemon, point_res, reg_drift
            )
        except Exception as e:
            print(f"Sampling worker exception: {e}")
            self.is_collecting = False

    def update_ui_state(self, snap, moments_ram, moments_cpu, gini_ram, p_ram, lorenz_ram, shares_ram,
                        gini_cpu, p_cpu, lorenz_cpu, fit_info, km_user, km_daemon, point_res, reg_drift):
        self.current_snapshot = snap
        self.moments_ram = moments_ram
        self.moments_cpu = moments_cpu
        self.gini_ram = gini_ram
        self.p_ram = p_ram
        self.lorenz_ram = lorenz_ram
        self.shares_ram = shares_ram
        self.gini_cpu = gini_cpu
        self.p_cpu = p_cpu
        self.lorenz_cpu = lorenz_cpu
        self.fit_info = fit_info
        self.km_user = km_user
        self.km_daemon = km_daemon
        self.point_res = point_res
        self.reg_drift = reg_drift

        # Update Top HUD Cards
        self.card_gini_ram[1].set_text(f"{gini_ram:.3f}")
        self.card_gini_ram[2].set_text(f"Top 5% holds {shares_ram.get('top_5_pct', 0.0):.1f}% RAM")

        self.card_gini_cpu[1].set_text(f"{gini_cpu:.3f}")
        self.card_gini_cpu[2].set_text(f"Total CPU: {snap.total_cpu_pct:.1f}%")

        self.card_procs[1].set_text(f"{len(snap.processes)}")
        self.card_procs[2].set_text(f"User: {snap.user_app_count} | Sys: {snap.daemon_count} | Kern: {snap.kernel_thread_count}")

        if point_res.get("valid"):
            self.card_lambda[1].set_text(f"{point_res['lambda_rate_hz']:.2f} /s")
            self.card_lambda[2].set_text(f"CV: {point_res.get('cv', 0):.2f} ({point_res.get('regime', '')[:14]}...)")

        if reg_drift.get("valid"):
            slope_min = reg_drift['slope'] * 60.0
            self.card_drift[1].set_text(f"{slope_min:+.2f} MiB/min")
            self.card_drift[2].set_text(f"R²: {reg_drift.get('r2', 0):.2f} | {reg_drift.get('leak_severity', 'Normal')}")

        # Re-render active Canvas based on active tab
        current_tab = self.notebook.get_current_page()
        self.redraw_tab_plot(current_tab)

        # Update Outlier ListStore
        self.liststore.clear()
        for p in snap.processes:
            age_str = f"{p.age_seconds / 3600.0:.2f}h" if p.age_seconds >= 3600 else f"{p.age_seconds / 60.0:.1f}m"
            outlier_tag = "⚠️ OUTLIER (Tukey/Z)" if p.is_outlier else "Normal"
            self.liststore.append([
                p.pid,
                p.name,
                p.category,
                f"{p.cpu_pct:.1f}%",
                f"{p.rss_mb:.1f}",
                age_str,
                f"{p.mod_z_rss:.2f}",
                outlier_tag
            ])

        self.is_collecting = False
        return False

    def redraw_tab_plot(self, page_num: int):
        if not self.current_snapshot:
            return
        
        pos_ram = np.array([p.rss_mb for p in self.current_snapshot.processes if p.rss_mb > 0])
        
        if page_num == 0:
            plots.render_inequality_and_dist(
                self.fig_ineq, self.gini_ram, self.p_ram, self.lorenz_ram,
                self.gini_cpu, self.p_cpu, self.lorenz_cpu,
                pos_ram, self.fit_info
            )
            self.canvas_ineq.draw_idle()
        elif page_num == 1:
            plots.render_kaplan_meier_survival(self.fig_km, self.km_user, self.km_daemon)
            self.canvas_km.draw_idle()
        elif page_num == 2:
            plots.render_stochastic_arrivals(self.fig_point, self.point_res)
            self.canvas_point.draw_idle()
        elif page_num == 3:
            plots.render_drift_and_acf(self.fig_drift, self.time_buffer.get_ram_series(), self.reg_drift)
            self.canvas_drift.draw_idle()

    def on_search_changed(self, entry):
        self.filter_model.refilter()

    def filter_func(self, model, iter, data):
        query = self.entry_filter.get_text().strip().lower()
        if not query:
            return True
        name = model.get_value(iter, 1).lower()
        cat = model.get_value(iter, 2).lower()
        tag = model.get_value(iter, 7).lower()
        return query in name or query in cat or query in tag

    def do_export(self, format_type: str):
        if not self.current_snapshot:
            return

        dialog = Gtk.FileChooserDialog(
            title=f"Save {format_type.upper()} Export",
            parent=self,
            action=Gtk.FileChooserAction.SAVE
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK
        )
        dialog.set_do_overwrite_confirmation(True)

        home_dir = os.path.expanduser("~")
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")

        if format_type == "latex":
            dialog.set_current_name(f"linuxmint_telemetry_{timestamp_str}.tex")
        elif format_type == "csv":
            dialog.set_current_name(f"linuxmint_processes_{timestamp_str}.csv")
        else:
            dialog.set_current_name(f"linuxmint_stats_{timestamp_str}.json")

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = dialog.get_filename()
            dialog.destroy()

            success = False
            if format_type == "latex":
                success = exporter.export_latex_report(
                    filepath, self.current_snapshot, self.moments_ram, self.moments_cpu,
                    self.gini_ram, self.gini_cpu, self.fit_info, self.km_user,
                    self.point_res, self.reg_drift
                )
            elif format_type == "csv":
                success = exporter.export_csv_dataset(filepath, self.current_snapshot.processes)
            elif format_type == "json":
                payload = {
                    "timestamp": self.current_snapshot.timestamp,
                    "moments_ram": self.moments_ram,
                    "moments_cpu": self.moments_cpu,
                    "gini_ram": self.gini_ram,
                    "gini_cpu": self.gini_cpu,
                    "shares_ram": self.shares_ram,
                    "heavy_tail_fit": self.fit_info,
                    "point_process": {k: v for k, v in self.point_res.items() if k != "intervals"},
                    "drift_regression": {k: v for k, v in self.reg_drift.items() if k != "fitted_line"},
                }
                success = exporter.export_json_schema(filepath, payload)

            msg_dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.INFO if success else Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=f"Report successfully saved to:\n{filepath}" if success else "Failed to export report."
            )
            msg_dialog.run()
            msg_dialog.destroy()
        else:
            dialog.destroy()


def main():
    app = MintStatLabApp()
    app.connect("destroy", Gtk.main_quit)
    Gtk.main()


if __name__ == "__main__":
    main()
