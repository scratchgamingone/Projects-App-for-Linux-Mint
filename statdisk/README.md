# StatDisk (Statistical Disk Space Analyzer)

> **A native desktop storage visualizer inspired by SquirrelDisk, enriched with advanced statistical distributions, heavy-tail modeling, and inequality metrics.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux%20Mint%20%7C%20Debian%20%7C%20Ubuntu-orange.svg)](#)
[![GUI](https://img.shields.io/badge/GUI-Native%20GTK3%20%2B%20Cairo%20%2B%20Matplotlib-emerald.svg)](#)
[![No Localhost](https://img.shields.io/badge/Architecture-100%25%20Native%20Desktop%20(No%20Localhost)-purple.svg)](#)

---

## 🌟 Overview

**StatDisk** is an interactive disk space visualization and analytical application. While conventional tools only show folder sizes, **StatDisk** combines SquirrelDisk's signature interactive radial maps with a **rigorous statistical computing engine designed for statistics and data science majors**.

- **No localhost servers**: Runs 100% natively as a Linux desktop window using PyGObject (GTK3), Cairo, and Matplotlib.
- **Packaged for Linux Mint / Debian**: Ships with a `.deb` package and native `.desktop` launcher that integrates directly into your Application Menu.

---

## 🚀 Key Features

### 1. SquirrelDisk-Inspired Visual Storage Maps
- **Interactive Multi-Level Sunburst Chart**:
  - Multi-level concentric rings representing folder hierarchies.
  - Angular sector spans proportional to byte volume.
  - Smooth anti-aliased geometry with cohesive categorical color palettes.
  - **Click any sector** to smoothly zoom down into that subtree.
  - **Click center circle** to navigate back up to the parent directory.
  - Real-time hover inspection card (HUD) displaying file count, percentage, human-readable size, and path.
- **Squarified Treemap Layout**:
  - Area-accurate rectangular partitioning (Bruls-Huizing-van Wijk algorithm).
  - Dynamic aspect-ratio optimization with visual drill-down.
- **Interactive Breadcrumb Navigation**:
  - Clickable breadcrumb trail (`/` > `home` > `user` > `Downloads`) for instant jumping.

### 2. Highly Organized File Browser & Cleaner
- Sortable tabular contents view with column ordering:
  - **Name** with system MIME icons
  - **Size** (IEC binary units: KiB, MiB, GiB, TiB)
  - **Usage Bar** (visual percentage progress bar)
  - **Content** (file counts or extensions)
  - **Category** (Datasets, Databases, Videos, Audio, Code, Archives, Documents, Images)
  - **Last Modified Timestamp**
- **Instant Search & Filters**: Type to filter files in real-time, or filter by category (`Folders Only`, `Datasets & Databases`, `Large Files >100MB`, etc.).
- **Right-Click Context Menu**:
  - Open File / Folder (`xdg-open`)
  - Open Containing Folder
  - Copy Full Path to Clipboard
  - Safe Move to Trash (`gio trash`)

### 3. Statistics Suite (Tailored for Statistics Majors)
StatDisk treats disk usage as an empirical random variable $X \sim \text{Filesystem}$ and computes comprehensive statistical metrics:

#### 📊 Moments & Dispersion
- **Sample Size ($N$)** and directory counts
- **Arithmetic Mean ($\bar{x}$)**, **Geometric Mean**, and **Harmonic Mean**
- **Sample Variance ($s^2$)** and **Standard Deviation ($s$)**
- **Median ($\tilde{x} = Q_2$)** and **Interquartile Range ($IQR = Q_3 - Q_1$)**
- **Median Absolute Deviation ($MAD = \text{median}(|x_i - \tilde{x}|)$)**
- **Coefficient of Variation ($CV = s / \bar{x}$)**
- **Fisher-Pearson Skewness ($g_1$)**: measures the heavy right-tail of disk files
- **Excess Kurtosis ($g_2$)**: quantifies distribution leptokurtosis
- **Comprehensive Quantiles**: $P_1, P_5, P_{10}, P_{25} (Q_1), P_{50} (\text{Median}), P_{75} (Q_3), P_{90}, P_{95}, P_{99}, P_{99.9}, \text{Max}$

#### 📈 Parametric Distribution Modeling (Log-Normal & Heavy-Tail)
- Empirical histogram with logarithmic size binning ($\log_{10}(\text{bytes})$).
- **Fitted Theoretical Log-Normal PDF** with maximum likelihood parameters $(\mu, \sigma)$.
- **Kernel Density Estimation (KDE)** overlay.
- **Kolmogorov-Smirnov Goodness-of-Fit Test** ($D_{KS}$ statistic and $p$-value).
- **Pareto Heavy-Tail Exponent ($\hat{\alpha}$)** computed via the Hill estimator.

#### ⚖️ Storage Inequality (Lorenz Curve & Gini Index)
- **Empirical Lorenz Curve**: Cumulative file proportion vs cumulative storage share.
- **Gini Coefficient ($G$)**: Calculated via trapezoidal integration of the inequality area.
- **Pareto Principle Check**: Exact percentages of files required to reach 50%, 80%, and 90% of total storage (e.g. *"Top 3.2% of files consume 80.0% of storage"*).

#### 🎯 Outlier Detection (Tukey's Fences & Modified Z-Score)
- Box & Whisker plot on log scale.
- Tukey fences:
  - Mild Outliers: $x > Q_3 + 1.5 \times IQR$
  - Extreme Outliers: $x > Q_3 + 3.0 \times IQR$
- **Modified Z-Score** using MAD: $M_i = \frac{0.6745(x_i - \tilde{x})}{MAD}$
- Ranked table of anomalous files with direct double-click open.

#### ⏳ Temporal Decay & Correlation Analysis
- Scatter plot of File Age (days since modification) vs File Size.
- **Pearson correlation coefficient ($r$)** and significance ($p$-value).
- **Spearman rank correlation coefficient ($\rho$)**.
- Age bracket breakdown (<7 days, 7-30 days, 1-6 months, 6-12 months, 1-3 years, >3 years).

#### 🏷️ Information Theory & Extension Diversity
- **Shannon Information Entropy**: $H(X) = -\sum p_i \log_2(p_i)$ in bits.
- **Pielou's Evenness ($J$)** and **Simpson's Diversity Index ($D$)**.
- Dual-axis Pareto chart: Top extensions by volume + cumulative percentage line.

#### 📄 Academic Report Exporter
- Export complete analysis to:
  - **LaTeX (`.tex`)**: Formatted tables and formulas ready for paper publication.
  - **Markdown (`.md`)**: GitHub-ready report.
  - **CSV (`.csv`)**: Raw dataset with modified Z-scores for R, Python, or Stata.
  - **JSON (`.json`)**: Machine-readable full statistical schema.

---

## 📦 Installation & Usage

### Option 1: Instant Local Install (No Sudo Required)
The app is already installed in your user profile and ready in your menu! If you ever want to reinstall:
```bash
cd /home/sam/statdisk
./install.sh
```

### Option 2: System-Wide Debian Package (.deb)
Install the generated `.deb` package system-wide:
```bash
sudo dpkg -i /home/sam/statdisk_1.0.0_all.deb
```
Or double-click `/home/sam/statdisk_1.0.0_all.deb` in the file manager to install via Linux Mint's GDebi package installer.

### Launching the Application
- Open your **Linux Mint Application Menu** and search for **StatDisk**.
- Or run in terminal:
  ```bash
  statdisk
  ```
- Or analyze a specific folder directly:
  ```bash
  statdisk /var/log
  ```

---

## 🛠️ Rebuilding the .deb Package
To rebuild the Debian package at any time:
```bash
cd /home/sam/statdisk
./build_deb.sh
```
The output `.deb` will be generated at `/home/sam/statdisk_1.0.0_all.deb`.
