# 🧪 CHEM 151 Master Review Desktop Suite

A standalone, offline native desktop study application and interactive calculator suite for **General Chemistry I (CHEM 151: Unit 1 & Unit 2)**.

Built as an offline GTK WebKit2 application—**no localhost, no web servers, and no browser address bar**.

---

## ✨ Features

### 1. Comprehensive Course Study Guide
- **Section 1: Complete Dictionary of Definitions (Unit 1 & Unit 2)**
  - Full glossary covering matter, measurements, precision vs accuracy, atomic theory, quantum numbers, periodic properties, chemical bonding, resonance, VSEPR geometries, and molecular orbital theory.
- **Section 2: Historical Registry of Scientists & Core Principles**
  - Lavoisier, Proust, Dalton, Thomson, Millikan, Rutherford, Bohr, de Broglie, Heisenberg, Hund, Pauli, Aufbau, and transition metal ion electron configurations.
- **Section 3: Physical Constants & Metric Conversion Tables**
  - Exact constants ($c, h, N_A, R_H$), metric prefixes ($10^9$ to $10^{-12}$), English-Metric conversion factors, and common polyatomic ion charges.
- **Section 4: Master Formulas & Periodic Trends**
  - Density, average atomic mass, mass percent, empirical/molecular multipliers, photon equations, Bohr energy transitions, de Broglie matter wavelength, ionization energy trends, and successive ionization jumps.
- **Section 5: Chemical Bonding, Lewis Structures, VSEPR Shapes & MOT**
  - The 8-Step Lewis Dot Structure protocol, complete VSEPR geometry table (2 to 6 electron domains), orbital hybridization ($sp, sp^2, sp^3, sp^3d, sp^3d^2$), and Molecular Orbital Theory diagrams ($\text{O}_2, \text{N}_2$).

### 2. 7 Offline Interactive Calculators
- 🧮 **Tool 1: Unit & Temperature Converter**: Metric prefixes ($G \leftrightarrow p$), English-to-Metric (in, cm, lb, g, gal, L, atm, mmHg, kPa), and Fahrenheit/Celsius/Kelvin.
- ⚖️ **Tool 2: Stoichiometry & Yield Solver**: Calculates limiting reactant, excess reactant, theoretical yield (grams & moles), **excess reactant remaining unreacted**, and percent yield.
- 🧬 **Tool 3: Empirical & Molecular Formula Determiner**: Solves empirical formulas from percent/mass compositions with automated fractional multiplier detection ($1/2, 1/3, 1/4$) and computes molecular formulas with given molar mass.
- 💡 **Tool 4: Electromagnetic Radiation Solver**: Interconverts between $\lambda$ (m, nm), $\nu$ (Hz), $E$ (J), and $kJ/mol$ while classifying the EM spectral region (UV, Visible, IR, etc.).
- ⚛️ **Tool 5: Bohr Hydrogen Transition Calculator**: Solves $\Delta E$, photon wavelength in nm, identifies absorption vs emission, and identifies the spectral series (Lyman, Balmer, Paschen, Brackett).
- 🌊 **Tool 6: de Broglie Matter Wavelength Solver**: Calculates $\lambda = h/mv$ for subatomic particles and macroscopic objects with quick presets.
- 🧲 **Tool 7: Formal Charge, Polarity & MOT Evaluator**: Formal charge calculator ($FC = V - N - B$), Pauling electronegativity difference ($\Delta\text{EN}$) bond classifier, and Molecular Orbital Theory bond order/magnetism.

### 3. Application User Experience
- **Dedicated Unit Tabs Navigation**: Features a main tab for **Unit 1** (Matter, Foundations & Stoichiometry) and another tab for **Unit 2** (Quantum Structure, Bonding & Geometry), plus an optional **All Units** comprehensive reference view.
- **Dynamic Sidebar Synchronization**: Switching tabs dynamically updates sidebar modules and calculator links to keep study sessions organized and clutter-free. Tab state is remembered across sessions.
- **Cross-Tab Smart Search**: Filters definitions, equations, and tools in real time. If search results exist in another unit tab, displays an instant one-click switch notice.
- **100% Offline & Native**: Runs in a dedicated GTK WebKit2 window using `file://` assets. Zero localhost server.
- **Local MathJax Engine**: Renders crisp LaTeX chemistry formulas using local system libraries (`/usr/share/javascript/mathjax`).
- **Dark Mode & PDF Export**: One-click dark/light theme switch and print-optimized PDF study sheets.

---

## 🚀 Installation & Launching

### Quick Launch (Current User)
```bash
chem151-master-review
```
Or launch from the **Projects** tab in your Linux Mint / Ubuntu Application Menu.

### Run Local Installer
```bash
cd ~/Projects/chem151-review
./install.sh
```

### Build & Install System-Wide Debian Package (`.deb`)
```bash
cd ~/Projects/chem151-review
./build_deb.sh
sudo apt install ./chem151-master-review_1.0.0_all.deb
```

---

## 📁 Project Architecture

```
chem151-review/
├── README.md                           # Documentation and usage guide
├── install.sh                          # Universal user/root installer script
├── build_deb.sh                        # Debian package builder script
├── chem151-master-review.desktop       # Desktop launcher for Projects category
├── chem151-master-review_1.0.0_all.deb # Ready-to-install Debian package
└── src/
    ├── app.html                        # Self-contained study suite and calculators
    ├── chem151-master-review           # Executable GTK WebKit2 Python launcher
    ├── chem151-master-review.svg       # Custom vector chemistry flask icon
    └── chem151_unit1_unit2_ultimate_master_review.ipynb # Source review notebook
```
