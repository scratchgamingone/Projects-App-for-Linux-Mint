#!/usr/bin/env bash
set -euo pipefail

# Directory structure
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_NAME="mint-autoclicker"
PKG_VERSION="1.1.0"
PKG_ARCH="all"
BUILD_DIR="${SCRIPT_DIR}/build/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}"
DEB_OUTPUT="${SCRIPT_DIR}/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}.deb"
DIST_OUTPUT="/home/sam/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}.deb"

echo "=== Building Debian Package: ${PKG_NAME} v${PKG_VERSION} ==="

# Clean previous build
rm -rf "${SCRIPT_DIR}/build" "${DEB_OUTPUT}" "${DIST_OUTPUT}"
mkdir -p "${BUILD_DIR}/DEBIAN"
mkdir -p "${BUILD_DIR}/usr/bin"
mkdir -p "${BUILD_DIR}/usr/lib/python3/dist-packages/mint_autoclicker"
mkdir -p "${BUILD_DIR}/usr/share/applications"
mkdir -p "${BUILD_DIR}/usr/share/pixmaps"

# Create icon directories
for size in 16 24 32 48 64 128 256 512; do
    mkdir -p "${BUILD_DIR}/usr/share/icons/hicolor/${size}x${size}/apps"
done
mkdir -p "${BUILD_DIR}/usr/share/icons/hicolor/scalable/apps"

# 1. DEBIAN/control
cat << 'EOF' > "${BUILD_DIR}/DEBIAN/control"
Package: mint-autoclicker
Version: 1.1.0
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.8), python3-tk, python3-xlib
Recommends: libcanberra-gtk-module, libcanberra-gtk3-module, wmctrl
Maintainer: Sam <sam@localhost>
Description: Modern, fast Auto Clicker for Linux Mint and Debian-based systems
 Mint Auto Clicker is an automated mouse clicking utility designed for
 clicking simulators, gaming (Roblox, Steam, browser games), and repetitive
 automation tasks.
 Features:
  - Cheat Engine style application & process selector with real-time search
  - Screen window picker (crosshair finder tool to target any window)
  - Window confinement (only clicks inside targeted application boundaries)
  - Active window lock (pauses clicking automatically if game loses focus)
  - Accidental exit guard (protects window titlebar & close button)
  - Global hotkey toggle (F6 default, customizable to F1-F12, Pause, etc.)
  - High-precision millisecond timing and CPS presets (10, 20, 50, 100 CPS)
  - Humanized timing jitter to bypass game anti-cheat and bot detectors
  - Left, right, and middle mouse button support
  - Single and double clicking modes
  - Repeat until stopped or fixed repeat count
  - Current cursor location or fixed X/Y coordinates with screen picker
  - Sleek dark theme matching Linux Mint Cinnamon
  - Always on top toggle and live statistics (clicks, elapsed time, CPS)
EOF

# 2. DEBIAN/postinst
cat << 'EOF' > "${BUILD_DIR}/DEBIAN/postinst"
#!/bin/sh
set -e

if [ "$1" = "configure" ]; then
    # Update desktop database
    if which update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi
    # Update icon caches
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

# 4. Copy Application Files into Python dist-packages
cp -r "${SCRIPT_DIR}/src/mint_autoclicker/"* "${BUILD_DIR}/usr/lib/python3/dist-packages/mint_autoclicker/"
find "${BUILD_DIR}/usr/lib/python3/dist-packages/mint_autoclicker" -type d -name "__pycache__" -exec rm -rf {} +
find "${BUILD_DIR}/usr/lib/python3/dist-packages/mint_autoclicker" -type f -name "*.pyc" -delete

# 5. Create launcher in /usr/bin/mint-autoclicker
cat << 'EOF' > "${BUILD_DIR}/usr/bin/mint-autoclicker"
#!/usr/bin/env python3
import sys
from mint_autoclicker.main import main

if __name__ == "__main__":
    main()
EOF
chmod 755 "${BUILD_DIR}/usr/bin/mint-autoclicker"

# 6. Copy Desktop file
cp "${SCRIPT_DIR}/mint-autoclicker.desktop" "${BUILD_DIR}/usr/share/applications/mint-autoclicker.desktop"
chmod 644 "${BUILD_DIR}/usr/share/applications/mint-autoclicker.desktop"

# 7. Copy Icons
for size in 16 24 32 48 64 128 256 512; do
    if [ -f "${SCRIPT_DIR}/src/mint_autoclicker/assets/icon-${size}.png" ]; then
        cp "${SCRIPT_DIR}/src/mint_autoclicker/assets/icon-${size}.png" \
           "${BUILD_DIR}/usr/share/icons/hicolor/${size}x${size}/apps/mint-autoclicker.png"
        chmod 644 "${BUILD_DIR}/usr/share/icons/hicolor/${size}x${size}/apps/mint-autoclicker.png"
    fi
done

if [ -f "${SCRIPT_DIR}/src/mint_autoclicker/assets/mint-autoclicker.svg" ]; then
    cp "${SCRIPT_DIR}/src/mint_autoclicker/assets/mint-autoclicker.svg" \
       "${BUILD_DIR}/usr/share/icons/hicolor/scalable/apps/mint-autoclicker.svg"
    chmod 644 "${BUILD_DIR}/usr/share/icons/hicolor/scalable/apps/mint-autoclicker.svg"
fi

if [ -f "${SCRIPT_DIR}/src/mint_autoclicker/assets/mint-autoclicker.png" ]; then
    cp "${SCRIPT_DIR}/src/mint_autoclicker/assets/mint-autoclicker.png" \
       "${BUILD_DIR}/usr/share/pixmaps/mint-autoclicker.png"
    chmod 644 "${BUILD_DIR}/usr/share/pixmaps/mint-autoclicker.png"
fi

# Ensure correct file permissions throughout package tree
find "${BUILD_DIR}/usr" -type d -exec chmod 755 {} +
find "${BUILD_DIR}/usr" -type f -exec chmod 644 {} +
chmod 755 "${BUILD_DIR}/usr/bin/mint-autoclicker"

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
