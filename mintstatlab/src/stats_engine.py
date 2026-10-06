"""
MintStatLab - Statistical Computing Engine
Calculates inequality metrics (Gini, Lorenz), heavy-tail distributions (Log-Normal, Pareto),
Kaplan-Meier survival estimation, Poisson point process modeling, and OLS drift regression.
"""

import math
from typing import Dict, List, Tuple, Any, Optional
import numpy as np
import scipy.stats as stats


def compute_distribution_moments(data: np.ndarray) -> Dict[str, float]:
    """Calculates comprehensive statistical moments and robust dispersion metrics."""
    if len(data) == 0:
        return {}
    
    data = np.asarray(data, dtype=float)
    n = len(data)
    mean_val = float(np.mean(data))
    std_val = float(np.std(data, ddof=1)) if n > 1 else 0.0
    var_val = float(np.var(data, ddof=1)) if n > 1 else 0.0
    
    # Percentiles
    p1, p5, p10, q1, p50, q3, p90, p95, p99, p999 = np.percentile(
        data, [1, 5, 10, 25, 50, 75, 90, 95, 99, 99.9]
    )
    iqr_val = float(q3 - q1)
    
    # Median Absolute Deviation (MAD)
    mad_val = float(np.median(np.abs(data - p50)))
    
    # Higher moments
    skew_val = float(stats.skew(data)) if n > 2 else 0.0
    kurt_val = float(stats.kurtosis(data)) if n > 3 else 0.0  # Fisher excess kurtosis
    
    # Harmonic & Geometric Means (positive values only)
    pos_data = data[data > 0]
    geo_mean = float(stats.gmean(pos_data)) if len(pos_data) > 0 else 0.0
    harm_mean = float(stats.hmean(pos_data)) if len(pos_data) > 0 else 0.0
    
    # Coefficient of Variation
    cv_val = float(std_val / mean_val) if mean_val > 0 else 0.0

    return {
        "n": n,
        "mean": mean_val,
        "std": std_val,
        "variance": var_val,
        "cv": cv_val,
        "median": float(p50),
        "q1": float(q1),
        "q3": float(q3),
        "iqr": iqr_val,
        "mad": mad_val,
        "min": float(np.min(data)),
        "max": float(np.max(data)),
        "skewness": skew_val,
        "excess_kurtosis": kurt_val,
        "geometric_mean": geo_mean,
        "harmonic_mean": harm_mean,
        "p1": float(p1),
        "p5": float(p5),
        "p10": float(p10),
        "p90": float(p90),
        "p95": float(p95),
        "p99": float(p99),
        "p999": float(p999),
    }


def compute_inequality_metrics(values: np.ndarray) -> Tuple[float, np.ndarray, np.ndarray, Dict[str, float]]:
    """
    Calculates the Gini Coefficient, empirical Lorenz Curve coordinates,
    and Pareto resource concentration shares.
    """
    arr = np.asarray(values, dtype=float)
    arr = arr[arr >= 0]
    n = len(arr)
    if n == 0 or np.sum(arr) == 0:
        return 0.0, np.array([0.0, 1.0]), np.array([0.0, 1.0]), {"top_1_pct": 0.0, "top_5_pct": 0.0, "top_20_pct": 0.0}

    sorted_arr = np.sort(arr)
    total_sum = np.sum(sorted_arr)
    
    # Exact Gini index using rank weighting
    index = np.arange(1, n + 1)
    gini = float((2.0 * np.sum(index * sorted_arr)) / (n * total_sum) - (n + 1.0) / n)
    gini = max(0.0, min(1.0, gini))

    # Lorenz Curve: (p, L(p))
    p = np.linspace(0.0, 1.0, num=min(n, 200))
    cum_shares = np.cumsum(sorted_arr) / total_sum
    # Interpolate to uniform p grid
    orig_p = np.linspace(0.0, 1.0, num=n)
    lorenz_y = np.interp(p, orig_p, cum_shares)
    lorenz_y[0] = 0.0
    lorenz_y[-1] = 1.0

    # Pareto concentration metrics: Top 1%, 5%, 20%
    rev_cum = np.cumsum(sorted_arr[::-1]) / total_sum
    top_1_idx = max(1, int(math.ceil(0.01 * n)))
    top_5_idx = max(1, int(math.ceil(0.05 * n)))
    top_20_idx = max(1, int(math.ceil(0.20 * n)))

    shares = {
        "top_1_pct": float(rev_cum[top_1_idx - 1] * 100.0),
        "top_5_pct": float(rev_cum[top_5_idx - 1] * 100.0),
        "top_20_pct": float(rev_cum[top_20_idx - 1] * 100.0),
    }

    return gini, p, lorenz_y, shares


def fit_heavy_tail_models(values: np.ndarray) -> Dict[str, Any]:
    """
    Fits parametric Log-Normal and Pareto distributions via Maximum Likelihood Estimation (MLE),
    and conducts Kolmogorov-Smirnov Goodness-of-Fit tests.
    """
    pos_data = np.asarray(values, dtype=float)
    pos_data = pos_data[pos_data > 0]
    
    if len(pos_data) < 10:
        return {"fitted": False, "reason": "Insufficient positive samples"}

    n = len(pos_data)
    
    # 1. Log-Normal Fit: X ~ LogNormal(mu, sigma)
    # scipy lognorm uses shape=s (sigma), scale=exp(mu) with floc=0
    shape_ln, loc_ln, scale_ln = stats.lognorm.fit(pos_data, floc=0)
    mu_ln = float(np.log(scale_ln))
    sigma_ln = float(shape_ln)
    
    # Kolmogorov-Smirnov Test for Log-Normal
    ks_ln, p_ln = stats.kstest(pos_data, "lognorm", args=(shape_ln, loc_ln, scale_ln))
    log_lik_ln = float(np.sum(stats.lognorm.logpdf(pos_data, shape_ln, loc_ln, scale_ln)))
    aic_ln = float(2 * 2 - 2 * log_lik_ln)

    # 2. Pareto Fit: X ~ Pareto(alpha, scale=xm)
    # Hill estimator / MLE on positive tail (top 50% or above threshold)
    threshold = float(np.percentile(pos_data, 50))
    tail_data = pos_data[pos_data >= threshold]
    if len(tail_data) >= 10:
        shape_p, loc_p, scale_p = stats.pareto.fit(tail_data, floc=0)
        ks_p, p_p = stats.kstest(tail_data, "pareto", args=(shape_p, loc_p, scale_p))
        log_lik_p = float(np.sum(stats.pareto.logpdf(tail_data, shape_p, loc_p, scale_p)))
        aic_p = float(2 * 2 - 2 * log_lik_p)
    else:
        shape_p, loc_p, scale_p, ks_p, p_p, aic_p = 1.0, 0.0, 1.0, 1.0, 0.0, 9999.0

    # Best model selection by AIC
    best_model = "Log-Normal" if aic_ln <= aic_p else "Pareto (Heavy Tail)"

    return {
        "fitted": True,
        "n_samples": n,
        "lognormal": {
            "mu": mu_ln,
            "sigma": sigma_ln,
            "scale": float(scale_ln),
            "ks_statistic": float(ks_ln),
            "p_value": float(p_ln),
            "aic": aic_ln,
        },
        "pareto": {
            "alpha": float(shape_p),
            "scale_xm": float(scale_p),
            "threshold": threshold,
            "ks_statistic": float(ks_p),
            "p_value": float(p_p),
            "aic": aic_p,
        },
        "best_model": best_model,
    }


def compute_kaplan_meier(durations: np.ndarray, event_observed: Optional[np.ndarray] = None) -> Dict[str, Any]:
    """
    Computes the non-parametric Kaplan-Meier survival estimator S(t)
    with Greenwood's formula for standard error and cumulative hazard H(t).
    """
    durations = np.asarray(durations, dtype=float)
    n = len(durations)
    if n == 0:
        return {"t": np.array([0.0]), "s": np.array([1.0]), "ci_lower": np.array([1.0]), "ci_upper": np.array([1.0])}

    if event_observed is None:
        # If all currently running, we treat observed as 1 (or current runtime as survival time)
        event_observed = np.ones(n, dtype=int)
    else:
        event_observed = np.asarray(event_observed, dtype=int)

    # Sort by time
    order = np.lexsort((event_observed, durations))
    d_sorted = durations[order]
    e_sorted = event_observed[order]

    unique_times, idx = np.unique(d_sorted, return_index=True)
    # Counts
    events_at_t = np.bincount(np.digitize(d_sorted, unique_times) - 1, weights=e_sorted)
    total_at_t = np.bincount(np.digitize(d_sorted, unique_times) - 1)

    timeline = [0.0]
    survival = [1.0]
    greenwood_terms = [0.0]

    n_at_risk = n
    cum_s = 1.0
    cum_var_term = 0.0

    for t, d_i, n_i in zip(unique_times, events_at_t, total_at_t):
        if n_at_risk <= 0:
            break
        # Probability of surviving this interval
        p_surv = 1.0 - (d_i / n_at_risk) if n_at_risk > 0 else 1.0
        cum_s *= max(0.0, p_surv)

        if n_at_risk > d_i and n_at_risk > 0:
            cum_var_term += d_i / (n_at_risk * (n_at_risk - d_i))

        timeline.append(float(t))
        survival.append(float(cum_s))
        greenwood_terms.append(float(cum_var_term))

        n_at_risk -= n_i

    t_arr = np.array(timeline)
    s_arr = np.array(survival)
    # Greenwood standard error
    se_arr = s_arr * np.sqrt(np.array(greenwood_terms))
    ci_lower = np.clip(s_arr - 1.96 * se_arr, 0.0, 1.0)
    ci_upper = np.clip(s_arr + 1.96 * se_arr, 0.0, 1.0)
    
    # Cumulative Hazard: H(t) = -ln(S(t))
    hazard_arr = -np.log(np.clip(s_arr, 1e-12, 1.0))

    # Median survival time
    median_time = float(t_arr[np.argmax(s_arr <= 0.5)]) if np.any(s_arr <= 0.5) else float(t_arr[-1])

    return {
        "t": t_arr,
        "s": s_arr,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "hazard": hazard_arr,
        "median_survival_seconds": median_time,
    }


def analyze_point_process_arrivals(timestamps: List[float]) -> Dict[str, Any]:
    """
    Analyzes inter-arrival times of system events to test the homogeneous
    Poisson Point Process hypothesis via exponential distribution tests and Fano factor.
    """
    if len(timestamps) < 5:
        return {"valid": False, "reason": "Insufficient timestamp events"}

    sorted_ts = np.sort(np.asarray(timestamps, dtype=float))
    intervals = np.diff(sorted_ts)
    intervals = intervals[intervals > 0]  # Positive inter-arrival times

    if len(intervals) < 4:
        return {"valid": False, "reason": "Insufficient positive intervals"}

    mean_dt = float(np.mean(intervals))
    std_dt = float(np.std(intervals, ddof=1)) if len(intervals) > 1 else 0.0
    var_dt = float(np.var(intervals, ddof=1)) if len(intervals) > 1 else 0.0

    # Rate parameter lambda = 1 / mean(Delta t)
    lambda_rate = float(1.0 / mean_dt) if mean_dt > 0 else 0.0

    # Fano factor / Index of Dispersion of inter-arrival times: D = Var / Mean
    # For Poisson process inter-arrivals (Exponential distribution), Var(X) = 1/lambda^2, Mean(X) = 1/lambda, so D_interval = 1/lambda
    # The coefficient of variation CV = sigma / mu = 1 for exponential distribution
    cv = float(std_dt / mean_dt) if mean_dt > 0 else 0.0
    
    # Kolmogorov-Smirnov test against Exponential(scale=mean_dt)
    ks_stat, ks_p = stats.kstest(intervals, "expon", args=(0.0, mean_dt))

    # Regime categorization based on CV
    if 0.8 <= cv <= 1.2 and ks_p > 0.05:
        regime = "Homogeneous Poisson Process (Random Independent Events)"
    elif cv > 1.2:
        regime = "Clustered / Overdispersed Burst Process (Cascading Events)"
    else:
        regime = "Regular / Underdispersed Process (Periodic Scheduling / Timers)"

    return {
        "valid": True,
        "n_events": len(sorted_ts),
        "n_intervals": len(intervals),
        "mean_interarrival_sec": mean_dt,
        "std_interarrival_sec": std_dt,
        "lambda_rate_hz": lambda_rate,
        "cv": cv,
        "ks_statistic": float(ks_stat),
        "ks_p_value": float(ks_p),
        "regime": regime,
        "intervals": intervals,
    }


def compute_drift_and_acf(series: List[float], max_lags: int = 20) -> Dict[str, Any]:
    """
    Computes OLS drift regression: y_t = beta_0 + beta_1 * t + eps,
    significance of slope (memory leak indicator), and Autocorrelation Function (ACF).
    """
    arr = np.asarray(series, dtype=float)
    n = len(arr)
    if n < 6:
        return {"valid": False, "reason": "Need at least 6 time series samples"}

    t = np.arange(n, dtype=float)
    reg = stats.linregress(t, arr)

    slope = float(reg.slope)
    intercept = float(reg.intercept)
    r_val = float(reg.rvalue)
    r2_val = float(r_val ** 2)
    p_val = float(reg.pvalue)
    stderr = float(reg.stderr)

    # Memory leak diagnosis
    # If slope is positive and statistically significant (p < 0.01)
    if slope > 0.05 and p_val < 0.01:
        leak_status = "⚠️ STATISTICALLY SIGNIFICANT DRIFT (Possible Leak)"
        leak_severity = "High"
    elif slope > 0.01 and p_val < 0.05:
        leak_status = "⚡ SLIGHT POSITIVE DRIFT (Monitor Trend)"
        leak_severity = "Moderate"
    else:
        leak_status = "✓ STEADY / ERGODIC (No Significant Leak)"
        leak_severity = "Normal"

    # Autocorrelation Function (ACF)
    diff = arr - np.mean(arr)
    denom = np.sum(diff ** 2)
    lags = min(max_lags, n // 2)
    acf_vals = []
    
    if denom > 1e-12:
        for k in range(lags + 1):
            if k == 0:
                acf_vals.append(1.0)
            else:
                num = np.sum(diff[k:] * diff[:-k])
                acf_vals.append(float(num / denom))
    else:
        acf_vals = [1.0] + [0.0] * lags

    # 95% Bartlett confidence limits: +/- 1.96 / sqrt(N)
    bartlett_ci = float(1.96 / math.sqrt(n))

    return {
        "valid": True,
        "n_samples": n,
        "slope": slope,
        "intercept": intercept,
        "r2": r2_val,
        "p_value": p_val,
        "stderr": stderr,
        "fitted_line": (intercept + slope * t).tolist(),
        "leak_status": leak_status,
        "leak_severity": leak_severity,
        "lags": list(range(lags + 1)),
        "acf": acf_vals,
        "bartlett_ci": bartlett_ci,
    }


def compute_modified_z_scores(values: np.ndarray) -> np.ndarray:
    """Computes robust Modified Z-scores using Median Absolute Deviation (MAD)."""
    arr = np.asarray(values, dtype=float)
    if len(arr) == 0:
        return np.array([])
    med = np.median(arr)
    mad = np.median(np.abs(arr - med))
    if mad < 1e-9:
        return np.zeros_like(arr)
    return 0.6745 * (arr - med) / mad
