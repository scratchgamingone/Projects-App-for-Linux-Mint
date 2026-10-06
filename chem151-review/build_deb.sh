#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_NAME="chem151-master-review"
PKG_VERSION="1.0.0"
PKG_ARCH="all"
BUILD_DIR="${SCRIPT_DIR}/build/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}"
DEB_OUTPUT="${SCRIPT_DIR}/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}.deb"
COURSE_OUTPUT="/home/sam/Documents/LCC/CHEM 151/Unit 2/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}.deb"

echo "=== Building Debian Package: ${PKG_NAME} v${PKG_VERSION} ==="

# Clean previous build
rm -rf "${SCRIPT_DIR}/build" "${DEB_OUTPUT}"
mkdir -p "${BUILD_DIR}/DEBIAN"
mkdir -p "${BUILD_DIR}/usr/bin"
mkdir -p "${BUILD_DIR}/usr/share/chem151-master-review"
mkdir -p "${BUILD_DIR}/usr/share/applications"
mkdir -p "${BUILD_DIR}/usr/share/icons/hicolor/scalable/apps"

# 1. DEBIAN/control
cat << 'EOF' > "${BUILD_DIR}/DEBIAN/control"
Package: chem151-master-review
Version: 1.0.0
Section: science
Priority: optional
Architecture: all
Depends: python3 (>= 3.8), python3-gi, gir1.2-gtk-3.0, gir1.2-webkit2-4.1
Recommends: libjs-mathjax, fonts-mathjax
Maintainer: Sam <sam@localhost>
Description: CHEM 151 Ultimate Master Review Desktop Suite
 Complete General Chemistry Unit 1 and Unit 2 study guide,
 reference tables, definitions, and 7 interactive chemistry calculators.
 Features:
  - 100% offline native GTK WebKit2 desktop window (zero localhost, no servers)
  - Full dictionary of chemistry definitions for Units 1 and 2
  - Complete historical registry of chemistry scientists, experiments, and laws
  - Physical constants and English-Metric conversion tables
  - Chemical bonding, 8-step Lewis dot protocol, VSEPR shapes, and MOT
  - Interactive Tool 1: Metric, English-Metric & Temperature converter
  - Interactive Tool 2: Stoichiometry, Limiting & Excess reactant solver
  - Interactive Tool 3: Empirical & Molecular formula determiner
  - Interactive Tool 4: Electromagnetic radiation (c = lambda * nu, E = h * nu)
  - Interactive Tool 5: Bohr hydrogen energy level transitions (Delta E, Lyman, Balmer)
  - Interactive Tool 6: de Broglie matter wavelength solver (lambda = h / mv)
  - Interactive Tool 7: Formal charge, bond polarity (Delta EN), and MOT bond order
  - Real-time search filter across all study sections
  - Clean light and dark mode toggles with printable PDF styling
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

# 4. Copy app files to /usr/share/chem151-master-review
cp "${SCRIPT_DIR}/src/app.html" "${BUILD_DIR}/usr/share/chem151-master-review/app.html"
cp "${SCRIPT_DIR}/src/chem151-master-review.svg" "${BUILD_DIR}/usr/share/chem151-master-review/chem151-master-review.svg"
if [ -f "${SCRIPT_DIR}/src/chem151_unit1_unit2_ultimate_master_review.ipynb" ]; then
    cp "${SCRIPT_DIR}/src/chem151_unit1_unit2_ultimate_master_review.ipynb" "${BUILD_DIR}/usr/share/chem151-master-review/"
fi

# 5. Create launcher in /usr/bin/chem151-master-review
cp "${SCRIPT_DIR}/src/chem151-master-review" "${BUILD_DIR}/usr/bin/chem151-master-review"
chmod 755 "${BUILD_DIR}/usr/bin/chem151-master-review"

# 6. Desktop & Icon
cp "${SCRIPT_DIR}/chem151-master-review.desktop" "${BUILD_DIR}/usr/share/applications/chem151-master-review.desktop"
chmod 644 "${BUILD_DIR}/usr/share/applications/chem151-master-review.desktop"

cp "${SCRIPT_DIR}/src/chem151-master-review.svg" "${BUILD_DIR}/usr/share/icons/hicolor/scalable/apps/chem151-master-review.svg"
chmod 644 "${BUILD_DIR}/usr/share/icons/hicolor/scalable/apps/chem151-master-review.svg"

# Ensure permissions
find "${BUILD_DIR}/usr" -type d -exec chmod 755 {} +
find "${BUILD_DIR}/usr" -type f -exec chmod 644 {} +
chmod 755 "${BUILD_DIR}/usr/bin/chem151-master-review"

# 7. Build Debian Package
echo "Building .deb archive..."
dpkg-deb --build --root-owner-group "${BUILD_DIR}" "${DEB_OUTPUT}"

# Also copy to course directory if it exists
if [ -d "/home/sam/Documents/LCC/CHEM 151/Unit 2" ]; then
    cp "${DEB_OUTPUT}" "${COURSE_OUTPUT}"
fi

echo "=========================================================="
echo "SUCCESS: Built package successfully!"
echo "Debian Package: ${DEB_OUTPUT}"
echo "Package size: $(ls -lh "${DEB_OUTPUT}" | awk '{print $5}')"
echo "=========================================================="
