#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_NAME="statdisk"
PKG_VERSION="1.0.0"
PKG_ARCH="all"
BUILD_DIR="${SCRIPT_DIR}/build/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}"
DEB_OUTPUT="${SCRIPT_DIR}/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}.deb"
DIST_OUTPUT="/home/sam/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}.deb"

echo "=== Building Debian Package: ${PKG_NAME} v${PKG_VERSION} ==="

# Clean previous build
rm -rf "${SCRIPT_DIR}/build" "${DEB_OUTPUT}" "${DIST_OUTPUT}"
mkdir -p "${BUILD_DIR}/DEBIAN"
mkdir -p "${BUILD_DIR}/usr/bin"
mkdir -p "${BUILD_DIR}/usr/lib/python3/dist-packages/statdisk"
mkdir -p "${BUILD_DIR}/usr/share/applications"
mkdir -p "${BUILD_DIR}/usr/share/pixmaps"

# Create icon directories
for size in 16 24 32 48 64 128 256 512; do
    mkdir -p "${BUILD_DIR}/usr/share/icons/hicolor/${size}x${size}/apps"
done
mkdir -p "${BUILD_DIR}/usr/share/icons/hicolor/scalable/apps"

# 1. DEBIAN/control
cat << 'EOF' > "${BUILD_DIR}/DEBIAN/control"
Package: statdisk
Version: 1.0.0
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.8), python3-gi, python3-cairo, python3-matplotlib, python3-scipy, python3-numpy, gir1.2-gtk-3.0
Recommends: xdg-utils, libcanberra-gtk3-module
Maintainer: Sam <sam@localhost>
Description: Interactive disk space analyzer with advanced statistical distributions
 StatDisk is a modern disk storage visualization and analytical utility inspired
 by SquirrelDisk, designed for developers and statistics majors.
 Features:
  - Interactive multi-level Sunburst chart with click-to-zoom and breadcrumbs
  - Squarified Treemap layout algorithm with instant visual drill-down
  - Highly organized hierarchical file browser with search filters and usage bars
  - Rigorous statistical moments: Mean, Geometric Mean, Harmonic Mean, Median,
    Variance, Standard Deviation, IQR, MAD, Fisher-Pearson Skewness, Excess Kurtosis
  - Parametric distribution modeling: Log-Normal PDF fitting and Kolmogorov-Smirnov test
  - Economic storage inequality: Lorenz Curve and Gini Coefficient calculation
  - Pareto 80/20 rule validation and power-law heavy-tail alpha exponent estimation
  - Outlier detection via Tukey's fences (1.5x and 3.0x IQR) and Modified Z-scores
  - Information theory: Shannon Entropy H(X), Pielou's Evenness, and Simpson Diversity
  - Temporal decay: Pearson and Spearman correlation between file age and file size
  - Academic report export to LaTeX (.tex), Markdown (.md), CSV, and JSON
  - Native GTK3 desktop app with no localhost server, designed for Linux Mint
EOF

# 2. DEBIAN/postinst
cat << 'EOF' > "${BUILD_DIR}/DEBIAN/postinst"
#!/bin/sh
set -e

if [ "$1" = "configure" ]; then
    if which update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi
    if which gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor 2>/dev/null || true
    fi
fi

exit 0
EOF
chmod 755 "${BUILD_DIR}/DEBIAN/postinst"

# 3. DEBIAN/postrm
cat << 'EOF' > "${BUILD_DIR}/DEBIAN/postrm"
#!/bin/sh
set -e

if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    if which update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi
    if which gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor 2>/dev/null || true
    fi
fi

exit 0
EOF
chmod 755 "${BUILD_DIR}/DEBIAN/postrm"

# 4. Copy Python package files
cp -r "${SCRIPT_DIR}/src/statdisk/"* "${BUILD_DIR}/usr/lib/python3/dist-packages/statdisk/"
find "${BUILD_DIR}/usr/lib/python3/dist-packages/statdisk" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "${BUILD_DIR}/usr/lib/python3/dist-packages/statdisk" -type f -name "*.pyc" -delete 2>/dev/null || true

# 5. Create launcher in /usr/bin/statdisk
cat << 'EOF' > "${BUILD_DIR}/usr/bin/statdisk"
#!/usr/bin/env python3
import sys
from statdisk.main import main

if __name__ == "__main__":
    main()
EOF
chmod 755 "${BUILD_DIR}/usr/bin/statdisk"

# 6. Copy Desktop file
cp "${SCRIPT_DIR}/statdisk.desktop" "${BUILD_DIR}/usr/share/applications/statdisk.desktop"
chmod 644 "${BUILD_DIR}/usr/share/applications/statdisk.desktop"

# 7. Copy Icons
for size in 16 24 32 48 64 128 256 512; do
    if [ -f "${SCRIPT_DIR}/src/statdisk/assets/icon-${size}.png" ]; then
        cp "${SCRIPT_DIR}/src/statdisk/assets/icon-${size}.png" \
           "${BUILD_DIR}/usr/share/icons/hicolor/${size}x${size}/apps/statdisk.png"
        chmod 644 "${BUILD_DIR}/usr/share/icons/hicolor/${size}x${size}/apps/statdisk.png"
    fi
done

if [ -f "${SCRIPT_DIR}/src/statdisk/assets/statdisk.svg" ]; then
    cp "${SCRIPT_DIR}/src/statdisk/assets/statdisk.svg" \
       "${BUILD_DIR}/usr/share/icons/hicolor/scalable/apps/statdisk.svg"
    chmod 644 "${BUILD_DIR}/usr/share/icons/hicolor/scalable/apps/statdisk.svg"
fi

if [ -f "${SCRIPT_DIR}/src/statdisk/assets/statdisk.png" ]; then
    cp "${SCRIPT_DIR}/src/statdisk/assets/statdisk.png" \
       "${BUILD_DIR}/usr/share/pixmaps/statdisk.png"
    chmod 644 "${BUILD_DIR}/usr/share/pixmaps/statdisk.png"
fi

# Ensure correct file permissions
find "${BUILD_DIR}/usr" -type d -exec chmod 755 {} +
find "${BUILD_DIR}/usr" -type f -exec chmod 644 {} +
chmod 755 "${BUILD_DIR}/usr/bin/statdisk"

# 8. Build Debian Package
echo "Building .deb archive..."
dpkg-deb --build --root-owner-group "${BUILD_DIR}" "${DEB_OUTPUT}"

# Copy to user root for easy access
cp "${DEB_OUTPUT}" "${DIST_OUTPUT}"

echo "=========================================================="
echo "SUCCESS: Built package successfully!"
echo "Debian Package: ${DIST_OUTPUT}"
echo "Package size: $(ls -lh "${DIST_OUTPUT}" | awk '{print $5}')"
echo "=========================================================="
