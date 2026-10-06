# 🌿 MintStatLab (Linux Mint Statistical Telemetry & Performance Lab)

> **A native Linux Mint GTK3 application transforming operating system telemetry into empirical statistical models (Lorenz curves, Gini inequality, Kaplan-Meier process survival, Poisson event arrival, and memory drift regression).**

[![Platform](https://img.shields.io/badge/Platform-Linux%20Mint%2022.x%20%7C%20Debian%20%7C%20Ubuntu-orange.svg)](#)
[![GUI](https://img.shields.io/badge/GUI-Native%20GTK3%20%2B%20Matplotlib-emerald.svg)](#)
[![No Localhost](https://img.shields.io/badge/Architecture-100%25%20Native%20Desktop%20(No%20Localhost)-purple.svg)](#)
[![Packaging](https://img.shields.io/badge/Package-.deb%20(Debian%20Binary)-blue.svg)](#)

---

## 🌟 Overview

While conventional system monitors only show basic load percentages, **MintStatLab** treats Linux Mint as an empirical data science stream. Tailored specifically for **statistics and mathematical data science majors**, it pairs real-time operating system diagnostics with rigorous statistical computing.

- **100% Native Linux Desktop (No Localhost)**: Runs via PyGObject (GTK3), Cairo, and Matplotlib. Absolutely zero web servers, browser windows, or localhost ports.
- **Packaged as `.deb`**: Ready-to-install Debian binary package for Linux Mint Cinnamon.
- **Cinnamon Menu Integration**: Automatically sits in the **Projects** menu category with a custom dark-teal vector icon matching your desktop theme.

---

## 🔬 Core Statistical Methodology

### 1. 📊 Resource Inequality & Heavy-Tail Modeling
- **Lorenz Curve**: Plots cumulative proportion of processes $p_i = i/n$ against cumulative share of system memory and CPU cores $L(p_i)$.
- **Gini Coefficient ($G$)**:
  $$G = \frac{\sum_{i=1}^n \sum_{j=1}^n |x_i - x_j|}{2n^2 \bar{x}} = \frac{2 \sum_{i=1}^n i x_{(i)}}{n \sum_{i=1}^n x_{(i)}} - \frac{n+1}{n}$$
  Quantifies resource monopolization by individual background daemons and user apps.
- **Parametric Distribution Fitting (MLE)**:
  - **Log-Normal**: Models positive memory allocations $X \sim \text{LogNormal}(\mu, \sigma)$.
  - **Pareto Heavy-Tail**: Models the extreme upper tail of memory hogs: $P(X > x) = (x_m / x)^\alpha$.
  - **Kolmogorov-Smirnov Test ($D_{KS}, p$)** & Akaike Information Criterion (AIC) for model selection.
- **Pareto Concentration**: Exact resource shares held by the top 1%, 5%, and 20% of processes.

### 2. ⏳ Process Survival Analysis (Kaplan-Meier Reliability)
- Evaluates process lifespans $T = t_{\text{now}} - t_{\text{start}}$ across user-facing apps vs. system daemons.
- **Kaplan-Meier Non-Parametric Estimator**:
  $$\hat{S}(t) = \prod_{t_i \le t} \left(1 - \frac{d_i}{n_i}\right)$$
- **Greenwood Variance & 95% Confidence Bands**:
  $$\widehat{\text{Var}}(\hat{S}(t)) = \hat{S}(t)^2 \sum_{t_i \le t} \frac{d_i}{n_i(n_i - d_i)}$$
- **Cumulative Hazard Function**: $\hat{H}(t) = -\ln \hat{S}(t)$.

### 3. 🎲 Stochastic Event Arrivals (Point Process Modeling)
- Intercepts system journal events (`journalctl`) and computes inter-arrival intervals $\Delta t_k = t_k - t_{k-1}$.
- **Poisson Point Process Hypothesis**:
  - Tests whether system alerts arrive independently at constant rate $\lambda = 1 / \bar{\Delta t}$.
  - Evaluates goodness-of-fit against the Exponential distribution $Exp(\lambda)$ via Q-Q plots and Kolmogorov-Smirnov tests.
- **Fano Factor / Dispersion Index ($D = \sigma^2 / \mu$)**:
  - $D \approx 1.0$: Homogeneous Poisson random process.
  - $D > 1.2$: Overdispersed burst process (cascading errors/alerts).
  - $D < 0.8$: Underdispersed regular process (scheduled periodic cron jobs/timers).

### 4. 📈 Temporal Drift & Memory Leak Regression
- Buffers real-time rolling memory consumption over an observation window.
- **Ordinary Least Squares (OLS) Linear Model**: $y_t = \hat{\beta}_0 + \hat{\beta}_1 t + \epsilon_t$.
- Calculates growth rate $\hat{\beta}_1$ (in MiB/min), standard error $SE(\hat{\beta}_1)$, $t$-statistic, and $p$-value.
- **Statistical Leak Detection**: Flags memory leaks when $\hat{\beta}_1 > 0$ with $p < 0.01$.
- **Autocorrelation Function (ACF)**: Computes autocorrelation $\rho_k$ across lags $k = 1 \dots 20$ with Bartlett 95% confidence intervals ($\pm 1.96 / \sqrt{N}$).

### 5. 🎯 Robust Outlier Detection (Tukey Fences & Modified Z-Scores)
- Avoids fragile mean/standard deviation outliers by computing **Modified Z-Scores** based on the Median Absolute Deviation (MAD):
  $$M_i = \frac{0.6745 \cdot (x_i - \tilde{x})}{\text{MAD}}$$
- Identifies anomalies exceeding Tukey's upper fence: $x_i > Q_3 + 1.5 \times IQR$.

---

## 📦 Building & Installing the Debian Package

### 1. Build the `.deb` Package
From the project directory, run the build script:
```bash
cd /home/sam/Projects/mintstatlab
./build-deb.sh
```
This generates `mintstatlab_1.0.0_all.deb` in the project root.

### 2. Instant Local Installation (No Sudo Required)
To install the application directly into your user profile and application menu:
```bash
./install.sh
```

### 3. System-Wide Installation (via `.deb`)
```bash
sudo dpkg -i mintstatlab_1.0.0_all.deb
```
Or double-click the `.deb` file in Nemo to install via Linux Mint's GDebi Package Installer.

---

## 🚀 Launching MintStatLab

- **Application Menu**: Navigate to **Menu > Projects > MintStatLab** (or search "MintStatLab").
- **Terminal**: Run `mintstatlab`.

---

## 📄 Academic Export Capabilities

Click the **Save (Disk)** button in the top headerbar to export:
1. **LaTeX Document (`.tex`)**: Fully formatted academic paper with LaTeX tables and formulas ready for submission.
2. **CSV Telemetry (`.csv`)**: Raw snapshot with modified Z-scores for further analysis in **R**, **Julia**, or **Python**.
3. **JSON Schema (`.json`)**: Complete machine-readable statistical payload.
