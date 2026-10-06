"""
MintStatLab - Matplotlib Visualization Engine
Generates publication-quality statistical figures adhering to Linux Mint's dark teal palette.
"""

from typing import Dict, List, Any
import numpy as np
import scipy.stats as stats
import matplotlib
matplotlib.use('GTK3Agg')
from matplotlib.figure import Figure

# Color Palette (Tokyo Night / Mint-Y-Dark-Teal inspired)
BG_COLOR = "#16161e"
SURFACE_COLOR = "#1a1b26"
GRID_COLOR = "#292e42"
TEXT_COLOR = "#c0caf5"
ACCENT_TEAL = "#7dcfff"
ACCENT_CYAN = "#73daca"
ACCENT_BLUE = "#7aa2f7"
ACCENT_GREEN = "#9ece6a"
ACCENT_ORANGE = "#ff9e64"
ACCENT_PURPLE = "#bb9af7"
ACCENT_RED = "#f7768e"
ACCENT_GOLD = "#e0af68"


def apply_dark_theme(ax):
    """Applies cohesive dark styling to an individual matplotlib axis."""
    ax.set_facecolor(SURFACE_COLOR)
    ax.tick_params(colors=TEXT_COLOR, labelsize=9)
    ax.grid(True, linestyle="--", linewidth=0.5, color=GRID_COLOR, alpha=0.7)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
        spine.set_linewidth(0.8)
    ax.xaxis.label.set_color(TEXT_COLOR)
    ax.yaxis.label.set_color(TEXT_COLOR)
    ax.title.set_color(ACCENT_TEAL)
    ax.title.set_fontweight("bold")
    ax.title.set_fontsize(11)


def render_inequality_and_dist(fig: Figure, gini_ram: float, p_ram: np.ndarray, lorenz_ram: np.ndarray,
                               gini_cpu: float, p_cpu: np.ndarray, lorenz_cpu: np.ndarray,
                               pos_ram: np.ndarray, fit_info: Dict[str, Any]):
    """Renders the Lorenz Inequality Curve and the Empirical Heavy-Tail Memory Distribution."""
    fig.clear()
    fig.patch.set_facecolor(BG_COLOR)

    ax1 = fig.add_subplot(1, 2, 1)
    apply_dark_theme(ax1)

    # Lorenz Curves
    ax1.plot([0, 1], [0, 1], color=TEXT_COLOR, linestyle=":", linewidth=1.5, label="Line of Perfect Equality (G=0)")
    ax1.plot(p_ram, lorenz_ram, color=ACCENT_CYAN, linewidth=2.5, label=f"RAM Allocation (G = {gini_ram:.3f})")
    ax1.fill_between(p_ram, p_ram, lorenz_ram, color=ACCENT_CYAN, alpha=0.15)

    if len(p_cpu) > 1 and np.max(lorenz_cpu) > 0:
        ax1.plot(p_cpu, lorenz_cpu, color=ACCENT_ORANGE, linewidth=2.0, linestyle="--", label=f"CPU Allocation (G = {gini_cpu:.3f})")
        ax1.fill_between(p_cpu, p_cpu, lorenz_cpu, color=ACCENT_ORANGE, alpha=0.10)

    # 80/20 Pareto mark
    ax1.scatter([0.8], [0.2], color=ACCENT_RED, s=40, zorder=5)
    ax1.annotate("Pareto 80/20", xy=(0.8, 0.2), xytext=(0.55, 0.28),
                 arrowprops=dict(arrowstyle="->", color=ACCENT_RED, lw=1.0),
                 color=ACCENT_RED, fontsize=8, fontweight="bold")

    ax1.set_title("System Resource Lorenz Curve & Inequality")
    ax1.set_xlabel("Cumulative Proportion of Processes")
    ax1.set_ylabel("Cumulative Share of Resource Volume")
    ax1.set_xlim(0, 1)
    ax1.set_ylim(0, 1)
    ax1.legend(loc="upper left", facecolor=BG_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=8)

    # Subplot 2: Heavy-Tail Memory Histogram & Fitted Distributions
    ax2 = fig.add_subplot(1, 2, 2)
    apply_dark_theme(ax2)

    if len(pos_ram) > 5:
        log_ram = np.log10(pos_ram)
        counts, bins, _ = ax2.hist(log_ram, bins=25, density=True, color=ACCENT_BLUE, alpha=0.45,
                                  edgecolor=ACCENT_TEAL, linewidth=0.8, label="Empirical Memory")

        # Fitted Log-Normal curve (in log10 space)
        if fit_info.get("fitted"):
            ln = fit_info["lognormal"]
            mu, sigma = ln["mu"], ln["sigma"]
            # Density in log10 space via Jacobian transform: f_Y(y) = f_X(10^y) * 10^y * ln(10)
            x_vals = np.linspace(min(bins), max(bins), 150)
            linear_x = 10 ** x_vals
            pdf_linear = stats.lognorm.pdf(linear_x, s=sigma, scale=np.exp(mu))
            pdf_log = pdf_linear * linear_x * np.log(10)
            ax2.plot(x_vals, pdf_log, color=ACCENT_GREEN, linewidth=2.2,
                     label=f"Log-Normal MLE (μ={mu:.1f}, σ={sigma:.2f})")

            # KS Goodness of fit annotation
            ax2.text(0.04, 0.92, f"KS D={ln['ks_statistic']:.3f} (p={ln['p_value']:.3f})\nBest Model: {fit_info.get('best_model')}",
                     transform=ax2.transAxes, color=ACCENT_GOLD, fontsize=8,
                     bbox=dict(boxstyle="round,pad=0.3", facecolor=SURFACE_COLOR, edgecolor=GRID_COLOR))

        ax2.set_title("Process Memory Density (Log10 Scale)")
        ax2.set_xlabel("log₁₀(RSS Memory in MiB)")
        ax2.set_ylabel("Probability Density")
        ax2.legend(loc="upper right", facecolor=BG_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=8)
    else:
        ax2.text(0.5, 0.5, "Collecting Memory Samples...", ha="center", va="center", color=TEXT_COLOR)

    fig.tight_layout()


def render_kaplan_meier_survival(fig: Figure, km_user: Dict[str, Any], km_daemon: Dict[str, Any]):
    """Renders Kaplan-Meier survival curves and cumulative hazard rate."""
    fig.clear()
    fig.patch.set_facecolor(BG_COLOR)

    ax1 = fig.add_subplot(2, 1, 1)
    apply_dark_theme(ax1)

    # User Applications curve
    if len(km_user.get("t", [])) > 1:
        t_u_hr = km_user["t"] / 3600.0
        ax1.step(t_u_hr, km_user["s"], where="post", color=ACCENT_CYAN, linewidth=2.2, label="User Applications")
        ax1.fill_between(t_u_hr, km_user["ci_lower"], km_user["ci_upper"], step="post", color=ACCENT_CYAN, alpha=0.15)
        # Median line
        med_u = km_user.get("median_survival_seconds", 0) / 3600.0
        ax1.axvline(med_u, color=ACCENT_CYAN, linestyle=":", alpha=0.7, label=f"User Median: {med_u:.2f} hrs")

    # System Daemons curve
    if len(km_daemon.get("t", [])) > 1:
        t_d_hr = km_daemon["t"] / 3600.0
        ax1.step(t_d_hr, km_daemon["s"], where="post", color=ACCENT_PURPLE, linewidth=2.0, linestyle="--", label="System Daemons")
        ax1.fill_between(t_d_hr, km_daemon["ci_lower"], km_daemon["ci_upper"], step="post", color=ACCENT_PURPLE, alpha=0.12)
        med_d = km_daemon.get("median_survival_seconds", 0) / 3600.0
        ax1.axvline(med_d, color=ACCENT_PURPLE, linestyle=":", alpha=0.7, label=f"Daemon Median: {med_d:.2f} hrs")

    ax1.set_title("Non-Parametric Kaplan-Meier Process Survival Function Ŝ(t)")
    ax1.set_ylabel("Survival Probability Ŝ(t)")
    ax1.set_ylim(-0.02, 1.05)
    ax1.legend(loc="upper right", facecolor=BG_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=8)

    # Subplot 2: Cumulative Hazard Rate H(t)
    ax2 = fig.add_subplot(2, 1, 2)
    apply_dark_theme(ax2)

    if len(km_user.get("t", [])) > 1:
        ax2.step(km_user["t"] / 3600.0, km_user["hazard"], where="post", color=ACCENT_CYAN, linewidth=1.8, label="User Hazard H(t)")
    if len(km_daemon.get("t", [])) > 1:
        ax2.step(km_daemon["t"] / 3600.0, km_daemon["hazard"], where="post", color=ACCENT_PURPLE, linewidth=1.8, linestyle="--", label="Daemon Hazard H(t)")

    ax2.set_title("Empirical Cumulative Hazard Function Ĥ(t) = -ln(Ŝ(t))")
    ax2.set_xlabel("Elapsed Process Lifespan (Hours)")
    ax2.set_ylabel("Cumulative Hazard")
    ax2.legend(loc="upper left", facecolor=BG_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=8)

    fig.tight_layout()


def render_stochastic_arrivals(fig: Figure, point_res: Dict[str, Any]):
    """Renders inter-arrival intervals and testing against the Poisson/Exponential hypothesis."""
    fig.clear()
    fig.patch.set_facecolor(BG_COLOR)

    if not point_res.get("valid"):
        ax = fig.add_subplot(1, 1, 1)
        apply_dark_theme(ax)
        ax.text(0.5, 0.5, f"Collecting Event Timestamps...\n({point_res.get('reason', 'Buffering')})",
                ha="center", va="center", color=TEXT_COLOR, fontsize=12)
        return

    intervals = point_res["intervals"]
    mean_dt = point_res["mean_interarrival_sec"]
    lambda_rate = point_res["lambda_rate_hz"]

    # Subplot 1: Inter-arrival Histogram vs Theoretical Exponential PDF
    ax1 = fig.add_subplot(1, 2, 1)
    apply_dark_theme(ax1)

    # Clip extreme outliers for visual clarity (95th percentile)
    clip_val = float(np.percentile(intervals, 95))
    filtered_int = intervals[intervals <= clip_val]
    
    ax1.hist(filtered_int, bins=25, density=True, color=ACCENT_GREEN, alpha=0.45,
             edgecolor=ACCENT_CYAN, linewidth=0.8, label="Empirical Δt")

    t_curve = np.linspace(0, clip_val, 150)
    exp_pdf = lambda_rate * np.exp(-lambda_rate * t_curve)
    ax1.plot(t_curve, exp_pdf, color=ACCENT_ORANGE, linewidth=2.2,
             label=f"Exp(λ={lambda_rate:.2f}/s) Theoretical")

    ax1.set_title("Journal Event Inter-Arrival Distribution")
    ax1.set_xlabel("Inter-Arrival Time Δt (seconds)")
    ax1.set_ylabel("Density f(Δt)")
    ax1.legend(loc="upper right", facecolor=BG_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=8)

    # Subplot 2: Q-Q Plot against Exponential Distribution
    ax2 = fig.add_subplot(1, 2, 2)
    apply_dark_theme(ax2)

    # Exponential quantiles
    sorted_int = np.sort(intervals)
    n = len(sorted_int)
    prob_points = (np.arange(1, n + 1) - 0.5) / n
    theoretical_quantiles = stats.expon.ppf(prob_points, scale=mean_dt)

    ax2.scatter(theoretical_quantiles, sorted_int, color=ACCENT_CYAN, s=12, alpha=0.7, label="Sample vs Theoretical")
    max_q = min(np.max(theoretical_quantiles), np.max(sorted_int))
    ax2.plot([0, max_q], [0, max_q], color=ACCENT_RED, linestyle="--", linewidth=1.5, label="Identity Line (y=x)")

    # Status box
    regime_text = f"Regime: {point_res.get('regime')}\nCV: {point_res.get('cv'):.2f} (Poisson=1.00)\nKS Test p-val: {point_res.get('ks_p_value'):.3f}"
    ax2.text(0.04, 0.88, regime_text, transform=ax2.transAxes, color=ACCENT_GOLD, fontsize=8,
             bbox=dict(boxstyle="round,pad=0.3", facecolor=SURFACE_COLOR, edgecolor=GRID_COLOR))

    ax2.set_title("Exponential Q-Q Plot (Poisson Arrival Test)")
    ax2.set_xlabel("Theoretical Quantiles (Exp)")
    ax2.set_ylabel("Empirical Quantiles (Seconds)")
    ax2.legend(loc="lower right", facecolor=BG_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=8)

    fig.tight_layout()


def render_drift_and_acf(fig: Figure, ram_series: List[float], reg: Dict[str, Any]):
    """Renders Time Series OLS Drift Regression (Memory Leak Detection) and ACF."""
    fig.clear()
    fig.patch.set_facecolor(BG_COLOR)

    if not reg.get("valid"):
        ax = fig.add_subplot(1, 1, 1)
        apply_dark_theme(ax)
        ax.text(0.5, 0.5, f"Sampling Time Series Window...\n({reg.get('reason', 'Need more samples')})",
                ha="center", va="center", color=TEXT_COLOR, fontsize=12)
        return

    n = len(ram_series)
    t = np.arange(n)

    # Subplot 1: OLS Regression
    ax1 = fig.add_subplot(1, 2, 1)
    apply_dark_theme(ax1)

    ax1.plot(t, ram_series, color=ACCENT_CYAN, linewidth=1.8, label="Total Memory (MiB)")
    ax1.plot(t, reg["fitted_line"], color=ACCENT_ORANGE, linestyle="--", linewidth=2.2,
             label=f"OLS Trend: y = {reg['intercept']:.1f} + ({reg['slope']:.3f})·t")

    status_color = ACCENT_RED if "SIGNIFICANT" in reg["leak_status"] else ACCENT_GREEN
    ax1.text(0.04, 0.88, f"Status: {reg['leak_status']}\nSlope β₁: {reg['slope']:.4f} MiB/s (p={reg['p_value']:.4f})\nFit R²: {reg['r2']:.3f}",
             transform=ax1.transAxes, color=status_color, fontsize=8, fontweight="bold",
             bbox=dict(boxstyle="round,pad=0.3", facecolor=SURFACE_COLOR, edgecolor=GRID_COLOR))

    ax1.set_title("Temporal Drift & Memory Leak Regression")
    ax1.set_xlabel("Observation Sample Index t (seconds)")
    ax1.set_ylabel("System Memory (MiB)")
    ax1.legend(loc="lower right", facecolor=BG_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=8)

    # Subplot 2: Autocorrelation Function (ACF)
    ax2 = fig.add_subplot(1, 2, 2)
    apply_dark_theme(ax2)

    lags = reg["lags"]
    acf = reg["acf"]
    ci = reg["bartlett_ci"]

    # Stem plot
    markerline, stemlines, baseline = ax2.stem(lags, acf)
    markerline.set_markerfacecolor(ACCENT_TEAL)
    markerline.set_markeredgecolor(ACCENT_CYAN)
    markerline.set_markersize(5)
    stemlines.set_color(ACCENT_BLUE)
    stemlines.set_linewidth(1.2)
    baseline.set_color(GRID_COLOR)

    # Bartlett 95% confidence bands
    ax2.axhline(ci, color=ACCENT_RED, linestyle=":", linewidth=1.2, label=f"Bartlett 95% CI (±{ci:.2f})")
    ax2.axhline(-ci, color=ACCENT_RED, linestyle=":", linewidth=1.2)
    ax2.fill_between(lags, -ci, ci, color=ACCENT_RED, alpha=0.08)

    ax2.set_title("Autocorrelation Function (ACF)")
    ax2.set_xlabel("Lag k")
    ax2.set_ylabel("Autocorrelation ρ_k")
    ax2.set_ylim(-1.05, 1.05)
    ax2.legend(loc="upper right", facecolor=BG_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=8)

    fig.tight_layout()
