# 📊 Spicetify AudioStats & Session Analytics

A specialized [Spicetify](https://spicetify.app/) extension engineered for **statistics majors, music analysts, and DJs**. 

It transforms Spotify into a real-time audio analytics workstation by tracking song audio features, computing live sample descriptive statistics ($\bar{x}$, $s$, Min/Max, and Pearson correlation $r$), and exporting listening datasets directly to CSV for statistical computing in **R** or **Python**.

---

## ✨ Features

- **🎧 Real-time Track Audio Features:**
  - **Tempo (BPM):** Precise beat rate.
  - **Musical Key & Scale:** Standard notation (e.g., `C Major`, `F♯ Minor`) + **Camelot Wheel code** (`8B`, `11A`).
  - **Harmonic Mixing Candidates:** Identifies $+1$, $-1$, relative keys, and compatible mixing tracks.
  - **Continuous Feature Vector ($0.0 - 1.0$):** Energy, Valence (Positivity), Danceability, Acousticness, Instrumentalness, Speechiness, Loudness (dB), and Time Signature.
- **📈 Session Sample Descriptive Statistics ($n$ tracks):**
  - **Sample Mean ($\bar{x}$):** Central tendency across listening session.
  - **Sample Standard Deviation ($s$):** Dispersion / variance of tempo, mood, and intensity.
  - **Range & Extrema:** Minimum and Maximum bounds.
  - **Bivariate Correlation ($r$):** Real-time Pearson product-moment correlation coefficient $r(\text{Energy}, \text{Valence})$ tracking the *Russell Circumplex Model of Affect*.
- **🖥️ Non-intrusive UI:**
  - **Playbar Mini-HUD Pill:** A compact status pill in the bottom playback bar showing `📊 128 BPM • 8B • V: 0.65 • E: 0.81`.
  - **Topbar Analytics Button:** Dedicated chart icon in Spotify's top bar to open the analytics modal anytime.
- **📥 CSV Data Export:**
  - One-click export button downloading all observed session tracks with timestamps, identifiers, and complete numerical feature vectors for **R**, **Python (pandas)**, or **Excel**.

---

## 🚀 Quick Installation

Run the included automated installer script:

```bash
cd /home/sam/Projects/spicetify-audio-stats
./install.sh
```

### Manual Installation

If you prefer to configure Spicetify manually:

```bash
# 1. Symlink the extension into Spicetify's extensions directory
ln -sf /home/sam/Projects/spicetify-audio-stats/audioStats.js ~/.config/spicetify/Extensions/audioStats.js

# 2. Register the extension in Spicetify's configuration
spicetify config extensions audioStats.js

# 3. Apply changes to Spotify
spicetify apply
```

---

## 📐 Statistical Calculations & Methodology

### 1. Sample Mean ($\bar{x}$)
$$\bar{x} = \frac{1}{n} \sum_{i=1}^{n} x_i$$

### 2. Sample Standard Deviation ($s$)
Unbiased estimator with Bessel's correction ($n - 1$ degrees of freedom):
$$s = \sqrt{\frac{1}{n - 1} \sum_{i=1}^{n} (x_i - \bar{x})^2}$$

### 3. Pearson Correlation Coefficient ($r$)
Bivariate linear association between track **Energy** ($X$) and **Valence** ($Y$):
$$r_{XY} = \frac{\sum_{i=1}^{n} (x_i - \bar{x})(y_i - \bar{y})}{\sqrt{\sum_{i=1}^{n} (x_i - \bar{x})^2 \sum_{i=1}^{n} (y_i - \bar{y})^2}}$$

---

## 🐍 Analyzing Exported CSVs in Python & R

### Python (Pandas & Seaborn)
```python
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

df = pd.read_csv("spotify_session_stats.csv")

# Print summary statistics
print(df[["tempo_bpm", "energy", "valence", "danceability"]].describe())

# Plot Valence vs. Energy scatter with regression trendline
sns.lmplot(data=df, x="valence", y="energy", hue="camelot", fit_reg=True)
plt.title("Listening Session Affective Space (Valence vs Energy)")
plt.show()
```

### R (ggplot2 & dplyr)
```r
library(dplyr)
library(ggplot2)

df <- read.csv("spotify_session_stats.csv")

# Summary metrics
summary(df %>% select(tempo_bpm, energy, valence, danceability))

# Correlation test
cor.test(df$energy, df$valence)

# Density plot of BPM distribution
ggplot(df, aes(x = tempo_bpm)) +
  geom_density(fill = "#1DB954", alpha = 0.5) +
  theme_minimal() +
  labs(title = "Session Tempo Distribution", x = "BPM", y = "Density")
```

---

## 🗑️ Uninstallation

To remove the extension:

```bash
cd /home/sam/Projects/spicetify-audio-stats
./uninstall.sh
```
