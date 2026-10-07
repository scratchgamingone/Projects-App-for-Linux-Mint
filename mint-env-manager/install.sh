#!/usr/bin/env bash
# ==============================================================================
# Mint Environment Manager Installer
# Installs application launcher, icons, and desktop integration for Linux Mint
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=================================================="
echo "       Mint Environment Manager Installer         "
echo "=================================================="

# Check Python environment
if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is required but not installed." >&2
    exit 1
fi

# Detect paths
TARGET_USER="${SUDO_USER:-$USER}"
TARGET_HOME="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"
[ -z "${TARGET_HOME}" ] && TARGET_HOME="${HOME}"

BIN_DIR="${TARGET_HOME}/.local/bin"
APP_DIR="${TARGET_HOME}/.local/share/applications"
ICON_BASE="${TARGET_HOME}/.local/share/icons/hicolor"
SITE_PKG_DIR="${TARGET_HOME}/.local/lib/python3.12/site-packages/mint_env_manager"

mkdir -p "${BIN_DIR}" "${APP_DIR}" "${ICON_BASE}" "${SITE_PKG_DIR}"

# 1. Install Python package
echo "Installing package files to ${SITE_PKG_DIR}..."
rm -rf "${SITE_PKG_DIR:?}"/*
cp -r "${SCRIPT_DIR}/src/"* "${SITE_PKG_DIR}/"

# 2. Install icons
echo "Installing application icons..."
for size in 16 24 32 48 64 128 256; do
    if [ -f "${SCRIPT_DIR}/assets/icon-${size}.png" ]; then
        mkdir -p "${ICON_BASE}/${size}x${size}/apps"
        cp "${SCRIPT_DIR}/assets/icon-${size}.png" \
           "${ICON_BASE}/${size}x${size}/apps/mint-env-manager.png"
    fi
done

if [ -f "${SCRIPT_DIR}/assets/mint-env-manager.svg" ]; then
    mkdir -p "${ICON_BASE}/scalable/apps"
    cp "${SCRIPT_DIR}/assets/mint-env-manager.svg" \
       "${ICON_BASE}/scalable/apps/mint-env-manager.svg"
fi

if [ -f "${SCRIPT_DIR}/assets/mint-env-manager.png" ]; then
    mkdir -p "${TARGET_HOME}/.local/share/pixmaps"
    cp "${SCRIPT_DIR}/assets/mint-env-manager.png" \
       "${TARGET_HOME}/.local/share/pixmaps/mint-env-manager.png"
fi

# 3. Create launcher script
LAUNCHER="${BIN_DIR}/mint-env-manager"
cat << 'EOF' > "${LAUNCHER}"
#!/usr/bin/env bash
# Mint Environment Manager Launcher
set -e

# Forward local X11 display permissions to root for GUI elevation if DISPLAY is present
if [ -n "${DISPLAY:-}" ] && command -v xhost >/dev/null 2>&1; then
    xhost +si:localuser:root >/dev/null 2>&1 || true
fi

# Run main module
exec /usr/bin/python3 -m mint_env_manager.main "$@"
EOF
chmod 0755 "${LAUNCHER}"

# Create convenience alias
ln -sfn "${LAUNCHER}" "${BIN_DIR}/env-manager"

# 4. Install Desktop File
cat << EOF > "${APP_DIR}/mint-env-manager.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=Mint Environment Manager
GenericName=System Environment & API Key Manager
Comment=Manage /etc/environment and .env variables with administrator elevation and live API key verification
Exec=${LAUNCHER} %f
Icon=mint-env-manager
Terminal=false
Categories=Projects;Settings;System;Development;
Keywords=env;environment;api;key;token;admin;sudo;pkexec;steam;github;openai;gemini;
StartupNotify=true
StartupWMClass=mint-env-manager
EOF
chmod 0644 "${APP_DIR}/mint-env-manager.desktop"

# 5. If root, also link to system-wide /usr/local/bin and /usr/share
if [ "$(id -u)" -eq 0 ]; then
    echo "Registering system-wide symlinks (/usr/local/bin and /usr/share)..."
    ln -sfn "${LAUNCHER}" "/usr/local/bin/mint-env-manager"
    ln -sfn "${LAUNCHER}" "/usr/local/bin/env-manager"
    cp "${APP_DIR}/mint-env-manager.desktop" "/usr/share/applications/mint-env-manager.desktop"
    if [ -f "${SCRIPT_DIR}/assets/mint-env-manager.svg" ]; then
        mkdir -p /usr/share/icons/hicolor/scalable/apps
        cp "${SCRIPT_DIR}/assets/mint-env-manager.svg" /usr/share/icons/hicolor/scalable/apps/
    fi
fi

# 6. Refresh desktop database & icon caches
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APP_DIR}" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -t -f "${ICON_BASE}" >/dev/null 2>&1 || true
fi

echo "=================================================="
echo " ✓ Mint Environment Manager successfully installed!"
echo "   Launcher: ${LAUNCHER}"
echo "   Desktop:  ${APP_DIR}/mint-env-manager.desktop"
echo "   Category: Applications -> Projects tab"
echo "=================================================="
