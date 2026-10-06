"""
Export dialog for StatDisk.
Exports statistical reports into LaTeX, Markdown, CSV, and JSON formats.
"""

import os
import json
import csv
from typing import Optional
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from statdisk.stats_engine import StatisticalReport
from statdisk.tree_model import format_bytes


class ExportDialog(Gtk.Dialog):
    """Dialog allowing users to export analytical results to various academic & data formats."""

    def __init__(self, parent: Gtk.Window, report: StatisticalReport, root_path: str):
        super().__init__(
            title="Export Statistical Analysis Report",
            transient_for=parent,
            flags=Gtk.DialogFlags.MODAL,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, "Export Now", Gtk.ResponseType.OK)
        )
        self.set_default_size(480, 260)
        self.report = report
        self.root_path = root_path

        box = self.get_content_area()
        box.set_spacing(12)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(16)
        box.set_margin_bottom(16)

        lbl = Gtk.Label()
        lbl.set_markup(
            "<span weight='bold' size='medium'>Export Analytical Results</span>\n"
            "<span size='small' color='#94a3b8'>Select export format and destination file:</span>"
        )
        lbl.set_xalign(0.0)
        box.pack_start(lbl, False, False, 0)

        grid = Gtk.Grid()
        grid.set_column_spacing(10)
        grid.set_row_spacing(10)
        box.pack_start(grid, True, True, 0)

        # Format selector
        lbl_fmt = Gtk.Label(label="Format:")
        lbl_fmt.set_xalign(0.0)
        grid.attach(lbl_fmt, 0, 0, 1, 1)

        self.combo_format = Gtk.ComboBoxText()
        self.combo_format.append('latex', "LaTeX Document (.tex) - Academic Paper Ready")
        self.combo_format.append('markdown', "Markdown Report (.md) - Clean GitHub Style")
        self.combo_format.append('csv', "CSV Dataset (.csv) - Raw Sizes & Outliers")
        self.combo_format.append('json', "JSON Data (.json) - Machine Readable")
        self.combo_format.set_active(0)
        self.combo_format.connect('changed', self._on_format_changed)
        grid.attach(self.combo_format, 1, 0, 1, 1)

        # Destination file chooser
        lbl_file = Gtk.Label(label="Save to:")
        lbl_file.set_xalign(0.0)
        grid.attach(lbl_file, 0, 1, 1, 1)

        self.file_chooser = Gtk.FileChooserButton(
            title="Save Report",
            action=Gtk.FileChooserAction.SAVE
        )
        default_dir = os.path.expanduser("~/Documents")
        if not os.path.exists(default_dir):
            default_dir = os.path.expanduser("~")
        self.file_chooser.set_current_folder(default_dir)
        self.file_chooser.set_current_name("storage_statistical_report.tex")
        grid.attach(self.file_chooser, 1, 1, 1, 1)

        box.show_all()

    def _on_format_changed(self, combo: Gtk.ComboBoxText) -> None:
        fmt = combo.get_active_id()
        base = "storage_statistical_report"
        if fmt == 'latex':
            self.file_chooser.set_current_name(f"{base}.tex")
        elif fmt == 'markdown':
            self.file_chooser.set_current_name(f"{base}.md")
        elif fmt == 'csv':
            self.file_chooser.set_current_name(f"{base}.csv")
        elif fmt == 'json':
            self.file_chooser.set_current_name(f"{base}.json")

    def execute_export(self) -> Optional[str]:
        target_path = self.file_chooser.get_filename()
        if not target_path:
            target_path = os.path.join(self.file_chooser.get_current_folder() or "/tmp", self.file_chooser.get_current_name())

        fmt = self.combo_format.get_active_id()
        rep = self.report

        try:
            if fmt == 'latex':
                self._export_latex(target_path, rep)
            elif fmt == 'markdown':
                self._export_markdown(target_path, rep)
            elif fmt == 'csv':
                self._export_csv(target_path, rep)
            elif fmt == 'json':
                self._export_json(target_path, rep)
            return target_path
        except Exception as e:
            return None

    def _export_latex(self, path: str, rep: StatisticalReport) -> None:
        tex = [
            r"\documentclass{article}",
            r"\usepackage[utf8]{inputenc}",
            r"\usepackage{booktabs}",
            r"\usepackage{amsmath}",
            r"\usepackage{geometry}",
            r"\geometry{margin=1in}",
            r"\title{Filesystem Storage Statistical Analysis Report}",
            r"\author{StatDisk Analyzer}",
            r"\date{\today}",
            r"\begin{document}",
            r"\maketitle",
            r"\section{Summary \& Central Tendency}",
            f"Analysis performed on scanned path: \\texttt{{{self.root_path}}}.\\\\",
            r"\begin{table}[h]",
            r"\centering",
            r"\begin{tabular}{llr}",
            r"\toprule",
            r"\textbf{Metric} & \textbf{Symbol} & \textbf{Value} \\",
            r"\midrule",
            f"Sample Size & $N$ & {rep.sample_size:,} files \\\\",
            f"Total Storage & $S_{{total}}$ & {format_bytes(rep.total_bytes)} \\\\",
            f"Arithmetic Mean & $\\bar{{x}}$ & {format_bytes(int(rep.mean))} \\\\",
            f"Geometric Mean & $\\bar{{x}}_{{geom}}$ & {format_bytes(int(rep.geometric_mean))} \\\\",
            f"Median (Q2) & $\\tilde{{x}}$ & {format_bytes(int(rep.median))} \\\\",
            f"Standard Deviation & $s$ & {format_bytes(int(rep.std_dev))} \\\\",
            f"Coefficient of Variation & $CV$ & {rep.cv:.3f} \\\\",
            f"Fisher-Pearson Skewness & $g_1$ & {rep.skewness:.3f} \\\\",
            f"Excess Kurtosis & $g_2$ & {rep.kurtosis:.3f} \\\\",
            f"Gini Coefficient & $G$ & {rep.gini_coefficient:.4f} \\\\",
            f"Shannon Entropy & $H(X)$ & {rep.shannon_entropy_ext:.3f} bits \\\\",
            r"\bottomrule",
            r"\end{tabular}",
            r"\caption{Descriptive statistics and distribution moments.}",
            r"\end{table}",
            r"\section{Storage Inequality \& Pareto Analysis}",
            f"The storage Gini coefficient is calculated as $G = {rep.gini_coefficient:.4f}$, demonstrating substantial inequality in space consumption.",
            f"Empirical Pareto check shows that the top {rep.pct_files_for_80pct_storage:.2f}\\% of files consume 80.0\\% of the total disk allocation.",
            r"\end{document}"
        ]
        with open(path, 'w', encoding='utf-8') as f:
            f.write("\n".join(tex))

    def _export_markdown(self, path: str, rep: StatisticalReport) -> None:
        md = [
            f"# StatDisk Storage Analysis Report",
            f"**Scanned Directory:** `{self.root_path}`  ",
            f"**Sample Size ($N$):** {rep.sample_size:,} files | **Directories:** {rep.total_directories:,}  ",
            f"**Total Volume:** {format_bytes(rep.total_bytes)} ({rep.total_bytes:,} bytes)\n",
            "## 1. Classical & Robust Moments",
            "| Statistic | Notation | Value | Notes |",
            "| :--- | :---: | :--- | :--- |",
            f"| Arithmetic Mean | $\\bar{{x}}$ | {format_bytes(int(rep.mean))} | {rep.mean:.1f} B |",
            f"| Geometric Mean | $\\bar{{x}}_{{geom}}$ | {format_bytes(int(rep.geometric_mean))} | Scale invariant |",
            f"| Median | $\\tilde{{x}}$ | {format_bytes(int(rep.median))} | 50th percentile |",
            f"| Standard Deviation | $s$ | {format_bytes(int(rep.std_dev))} | Sample dispersion |",
            f"| Interquartile Range | $IQR$ | {format_bytes(int(rep.iqr))} | $Q_3 - Q_1$ |",
            f"| Median Absolute Dev | $MAD$ | {format_bytes(int(rep.mad))} | Robust scale |",
            f"| Skewness | $g_1$ | {rep.skewness:.4f} | {'Right-skewed' if rep.skewness > 0 else 'Left-skewed'} |",
            f"| Excess Kurtosis | $g_2$ | {rep.kurtosis:.4f} | Heavy tailed |",
            f"| Gini Coefficient | $G$ | {rep.gini_coefficient:.4f} | 0 = Equal, 1 = Extreme |",
            f"| Shannon Entropy | $H(X)$ | {rep.shannon_entropy_ext:.3f} bits | Extension diversity |\n",
            "## 2. Pareto Storage Inequality",
            f"- **Top 50% Storage:** Consumed by the largest **{rep.pct_files_for_50pct_storage:.2f}%** of files.",
            f"- **Top 80% Storage:** Consumed by the largest **{rep.pct_files_for_80pct_storage:.2f}%** of files.",
            f"- **Top 90% Storage:** Consumed by the largest **{rep.pct_files_for_90pct_storage:.2f}%** of files.\n",
            "## 3. Parametric Distribution Fit",
            f"- Fitted Log-Normal: $\\mu = {rep.lognorm_mu:.3f}$, $\\sigma = {rep.lognorm_sigma:.3f}$",
            f"- Kolmogorov-Smirnov Test: $D = {rep.ks_stat:.4f}, p = {rep.ks_pvalue:.4e}$",
            f"- Pareto Heavy-Tail Exponent $\\hat{{\\alpha}} = {rep.pareto_alpha:.3f}$\n",
            "## 4. Top Outliers (Tukey & Modified Z-Score)",
            "| File Name | Size | Mod Z-Score | Share % | Path |",
            "| :--- | :--- | :---: | :---: | :--- |"
        ]
        for it in rep.top_outliers[:15]:
            md.append(f"| `{it['name']}` | {it['human_size']} | {it['modified_z']:.2f} | {it['pct_total']:.2f}% | `{it['path']}` |")

        with open(path, 'w', encoding='utf-8') as f:
            f.write("\n".join(md))

    def _export_csv(self, path: str, rep: StatisticalReport) -> None:
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['file_name', 'size_bytes', 'modified_z_score', 'pct_total', 'path'])
            for it in rep.top_outliers:
                writer.writerow([it['name'], it['size'], f"{it['modified_z']:.4f}", f"{it['pct_total']:.4f}", it['path']])

    def _export_json(self, path: str, rep: StatisticalReport) -> None:
        data = {
            'scanned_path': self.root_path,
            'sample_size': rep.sample_size,
            'total_directories': rep.total_directories,
            'total_bytes': rep.total_bytes,
            'central_tendency': {
                'mean': rep.mean,
                'geometric_mean': rep.geometric_mean,
                'harmonic_mean': rep.harmonic_mean,
                'median': rep.median,
            },
            'dispersion': {
                'variance': rep.variance,
                'std_dev': rep.std_dev,
                'cv': rep.cv,
                'iqr': rep.iqr,
                'mad': rep.mad,
                'skewness': rep.skewness,
                'kurtosis': rep.kurtosis
            },
            'inequality': {
                'gini_coefficient': rep.gini_coefficient,
                'pct_files_for_50pct_storage': rep.pct_files_for_50pct_storage,
                'pct_files_for_80pct_storage': rep.pct_files_for_80pct_storage,
                'pct_files_for_90pct_storage': rep.pct_files_for_90pct_storage
            },
            'information_theory': {
                'shannon_entropy_ext_bits': rep.shannon_entropy_ext,
                'normalized_entropy': rep.normalized_entropy_ext,
                'simpson_diversity': rep.simpson_diversity_ext,
                'unique_extensions': rep.unique_extensions_count
            },
            'parametric_fit': {
                'lognorm_mu': rep.lognorm_mu,
                'lognorm_sigma': rep.lognorm_sigma,
                'ks_stat': rep.ks_stat,
                'ks_pvalue': rep.ks_pvalue,
                'pareto_alpha': rep.pareto_alpha
            },
            'percentiles': rep.percentiles,
            'top_outliers': rep.top_outliers[:50]
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
