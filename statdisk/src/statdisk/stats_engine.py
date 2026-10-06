"""
Comprehensive Statistical Analysis Engine for StatDisk.
Provides rigorous descriptive, inferential, information-theoretic,
and inequality metrics tailored for statistics and data science.
"""

import os
import math
import time
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import scipy.stats as stats

from statdisk.tree_model import format_bytes, EXT_CATEGORIES


class StatisticalReport:
    """Holds computed statistical analysis results."""
    def __init__(self):
        self.sample_size: int = 0
        self.total_directories: int = 0
        self.total_bytes: int = 0
        self.scan_duration: float = 0.0

        # Central Tendency
        self.mean: float = 0.0
        self.geometric_mean: float = 0.0
        self.harmonic_mean: float = 0.0
        self.median: float = 0.0
        self.mode_val: float = 0.0

        # Dispersion
        self.variance: float = 0.0
        self.std_dev: float = 0.0
        self.cv: float = 0.0
        self.iqr: float = 0.0
        self.mad: float = 0.0
        self.quartile_dispersion: float = 0.0

        # Moments & Shape
        self.skewness: float = 0.0
        self.kurtosis: float = 0.0

        # Percentiles
        self.percentiles: Dict[str, float] = {}
        self.min_val: int = 0
        self.max_val: int = 0

        # Information Theory & Diversity
        self.shannon_entropy_ext: float = 0.0
        self.normalized_entropy_ext: float = 0.0
        self.simpson_diversity_ext: float = 0.0
        self.shannon_entropy_bytes: float = 0.0
        self.unique_extensions_count: int = 0

        # Storage Inequality & Economics
        self.gini_coefficient: float = 0.0
        self.lorenz_u: np.ndarray = np.array([])
        self.lorenz_v: np.ndarray = np.array([])
        self.pct_files_for_50pct_storage: float = 0.0
        self.pct_files_for_80pct_storage: float = 0.0
        self.pct_files_for_90pct_storage: float = 0.0

        # Distribution Fitting (Log-Normal & Pareto)
        self.lognorm_mu: float = 0.0
        self.lognorm_sigma: float = 0.0
        self.ks_stat: float = 0.0
        self.ks_pvalue: float = 0.0
        self.pareto_alpha: float = 0.0

        # Outlier Detection
        self.tukey_upper_mild: float = 0.0
        self.tukey_upper_extreme: float = 0.0
        self.mild_outlier_count: int = 0
        self.extreme_outlier_count: int = 0
        self.top_outliers: List[Dict[str, Any]] = []

        # Extension Breakdown
        self.top_extensions: List[Dict[str, Any]] = []
        self.category_breakdown: List[Dict[str, Any]] = []

        # Temporal Analysis
        self.pearson_r: float = 0.0
        self.pearson_p: float = 0.0
        self.spearman_rho: float = 0.0
        self.spearman_p: float = 0.0
        self.age_brackets: List[Dict[str, Any]] = []

        # Raw arrays for plotting
        self.raw_sizes: np.ndarray = np.array([])
        self.raw_ages_days: np.ndarray = np.array([])


class StatsEngine:
    """Computes high-precision statistics on filesystem dataset."""

    @staticmethod
    def analyze(sizes_list: List[int], mtimes_list: List[float],
                extensions_list: List[str], paths_list: List[str],
                total_dirs: int, scan_duration: float = 0.0) -> StatisticalReport:
        rep = StatisticalReport()
        rep.total_directories = total_dirs
        rep.scan_duration = scan_duration

        if not sizes_list:
            return rep

        sizes = np.array(sizes_list, dtype=np.float64)
        n = len(sizes)
        rep.sample_size = n
        rep.total_bytes = int(np.sum(sizes))
        rep.min_val = int(np.min(sizes))
        rep.max_val = int(np.max(sizes))
        rep.raw_sizes = sizes

        # 1. Central Tendency
        rep.mean = float(np.mean(sizes))
        rep.median = float(np.median(sizes))

        # Geometric & Harmonic Means (protecting zeros)
        pos_sizes = np.maximum(sizes, 1.0)
        rep.geometric_mean = float(np.exp(np.mean(np.log(pos_sizes))))
        rep.harmonic_mean = float(n / np.sum(1.0 / pos_sizes))

        # 2. Dispersion & Spread
        if n > 1:
            rep.variance = float(np.var(sizes, ddof=1))
            rep.std_dev = float(np.std(sizes, ddof=1))
            rep.cv = float(rep.std_dev / rep.mean) if rep.mean > 0 else 0.0
            rep.skewness = float(stats.skew(sizes, bias=False))
            rep.kurtosis = float(stats.kurtosis(sizes, bias=False))
        else:
            rep.variance = 0.0
            rep.std_dev = 0.0
            rep.cv = 0.0
            rep.skewness = 0.0
            rep.kurtosis = 0.0

        rep.mad = float(np.median(np.abs(sizes - rep.median)))

        # 3. Percentiles
        pct_keys = [1, 5, 10, 25, 50, 75, 90, 95, 99, 99.9]
        pct_vals = np.percentile(sizes, pct_keys)
        for k, v in zip(pct_keys, pct_vals):
            rep.percentiles[f"P{k}"] = float(v)

        q1 = rep.percentiles["P25"]
        q3 = rep.percentiles["P75"]
        rep.iqr = float(q3 - q1)
        if (q3 + q1) > 0:
            rep.quartile_dispersion = float(rep.iqr / (q3 + q1))

        # 4. Storage Inequality (Lorenz Curve & Gini Coefficient)
        sorted_sizes = np.sort(sizes)
        cum_sizes = np.cumsum(sorted_sizes)
        tot = cum_sizes[-1] if len(cum_sizes) > 0 else 0.0

        if tot > 0:
            # Subsample Lorenz curve to max 1000 points for smooth plotting & speed
            num_lorenz_pts = min(1000, n + 1)
            indices = np.linspace(0, n - 1, num_lorenz_pts, dtype=int)
            rep.lorenz_u = np.linspace(0.0, 1.0, num_lorenz_pts)
            rep.lorenz_v = np.zeros(num_lorenz_pts)
            rep.lorenz_v[1:] = cum_sizes[indices[1:]] / tot

            # Gini calculation via trapezoidal rule
            u = rep.lorenz_u
            v = rep.lorenz_v
            rep.gini_coefficient = float(1.0 - np.sum((u[1:] - u[:-1]) * (v[1:] + v[:-1])))

            # Pareto 50%, 80%, 90% space check
            idx_50 = np.searchsorted(cum_sizes, 0.50 * tot)
            idx_20 = np.searchsorted(cum_sizes, 0.20 * tot)
            idx_10 = np.searchsorted(cum_sizes, 0.10 * tot)

            rep.pct_files_for_50pct_storage = float((n - idx_50) / n * 100.0)
            rep.pct_files_for_80pct_storage = float((n - idx_20) / n * 100.0)
            rep.pct_files_for_90pct_storage = float((n - idx_10) / n * 100.0)

        # 5. Distribution Fitting (Log-Normal & Pareto)
        log_sizes = np.log(pos_sizes)
        rep.lognorm_mu = float(np.mean(log_sizes))
        rep.lognorm_sigma = float(np.std(log_sizes, ddof=1)) if n > 1 else 1.0

        # Kolmogorov-Smirnov test for log-normality
        if n >= 10:
            subsample = log_sizes if n <= 2000 else np.random.choice(log_sizes, 2000, replace=False)
            res = stats.kstest(subsample, 'norm', args=(rep.lognorm_mu, rep.lognorm_sigma))
            rep.ks_stat = float(res.statistic)
            rep.ks_pvalue = float(res.pvalue)

        # Pareto Hill Estimator for heavy tail
        if n >= 20:
            tail_threshold = rep.percentiles["P90"]
            tail_sizes = sizes[sizes >= tail_threshold]
            if len(tail_sizes) > 1 and tail_threshold > 0:
                rep.pareto_alpha = float(1.0 + len(tail_sizes) / np.sum(np.log(tail_sizes / tail_threshold)))

        # 6. Outlier Analysis (Tukey's Fences & Modified Z-scores)
        rep.tukey_upper_mild = float(q3 + 1.5 * rep.iqr)
        rep.tukey_upper_extreme = float(q3 + 3.0 * rep.iqr)

        mild_mask = sizes > rep.tukey_upper_mild
        extreme_mask = sizes > rep.tukey_upper_extreme
        rep.mild_outlier_count = int(np.sum(mild_mask))
        rep.extreme_outlier_count = int(np.sum(extreme_mask))

        # Identify top 50 largest outlier files with Modified Z-Score
        top_k = min(50, n)
        largest_indices = np.argsort(sizes)[::-1][:top_k]

        mad_denom = rep.mad if rep.mad > 0 else (rep.std_dev if rep.std_dev > 0 else 1.0)
        for idx in largest_indices:
            sz = int(sizes[idx])
            mod_z = float(0.6745 * (sz - rep.median) / mad_denom)
            path_str = paths_list[idx] if idx < len(paths_list) else ""
            rep.top_outliers.append({
                'path': path_str,
                'name': os.path.basename(path_str),
                'size': sz,
                'human_size': format_bytes(sz),
                'modified_z': mod_z,
                'pct_total': float(sz / rep.total_bytes * 100.0) if rep.total_bytes > 0 else 0.0
            })

        # 7. Extension Breakdown & Shannon Information Entropy
        ext_counts: Dict[str, int] = {}
        ext_bytes: Dict[str, int] = {}
        cat_bytes: Dict[str, int] = {}
        cat_counts: Dict[str, int] = {}

        for i in range(n):
            e = extensions_list[i] if extensions_list[i] else '[No Ext]'
            sz = int(sizes[i])
            ext_counts[e] = ext_counts.get(e, 0) + 1
            ext_bytes[e] = ext_bytes.get(e, 0) + sz

            cat = EXT_CATEGORIES.get(e, 'Other')
            cat_bytes[cat] = cat_bytes.get(cat, 0) + sz
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        rep.unique_extensions_count = len(ext_counts)

        # Shannon Entropy H = -sum(p * log2(p))
        h_ext = 0.0
        simpson = 0.0
        for cnt in ext_counts.values():
            p = cnt / n
            if p > 0:
                h_ext -= p * math.log2(p)
                simpson += p * p
        rep.shannon_entropy_ext = float(h_ext)
        rep.simpson_diversity_ext = float(1.0 - simpson)

        if rep.unique_extensions_count > 1:
            rep.normalized_entropy_ext = float(h_ext / math.log2(rep.unique_extensions_count))

        # Byte allocation entropy
        if rep.total_bytes > 0:
            h_bytes = 0.0
            for b in ext_bytes.values():
                w = b / rep.total_bytes
                if w > 0:
                    h_bytes -= w * math.log2(w)
            rep.shannon_entropy_bytes = float(h_bytes)

        # Top extensions
        sorted_exts = sorted(ext_bytes.items(), key=lambda kv: kv[1], reverse=True)
        running_cum_bytes = 0
        for ext_name, b_val in sorted_exts[:20]:
            running_cum_bytes += b_val
            pct = (b_val / rep.total_bytes * 100.0) if rep.total_bytes > 0 else 0.0
            cum_pct = (running_cum_bytes / rep.total_bytes * 100.0) if rep.total_bytes > 0 else 0.0
            rep.top_extensions.append({
                'extension': ext_name,
                'bytes': b_val,
                'human_size': format_bytes(b_val),
                'count': ext_counts.get(ext_name, 0),
                'percent': pct,
                'cumulative_percent': cum_pct
            })

        # Category breakdown
        for cat_name, b_val in sorted(cat_bytes.items(), key=lambda kv: kv[1], reverse=True):
            pct = (b_val / rep.total_bytes * 100.0) if rep.total_bytes > 0 else 0.0
            rep.category_breakdown.append({
                'category': cat_name,
                'bytes': b_val,
                'human_size': format_bytes(b_val),
                'count': cat_counts.get(cat_name, 0),
                'percent': pct
            })

        # 8. Temporal & Correlation Analysis (Age vs Size)
        now = time.time()
        ages_days = np.array([max(0.0, (now - mt) / 86400.0) for mt in mtimes_list], dtype=np.float64)
        rep.raw_ages_days = ages_days

        if n >= 3 and np.std(ages_days) > 1e-9 and np.std(log_sizes) > 1e-9:
            try:
                pr, pp = stats.pearsonr(ages_days, log_sizes)
                rep.pearson_r = float(pr) if not math.isnan(pr) else 0.0
                rep.pearson_p = float(pp) if not math.isnan(pp) else 1.0
            except Exception:
                pass

            try:
                sr, sp = stats.spearmanr(ages_days, sizes)
                rep.spearman_rho = float(sr) if not math.isnan(sr) else 0.0
                rep.spearman_p = float(sp) if not math.isnan(sp) else 1.0
            except Exception:
                pass

        # Age brackets
        brackets = [
            ('< 7 days', 0.0, 7.0),
            ('7 - 30 days', 7.0, 30.0),
            ('1 - 6 months', 30.0, 180.0),
            ('6 - 12 months', 180.0, 365.0),
            ('1 - 3 years', 365.0, 365.0 * 3),
            ('> 3 years', 365.0 * 3, float('inf')),
        ]

        for label, low, high in brackets:
            mask = (ages_days >= low) & (ages_days < high)
            b_cnt = int(np.sum(mask))
            b_bytes = int(np.sum(sizes[mask]))
            pct = (b_bytes / rep.total_bytes * 100.0) if rep.total_bytes > 0 else 0.0
            rep.age_brackets.append({
                'bracket': label,
                'count': b_cnt,
                'bytes': b_bytes,
                'human_size': format_bytes(b_bytes),
                'percent': pct
            })

        return rep
