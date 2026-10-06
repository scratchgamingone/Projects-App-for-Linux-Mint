"""
Comprehensive Statistical Analysis Panel for Statistics Majors.
Includes distribution moments, log-normal fitting, Lorenz curve & Gini index,
Tukey outlier detection, temporal correlation, and Pareto extension analysis.
"""

import math
import subprocess
import os
from typing import Optional, List, Dict, Any
import numpy as np
import scipy.stats as stats

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, Pango

import matplotlib
matplotlib.use('GTK3Agg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_gtk3agg import FigureCanvasGTK3Agg
import matplotlib.ticker as ticker

from statdisk.stats_engine import StatisticalReport
from statdisk.tree_model import format_bytes

DARK_BG = '#1a1d24'
CARD_BG = '#222630'
TEXT_COLOR = '#e2e8f0'
TEXT_MUTED = '#94a3b8'
ACCENT_BLUE = '#38bdf8'
ACCENT_GREEN = '#34d399'
ACCENT_CORAL = '#f87171'
ACCENT_AMBER = '#fbbf24'
ACCENT_PURPLE = '#c084fc'
GRID_COLOR = '#2e3442'


def style_ax(ax):
    """Apply modern dark styling to a matplotlib axes."""
    ax.set_facecolor(CARD_BG)
    ax.tick_params(colors=TEXT_MUTED, labelsize=9)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
        spine.set_linewidth(1.0)
    ax.grid(True, linestyle='--', alpha=0.3, color=GRID_COLOR)
    ax.title.set_color(TEXT_COLOR)
    ax.xaxis.label.set_color(TEXT_COLOR)
    ax.yaxis.label.set_color(TEXT_COLOR)


class StatsPanel(Gtk.Notebook):
    """Multi-tab notebook displaying deep statistical analysis."""

    def __init__(self):
        super().__init__()
        self.set_scrollable(True)
        self.report: Optional[StatisticalReport] = None

        # Build tabs
        self.tab_summary = self._build_tab_summary()
        self.tab_distribution = self._build_tab_distribution()
        self.tab_inequality = self._build_tab_inequality()
        self.tab_outliers = self._build_tab_outliers()
        self.tab_temporal = self._build_tab_temporal()
        self.tab_extensions = self._build_tab_extensions()

        self.append_page(self.tab_summary, Gtk.Label(label="📊 Summary & Moments"))
        self.append_page(self.tab_distribution, Gtk.Label(label="📈 Log-Normal & PDF"))
        self.append_page(self.tab_inequality, Gtk.Label(label="⚖️ Lorenz & Gini"))
        self.append_page(self.tab_outliers, Gtk.Label(label="🎯 Outliers & Tukey"))
        self.append_page(self.tab_temporal, Gtk.Label(label="⏳ Age & Correlation"))
        self.append_page(self.tab_extensions, Gtk.Label(label="🏷️ Extensions & Pareto"))

    # =========================================================================
    # TAB 1: SUMMARY & MOMENTS
    # =========================================================================
    def _build_tab_summary(self) -> Gtk.Widget:
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        vbox.set_margin_start(16)
        vbox.set_margin_end(16)
        vbox.set_margin_top(16)
        vbox.set_margin_bottom(16)

        # Header intro
        lbl_intro = Gtk.Label()
        lbl_intro.set_markup(
            "<span size='large' weight='bold'>Filesystem Statistical Moments &amp; Dispersion</span>\n"
            "<span size='small' color='#94a3b8'>Classical and robust descriptive metrics computed on the sampled dataset.</span>"
        )
        lbl_intro.set_xalign(0.0)
        vbox.pack_start(lbl_intro, False, False, 0)

        # Grid of metric cards
        self.grid_cards = Gtk.Grid()
        self.grid_cards.set_column_spacing(12)
        self.grid_cards.set_row_spacing(12)
        self.grid_cards.set_hexpand(True)
        vbox.pack_start(self.grid_cards, False, False, 0)

        # Separator
        vbox.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 6)

        # Quantiles Table Section
        lbl_q_title = Gtk.Label()
        lbl_q_title.set_markup("<span weight='bold'>Empirical Quantiles &amp; Percentile Distribution</span>")
        lbl_q_title.set_xalign(0.0)
        vbox.pack_start(lbl_q_title, False, False, 0)

        self.store_quantiles = Gtk.ListStore(str, str, str)
        self.tree_quantiles = Gtk.TreeView(model=self.store_quantiles)
        self.tree_quantiles.set_rules_hint(True)

        for idx, (title, width) in enumerate([("Percentile", 120), ("Value (Human Readable)", 200), ("Exact Bytes", 160)]):
            rend = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(title, rend, text=idx)
            col.set_min_width(width)
            self.tree_quantiles.append_column(col)

        vbox.pack_start(self.tree_quantiles, False, False, 0)

        scrolled.add(vbox)
        return scrolled

    def _create_metric_card(self, title: str, value: str, sub: str, accent_color: str) -> Gtk.Frame:
        frame = Gtk.Frame()
        frame.get_style_context().add_class('stat-card')
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(10)
        box.set_margin_bottom(10)

        lbl_title = Gtk.Label()
        lbl_title.set_markup(f"<span size='small' color='{TEXT_MUTED}'>{title}</span>")
        lbl_title.set_xalign(0.0)
        box.pack_start(lbl_title, False, False, 0)

        lbl_val = Gtk.Label()
        lbl_val.set_markup(f"<span size='x-large' weight='bold' color='{accent_color}'>{value}</span>")
        lbl_val.set_xalign(0.0)
        box.pack_start(lbl_val, False, False, 0)

        lbl_sub = Gtk.Label()
        lbl_sub.set_markup(f"<span size='xx-small' color='{TEXT_MUTED}'>{sub}</span>")
        lbl_sub.set_xalign(0.0)
        box.pack_start(lbl_sub, False, False, 0)

        frame.add(box)
        return frame

    # =========================================================================
    # TAB 2: LOG-NORMAL & PDF
    # =========================================================================
    def _build_tab_distribution(self) -> Gtk.Widget:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)

        self.fig_dist = Figure(figsize=(7, 4.5), dpi=100, facecolor=DARK_BG)
        self.canvas_dist = FigureCanvasGTK3Agg(self.fig_dist)
        vbox.pack_start(self.canvas_dist, True, True, 0)

        self.lbl_dist_notes = Gtk.Label()
        self.lbl_dist_notes.set_line_wrap(True)
        self.lbl_dist_notes.set_xalign(0.0)
        vbox.pack_start(self.lbl_dist_notes, False, False, 0)

        return vbox

    # =========================================================================
    # TAB 3: LORENZ & GINI
    # =========================================================================
    def _build_tab_inequality(self) -> Gtk.Widget:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)

        self.fig_ineq = Figure(figsize=(7, 4.5), dpi=100, facecolor=DARK_BG)
        self.canvas_ineq = FigureCanvasGTK3Agg(self.fig_ineq)
        vbox.pack_start(self.canvas_ineq, True, True, 0)

        self.lbl_ineq_notes = Gtk.Label()
        self.lbl_ineq_notes.set_line_wrap(True)
        self.lbl_ineq_notes.set_xalign(0.0)
        vbox.pack_start(self.lbl_ineq_notes, False, False, 0)

        return vbox

    # =========================================================================
    # TAB 4: OUTLIERS & TUKEY
    # =========================================================================
    def _build_tab_outliers(self) -> Gtk.Widget:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)

        # Matplotlib Boxplot at top
        self.fig_outliers = Figure(figsize=(7, 2.5), dpi=100, facecolor=DARK_BG)
        self.canvas_outliers = FigureCanvasGTK3Agg(self.fig_outliers)
        vbox.pack_start(self.canvas_outliers, False, False, 0)

        lbl_table = Gtk.Label()
        lbl_table.set_markup("<span weight='bold'>Identified Statistical Outliers (Tukey's Fences &amp; Modified Z-Score)</span>")
        lbl_table.set_xalign(0.0)
        vbox.pack_start(lbl_table, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        # Col 0: File Name, Col 1: Human Size, Col 2: Modified Z-Score, Col 3: % Total, Col 4: Path
        self.store_outliers = Gtk.ListStore(str, str, str, str, str)
        self.tree_outliers = Gtk.TreeView(model=self.store_outliers)
        self.tree_outliers.set_rules_hint(True)

        cols = [
            ("File Name", 200, 0),
            ("Size", 100, 1),
            ("Modified Z-Score (MAD)", 150, 2),
            ("Share of Total", 110, 3),
            ("Full Path", 320, 4)
        ]
        for title, w, c_idx in cols:
            rend = Gtk.CellRendererText()
            rend.set_property("ellipsize", Pango.EllipsizeMode.END)
            c = Gtk.TreeViewColumn(title, rend, text=c_idx)
            c.set_min_width(w)
            c.set_resizable(True)
            self.tree_outliers.append_column(c)

        self.tree_outliers.connect('row-activated', self._on_outlier_row_activated)
        scrolled.add(self.tree_outliers)
        vbox.pack_start(scrolled, True, True, 0)

        return vbox

    def _on_outlier_row_activated(self, tree: Gtk.TreeView, path: Gtk.TreePath, column: Gtk.TreeViewColumn) -> None:
        model = tree.get_model()
        tree_iter = model.get_iter(path)
        if tree_iter:
            file_path = model.get_value(tree_iter, 4)
            subprocess.Popen(['xdg-open', file_path])

    # =========================================================================
    # TAB 5: TEMPORAL & CORRELATION
    # =========================================================================
    def _build_tab_temporal(self) -> Gtk.Widget:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)

        self.fig_temporal = Figure(figsize=(7, 4.0), dpi=100, facecolor=DARK_BG)
        self.canvas_temporal = FigureCanvasGTK3Agg(self.fig_temporal)
        vbox.pack_start(self.canvas_temporal, True, True, 0)

        # Age brackets table
        lbl_b = Gtk.Label()
        lbl_b.set_markup("<span weight='bold'>Storage Allocation by Age Bracket (Temporal Decay)</span>")
        lbl_b.set_xalign(0.0)
        vbox.pack_start(lbl_b, False, False, 0)

        self.store_age = Gtk.ListStore(str, str, str, str)
        self.tree_age = Gtk.TreeView(model=self.store_age)
        self.tree_age.set_rules_hint(True)

        for idx, (title, w) in enumerate([("Age Bracket", 140), ("Files Count", 100), ("Volume", 120), ("Percentage", 100)]):
            rend = Gtk.CellRendererText()
            c = Gtk.TreeViewColumn(title, rend, text=idx)
            c.set_min_width(w)
            self.tree_age.append_column(c)

        vbox.pack_start(self.tree_age, False, False, 0)
        return vbox

    # =========================================================================
    # TAB 6: EXTENSIONS & PARETO
    # =========================================================================
    def _build_tab_extensions(self) -> Gtk.Widget:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)

        self.fig_ext = Figure(figsize=(7, 4.5), dpi=100, facecolor=DARK_BG)
        self.canvas_ext = FigureCanvasGTK3Agg(self.fig_ext)
        vbox.pack_start(self.canvas_ext, True, True, 0)

        self.lbl_entropy_notes = Gtk.Label()
        self.lbl_entropy_notes.set_line_wrap(True)
        self.lbl_entropy_notes.set_xalign(0.0)
        vbox.pack_start(self.lbl_entropy_notes, False, False, 0)

        return vbox

    # =========================================================================
    # UPDATE DATA & RENDER PLOTS
    # =========================================================================
    def update_report(self, rep: Optional[StatisticalReport]) -> None:
        self.report = rep
        if not rep or rep.sample_size == 0:
            return

        self._render_tab_summary()
        self._render_tab_distribution()
        self._render_tab_inequality()
        self._render_tab_outliers()
        self._render_tab_temporal()
        self._render_tab_extensions()

    def _render_tab_summary(self) -> None:
        rep = self.report
        # Clear existing cards
        for ch in self.grid_cards.get_children():
            self.grid_cards.remove(ch)

        cards_data = [
            ("SAMPLE SIZE (N)", f"{rep.sample_size:,}", f"Dirs: {rep.total_directories:,} | Scan: {rep.scan_duration:.2f}s", ACCENT_BLUE),
            ("TOTAL STORAGE VOLUME", format_bytes(rep.total_bytes), f"{rep.total_bytes:,} exact bytes", ACCENT_GREEN),
            ("ARITHMETIC MEAN (x̄)", format_bytes(int(rep.mean)), f"Geo Mean: {format_bytes(int(rep.geometric_mean))}", ACCENT_PURPLE),
            ("MEDIAN (x̃ / Q2)", format_bytes(int(rep.median)), f"IQR: {format_bytes(int(rep.iqr))}", ACCENT_AMBER),
            ("STANDARD DEVIATION (s)", format_bytes(int(rep.std_dev)), f"CV: {rep.cv:.2f} (Variance: {rep.variance:.1e})", ACCENT_CORAL),
            ("SKEWNESS (g₁)", f"{rep.skewness:.3f}", "Positive > 0: Heavy right-tail", ACCENT_BLUE),
            ("EXCESS KURTOSIS (g₂)", f"{rep.kurtosis:.2f}", "Leptokurtic (Heavy tailed)", ACCENT_PURPLE),
            ("GINI COEFFICIENT (G)", f"{rep.gini_coefficient:.4f}", f"0=Equal, 1=Extreme inequality", ACCENT_CORAL),
            ("PARETO 80/20 CHECK", f"{rep.pct_files_for_80pct_storage:.1f}%", "Percentage of files holding 80% space", ACCENT_AMBER),
            ("SHANNON ENTROPY H(X)", f"{rep.shannon_entropy_ext:.3f} bits", f"Evenness J: {rep.normalized_entropy_ext:.3f}", ACCENT_GREEN),
            ("SIMPSON DIVERSITY", f"{rep.simpson_diversity_ext:.3f}", f"Unique Exts: {rep.unique_extensions_count}", ACCENT_BLUE),
            ("EXTREME OUTLIERS", f"{rep.extreme_outlier_count:,}", f"Mild: {rep.mild_outlier_count:,} (>1.5×IQR)", ACCENT_CORAL),
        ]

        row = 0
        col = 0
        cols_per_row = 3
        for title, val, sub, color in cards_data:
            c = self._create_metric_card(title, val, sub, color)
            self.grid_cards.attach(c, col, row, 1, 1)
            col += 1
            if col >= cols_per_row:
                col = 0
                row += 1

        self.grid_cards.show_all()

        # Update Quantiles Table
        self.store_quantiles.clear()
        pct_order = ["P1", "P5", "P10", "P25", "P50", "P75", "P90", "P95", "P99", "P99.9"]
        for p in pct_order:
            if p in rep.percentiles:
                val = rep.percentiles[p]
                lbl = f"{p} (1st Quartile)" if p == "P25" else (f"{p} (Median / 2nd Quartile)" if p == "P50" else (f"{p} (3rd Quartile)" if p == "P75" else p))
                self.store_quantiles.append([lbl, format_bytes(int(val)), f"{int(val):,} B"])

        self.store_quantiles.append(["Max (100th Percentile)", format_bytes(rep.max_val), f"{rep.max_val:,} B"])

    def _render_tab_distribution(self) -> None:
        rep = self.report
        self.fig_dist.clf()
        ax = self.fig_dist.add_subplot(111)
        style_ax(ax)

        sizes = rep.raw_sizes
        pos_sizes = np.maximum(sizes, 1.0)
        log10_sizes = np.log10(pos_sizes)

        # Plot empirical histogram
        num_bins = min(60, max(15, int(np.sqrt(rep.sample_size))))
        counts, bin_edges, patches = ax.hist(
            log10_sizes, bins=num_bins, density=True,
            alpha=0.65, color=ACCENT_BLUE, edgecolor='#1e293b', label='Empirical Distribution'
        )

        # Fit Log-Normal PDF
        x_vals = np.linspace(min(log10_sizes), max(log10_sizes), 300)
        # Convert log10 parameters
        mu_10 = rep.lognorm_mu / math.log(10)
        sigma_10 = rep.lognorm_sigma / math.log(10)
        pdf_fitted = stats.norm.pdf(x_vals, loc=mu_10, scale=sigma_10)
        ax.plot(x_vals, pdf_fitted, color=ACCENT_CORAL, linewidth=2.2, label=f'Fitted Log-Normal (μ={mu_10:.2f}, σ={sigma_10:.2f})')

        # KDE Curve
        if rep.sample_size >= 20:
            try:
                sub = log10_sizes if len(log10_sizes) <= 2000 else np.random.choice(log10_sizes, 2000, replace=False)
                kde = stats.gaussian_kde(sub)
                ax.plot(x_vals, kde(x_vals), color=ACCENT_GREEN, linestyle='--', linewidth=1.8, label='Kernel Density Estimate (KDE)')
            except Exception:
                pass

        # X-axis custom ticks for binary sizes
        ticks = [0, 3, 6, 9, 12]
        tick_labels = ['1 B', '1 KB', '1 MB', '1 GB', '1 TB']
        ax.set_xticks(ticks)
        ax.set_xticklabels(tick_labels)
        ax.set_xlabel("File Size (Logarithmic Scale)", fontsize=10, weight='bold')
        ax.set_ylabel("Probability Density f(x)", fontsize=10, weight='bold')
        ax.set_title("Probability Density Function (PDF) & Parametric Log-Normal Fit", fontsize=11, weight='bold')
        ax.legend(facecolor=CARD_BG, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=8, loc='upper right')

        self.fig_dist.tight_layout()
        self.canvas_dist.draw()

        # Update notes
        ks_text = f"Kolmogorov-Smirnov Goodness-of-Fit Test: D = {rep.ks_stat:.4f}, p-value = {rep.ks_pvalue:.4e}."
        if rep.pareto_alpha > 0:
            ks_text += f" | Estimated Pareto Heavy-Tail Exponent α = {rep.pareto_alpha:.3f}."
        self.lbl_dist_notes.set_markup(f"<span size='small' color='{TEXT_MUTED}'>{ks_text}</span>")

    def _render_tab_inequality(self) -> None:
        rep = self.report
        self.fig_ineq.clf()
        ax = self.fig_ineq.add_subplot(111)
        style_ax(ax)

        u = rep.lorenz_u
        v = rep.lorenz_v

        # 45-degree Line of Absolute Equality
        ax.plot([0, 1], [0, 1], color=TEXT_MUTED, linestyle=':', linewidth=1.5, label='Line of Absolute Equality (G = 0)')

        # Empirical Lorenz curve
        ax.plot(u, v, color=ACCENT_CORAL, linewidth=2.5, label=f'Storage Lorenz Curve (G = {rep.gini_coefficient:.4f})')

        # Fill Gini Area
        ax.fill_between(u, v, u, color=ACCENT_CORAL, alpha=0.18, label='Storage Concentration Area')

        # Pareto 80/20 Marker
        pct_files_80 = rep.pct_files_for_80pct_storage / 100.0
        file_ratio_x = 1.0 - pct_files_80
        ax.scatter([file_ratio_x], [0.20], color=ACCENT_AMBER, s=60, zorder=5)
        ax.annotate(
            f"80% Storage\n(Top {rep.pct_files_for_80pct_storage:.1f}% files)",
            xy=(file_ratio_x, 0.20),
            xytext=(max(0.05, file_ratio_x - 0.25), 0.35),
            arrowprops=dict(facecolor=ACCENT_AMBER, shrink=0.08, width=1, headwidth=6),
            color=ACCENT_AMBER, fontsize=9, weight='bold'
        )

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel("Cumulative Proportion of Files (Ranked Smallest to Largest)", fontsize=10, weight='bold')
        ax.set_ylabel("Cumulative Proportion of Storage Space", fontsize=10, weight='bold')
        ax.set_title(f"Storage Inequality Lorenz Curve (Gini Coefficient G = {rep.gini_coefficient:.4f})", fontsize=11, weight='bold')
        ax.xaxis.set_major_formatter(ticker.PercentFormatter(1.0))
        ax.yaxis.set_major_formatter(ticker.PercentFormatter(1.0))
        ax.legend(facecolor=CARD_BG, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=8, loc='upper left')

        self.fig_ineq.tight_layout()
        self.canvas_ineq.draw()

        ineq_desc = (
            f"<b>Economic Inequality Analysis:</b> The Gini index of <b>{rep.gini_coefficient:.4f}</b> signifies "
            f"extreme storage concentration. In this dataset, the top <b>{rep.pct_files_for_50pct_storage:.2f}%</b> of files "
            f"occupy 50% of storage, and the top <b>{rep.pct_files_for_80pct_storage:.2f}%</b> occupy 80% of storage."
        )
        self.lbl_ineq_notes.set_markup(f"<span size='small' color='{TEXT_MUTED}'>{ineq_desc}</span>")

    def _render_tab_outliers(self) -> None:
        rep = self.report
        self.fig_outliers.clf()
        ax = self.fig_outliers.add_subplot(111)
        style_ax(ax)

        sizes = rep.raw_sizes
        log10_sizes = np.log10(np.maximum(sizes, 1.0))

        # Horizontal Boxplot
        bp = ax.boxplot(
            log10_sizes, vert=False, patch_artist=True,
            boxprops=dict(facecolor=ACCENT_BLUE, color=TEXT_COLOR, alpha=0.7),
            capprops=dict(color=TEXT_COLOR),
            whiskerprops=dict(color=TEXT_COLOR),
            flierprops=dict(marker='o', markersize=3, markerfacecolor=ACCENT_CORAL, alpha=0.5),
            medianprops=dict(color=ACCENT_AMBER, linewidth=2.5)
        )

        ticks = [0, 3, 6, 9, 12]
        tick_labels = ['1 B', '1 KB', '1 MB', '1 GB', '1 TB']
        ax.set_xticks(ticks)
        ax.set_xticklabels(tick_labels)
        ax.set_yticks([])
        ax.set_xlabel("File Size (Logarithmic)", fontsize=9, weight='bold')
        ax.set_title(
            f"Tukey Box & Whisker Plot (Mild Outliers: {rep.mild_outlier_count:,} | Extreme Outliers: {rep.extreme_outlier_count:,})",
            fontsize=10, weight='bold'
        )

        self.fig_outliers.tight_layout()
        self.canvas_outliers.draw()

        # Update outlier table
        self.store_outliers.clear()
        for it in rep.top_outliers:
            self.store_outliers.append([
                it['name'],
                it['human_size'],
                f"{it['modified_z']:.2f}",
                f"{it['pct_total']:.2f}%",
                it['path']
            ])

    def _render_tab_temporal(self) -> None:
        rep = self.report
        self.fig_temporal.clf()
        ax = self.fig_temporal.add_subplot(111)
        style_ax(ax)

        ages = rep.raw_ages_days
        sizes = rep.raw_sizes

        # Subsample for scatter plot if large
        n = len(ages)
        if n > 2000:
            idx = np.random.choice(n, 2000, replace=False)
            plot_ages = ages[idx]
            plot_sizes = sizes[idx]
        else:
            plot_ages = ages
            plot_sizes = sizes

        log_s = np.log10(np.maximum(plot_sizes, 1.0))
        ax.scatter(plot_ages, log_s, alpha=0.35, color=ACCENT_BLUE, s=16, edgecolors='none')

        # Fit trendline
        if n >= 5 and np.std(plot_ages) > 1e-4:
            try:
                poly = np.polyfit(plot_ages, log_s, 1)
                x_line = np.linspace(min(plot_ages), max(plot_ages), 100)
                y_line = np.polyval(poly, x_line)
                ax.plot(x_line, y_line, color=ACCENT_CORAL, linewidth=2.0,
                        label=f'Linear Fit (Pearson r = {rep.pearson_r:.3f}, p = {rep.pearson_p:.2e})')
                ax.legend(facecolor=CARD_BG, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=8)
            except Exception:
                pass

        ticks = [0, 3, 6, 9, 12]
        tick_labels = ['1 B', '1 KB', '1 MB', '1 GB', '1 TB']
        ax.set_yticks(ticks)
        ax.set_yticklabels(tick_labels)
        ax.set_xlabel("File Age (Days Since Modification)", fontsize=10, weight='bold')
        ax.set_ylabel("File Size", fontsize=10, weight='bold')
        ax.set_title(f"Temporal Decay: File Age vs. File Size (Spearman ρ = {rep.spearman_rho:.3f})", fontsize=11, weight='bold')

        self.fig_temporal.tight_layout()
        self.canvas_temporal.draw()

        # Update age bracket table
        self.store_age.clear()
        for b in rep.age_brackets:
            self.store_age.append([
                b['bracket'],
                f"{b['count']:,}",
                b['human_size'],
                f"{b['percent']:.1f}%"
            ])

    def _render_tab_extensions(self) -> None:
        rep = self.report
        self.fig_ext.clf()
        ax1 = self.fig_ext.add_subplot(121)
        ax2 = self.fig_ext.add_subplot(122)
        style_ax(ax1)
        style_ax(ax2)

        # Plot 1: Pareto bar chart of top 10 extensions
        top_exts = rep.top_extensions[:10]
        if top_exts:
            names = [e['extension'] for e in top_exts]
            sizes_mb = [e['bytes'] / (1024 * 1024) for e in top_exts]
            cum_pcts = [e['cumulative_percent'] for e in top_exts]

            x_pos = np.arange(len(names))
            ax1.bar(x_pos, sizes_mb, color=ACCENT_PURPLE, alpha=0.8, label='Volume (MiB)')
            ax1.set_xticks(x_pos)
            ax1.set_xticklabels(names, rotation=45, ha='right', fontsize=8)
            ax1.set_ylabel("Volume (MiB)", fontsize=9, weight='bold')
            ax1.set_title("Top File Extensions (Pareto)", fontsize=10, weight='bold')

            # Dual axis for cumulative percentage
            ax1_twin = ax1.twinx()
            ax1_twin.plot(x_pos, cum_pcts, color=ACCENT_AMBER, marker='o', linewidth=1.8, label='Cumulative %')
            ax1_twin.set_ylabel("Cumulative %", color=ACCENT_AMBER, fontsize=9)
            ax1_twin.tick_params(colors=ACCENT_AMBER, labelsize=8)
            ax1_twin.set_ylim(0, 105)
            ax1_twin.spines['right'].set_color(GRID_COLOR)

        # Plot 2: MIME Categories Donut Chart
        cats = rep.category_breakdown[:7]
        if cats:
            cat_names = [c['category'] for c in cats]
            cat_vals = [c['bytes'] for c in cats]
            palette = [ACCENT_BLUE, ACCENT_GREEN, ACCENT_CORAL, ACCENT_AMBER, ACCENT_PURPLE, '#38bdf8', '#fb7185']

            wedges, texts, autotexts = ax2.pie(
                cat_vals, labels=cat_names, autopct='%1.1f%%', startangle=140,
                colors=palette[:len(cats)],
                textprops=dict(color=TEXT_COLOR, fontsize=8),
                wedgeprops=dict(width=0.45, edgecolor=DARK_BG, linewidth=1.5)
            )
            for autotext in autotexts:
                autotext.set_color('#ffffff')
                autotext.set_weight('bold')
            ax2.set_title("Storage Volume by Category", fontsize=10, weight='bold')

        self.fig_ext.tight_layout()
        self.canvas_ext.draw()

        info_text = (
            f"<b>Information Entropy:</b> H(X) = <b>{rep.shannon_entropy_ext:.3f} bits</b> "
            f"(Pielou's Evenness J = {rep.normalized_entropy_ext:.3f}, Simpson Diversity D = {rep.simpson_diversity_ext:.3f}). "
            f"Total unique file extensions detected: <b>{rep.unique_extensions_count}</b>."
        )
        self.lbl_entropy_notes.set_markup(f"<span size='small' color='{TEXT_MUTED}'>{info_text}</span>")
