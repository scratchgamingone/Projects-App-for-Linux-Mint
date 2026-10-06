#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_DEB="${SCRIPT_DIR}/chem151-master-review_1.0.0_all.deb"

echo "==============================================="
echo "       CHEM 151 Master Review Installer        "
echo "==============================================="

if [ "$(id -u)" -eq 0 ]; then
    echo "Installing system-wide .deb package via dpkg..."
    if [ ! -f "${PKG_DEB}" ]; then
        "${SCRIPT_DIR}/build_deb.sh"
    fi
    dpkg -i "${PKG_DEB}" || apt-get install -f -y
    echo "System-wide installation complete! CHEM 151 is in your Projects menu."
    exit 0
fi

# User-level installation (No sudo required)
echo "Installing for current user ($(whoami))..."
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"
DATA_DIR="${HOME}/.local/share/chem151-master-review"

mkdir -p "${BIN_DIR}" "${APP_DIR}" "${ICON_DIR}" "${DATA_DIR}"

# 1. Copy app assets
cp "${SCRIPT_DIR}/src/app.html" "${DATA_DIR}/app.html"
cp "${SCRIPT_DIR}/src/chem151-master-review.svg" "${DATA_DIR}/chem151-master-review.svg"
if [ -f "${SCRIPT_DIR}/src/chem151_unit1_unit2_ultimate_master_review.ipynb" ]; then
    cp "${SCRIPT_DIR}/src/chem151_unit1_unit2_ultimate_master_review.ipynb" "${DATA_DIR}/"
fi

# 2. Copy launcher
cp "${SCRIPT_DIR}/src/chem151-master-review" "${BIN_DIR}/chem151-master-review"
chmod 755 "${BIN_DIR}/chem151-master-review"

# 3. Copy icon
cp "${SCRIPT_DIR}/src/chem151-master-review.svg" "${ICON_DIR}/chem151-master-review.svg"

# 4. Copy and adjust desktop entry for user
cp "${SCRIPT_DIR}/chem151-master-review.desktop" "${APP_DIR}/chem151-master-review.desktop"

# 5. Refresh databases
if which update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APP_DIR}" 2>/dev/null || true
fi
if which gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true
fi

echo "==============================================="
echo "✓ Installation complete!"
echo "  Launcher: ${BIN_DIR}/chem151-master-review"
echo "  Desktop shortcut: Installed to Projects menu"
echo "  Run via terminal: chem151-master-review"
echo "==============================================="
