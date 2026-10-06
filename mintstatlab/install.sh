#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"

echo "=========================================================="
echo "   MintStatLab - User-Level Desktop Installation"
echo "=========================================================="

mkdir -p "${BIN_DIR}" "${APP_DIR}" "${ICON_DIR}"

# 1. Install executable link
chmod 755 "${PROJECT_ROOT}/bin/mintstatlab"
ln -sf "${PROJECT_ROOT}/bin/mintstatlab" "${BIN_DIR}/mintstatlab"
echo "✓ Installed launcher to ${BIN_DIR}/mintstatlab"

# 2. Install scalable SVG icon
cp -f "${PROJECT_ROOT}/data/icons/mintstatlab.svg" "${ICON_DIR}/mintstatlab.svg"
echo "✓ Installed icon to ${ICON_DIR}/mintstatlab.svg"

# 3. Install desktop launcher
sed "s|Exec=mintstatlab|Exec=${BIN_DIR}/mintstatlab|g" "${PROJECT_ROOT}/data/mintstatlab.desktop" > "${APP_DIR}/mintstatlab.desktop"
chmod 644 "${APP_DIR}/mintstatlab.desktop"
echo "✓ Installed desktop entry to ${APP_DIR}/mintstatlab.desktop"

# 4. Refresh Desktop & Icon Database
if which update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APP_DIR}" >/dev/null 2>&1 || true
fi
if which gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f "${HOME}/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

echo ""
echo "=========================================================="
echo " ✅ MintStatLab installed successfully!"
echo "    Category: Projects -> MintStatLab in Application Menu"
echo "    Terminal: Run 'mintstatlab'"
echo "=========================================================="
