#!/usr/bin/env bash
# ==============================================================================
# Build Debian Package for Mint Script Runner
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_NAME="mint-script-runner"
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
mkdir -p "${BUILD_DIR}/usr/lib/mint-script-runner"
mkdir -p "${BUILD_DIR}/usr/lib/python3/dist-packages/mint_script_runner"
mkdir -p "${BUILD_DIR}/usr/share/applications"
mkdir -p "${BUILD_DIR}/usr/share/pixmaps"

# Icon directories
for size in 16 24 32 48 64 128 256 512; do
    mkdir -p "${BUILD_DIR}/usr/share/icons/hicolor/${size}x${size}/apps"
done
mkdir -p "${BUILD_DIR}/usr/share/icons/hicolor/scalable/apps"

# 1. DEBIAN/control
cat << 'EOF' > "${BUILD_DIR}/DEBIAN/control"
Package: mint-script-runner
Version: 1.0.0
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.8), python3-gi, gir1.2-gtk-3.0, pkexec
Recommends: git
Maintainer: Sam <sam@localhost>
Description: Native Drag & Drop .sh Shell Script Runner for Linux Mint
 Mint Script Runner provides an intuitive graphical interface to execute
 any shell script (.sh) without opening the terminal.
 Features:
  - Drag and Drop .sh script files directly into the window
  - Right-click "Open With" integration from file manager (Nemo)
  - Pre-flight execution confirmation dialog (Root / Administrator vs Normal User)
  - Seamless root privilege elevation using PolicyKit (pkexec)
  - Dedicated GitHub Credentials Settings tab
  - Automatic Git/GitHub script detection and silent credential injection
  - Automated GIT_ASKPASS helper for non-interactive git push/pull/clone
  - Real-time dark terminal console streaming output line-by-line
  - Process stop/kill controls and execution timer
  - 100% offline native GTK3 desktop application (no localhost / no browser)
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

# 4. Copy Python Module Files
cp -r "${SCRIPT_DIR}/src/mint_script_runner/"* "${BUILD_DIR}/usr/lib/python3/dist-packages/mint_script_runner/"
find "${BUILD_DIR}/usr/lib/python3/dist-packages/mint_script_runner" -type d -name "__pycache__" -exec rm -rf {} +
find "${BUILD_DIR}/usr/lib/python3/dist-packages/mint_script_runner" -type f -name "*.pyc" -delete

# 5. Copy AskPass Helper
cp "${SCRIPT_DIR}/src/mint_script_runner/askpass_helper.py" "${BUILD_DIR}/usr/lib/mint-script-runner/git-askpass.py"
chmod 755 "${BUILD_DIR}/usr/lib/mint-script-runner/git-askpass.py"

# 6. Create /usr/bin/mint-script-runner launcher
cat << 'EOF' > "${BUILD_DIR}/usr/bin/mint-script-runner"
#!/usr/bin/env python3
import sys
from mint_script_runner.main import main

if __name__ == "__main__":
    main()
EOF
chmod 755 "${BUILD_DIR}/usr/bin/mint-script-runner"

# 7. Copy Desktop File
cp "${SCRIPT_DIR}/mint-script-runner.desktop" "${BUILD_DIR}/usr/share/applications/mint-script-runner.desktop"
chmod 644 "${BUILD_DIR}/usr/share/applications/mint-script-runner.desktop"

# 8. Copy Icons
for size in 16 24 32 48 64 128 256 512; do
    if [ -f "${SCRIPT_DIR}/src/mint_script_runner/assets/icon-${size}.png" ]; then
        cp "${SCRIPT_DIR}/src/mint_script_runner/assets/icon-${size}.png" \
           "${BUILD_DIR}/usr/share/icons/hicolor/${size}x${size}/apps/mint-script-runner.png"
        chmod 644 "${BUILD_DIR}/usr/share/icons/hicolor/${size}x${size}/apps/mint-script-runner.png"
    fi
done

if [ -f "${SCRIPT_DIR}/src/mint_script_runner/assets/mint-script-runner.svg" ]; then
    cp "${SCRIPT_DIR}/src/mint_script_runner/assets/mint-script-runner.svg" \
       "${BUILD_DIR}/usr/share/icons/hicolor/scalable/apps/mint-script-runner.svg"
    chmod 644 "${BUILD_DIR}/usr/share/icons/hicolor/scalable/apps/mint-script-runner.svg"
fi

if [ -f "${SCRIPT_DIR}/src/mint_script_runner/assets/mint-script-runner.png" ]; then
    cp "${SCRIPT_DIR}/src/mint_script_runner/assets/mint-script-runner.png" \
       "${BUILD_DIR}/usr/share/pixmaps/mint-script-runner.png"
    chmod 644 "${BUILD_DIR}/usr/share/pixmaps/mint-script-runner.png"
fi

# Ensure correct permissions
find "${BUILD_DIR}/usr" -type d -exec chmod 755 {} +
find "${BUILD_DIR}/usr" -type f -exec chmod 644 {} +
chmod 755 "${BUILD_DIR}/usr/bin/mint-script-runner"
chmod 755 "${BUILD_DIR}/usr/lib/mint-script-runner/git-askpass.py"

# 9. Build Debian Package
echo "Building .deb archive..."
dpkg-deb --build --root-owner-group "${BUILD_DIR}" "${DEB_OUTPUT}"

cp "${DEB_OUTPUT}" "${DIST_OUTPUT}"

echo "=========================================================="
echo "✅ Build Complete!"
echo "Package: ${DEB_OUTPUT}"
echo "Size: $(ls -lh "${DEB_OUTPUT}" | awk '{print $5}')"
echo "=========================================================="
