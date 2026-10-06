#!/usr/bin/env bash
# ==============================================================================
# Mint Script Runner Installer (User-level & System-wide .deb)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_DEB="${SCRIPT_DIR}/mint-script-runner_1.0.0_all.deb"

echo "==============================================="
echo "       Mint Script Runner Installer            "
echo "==============================================="

# 1. Ensure .deb is built
if [ ! -f "${PKG_DEB}" ]; then
    echo "Building Debian package first..."
    "${SCRIPT_DIR}/build_deb.sh"
fi

# 2. System-wide installation if root
if [ "$(id -u)" -eq 0 ]; then
    echo "Installing system-wide .deb package via dpkg..."
    dpkg -i "${PKG_DEB}" || apt-get install -f -y
    echo "System-wide installation complete! Mint Script Runner is in your Application Menu."
    exit 0
fi

# 3. User-level installation (Immediate, No sudo required)
echo "Installing for current user ($(whoami))..."
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"
ICON_BASE="${HOME}/.local/share/icons/hicolor"
SITE_PKG_DIR="${HOME}/.local/lib/python3.12/site-packages/mint_script_runner"
ASKPASS_DIR="${HOME}/.local/lib/mint-script-runner"

mkdir -p "${BIN_DIR}" "${APP_DIR}" "${SITE_PKG_DIR}" "${ASKPASS_DIR}"

# Copy application source into user site-packages
rm -rf "${SITE_PKG_DIR}"/*
cp -r "${SCRIPT_DIR}/src/mint_script_runner/"* "${SITE_PKG_DIR}/"

# Copy askpass helper
cp "${SCRIPT_DIR}/src/mint_script_runner/askpass_helper.py" "${ASKPASS_DIR}/git-askpass.py"
chmod +x "${ASKPASS_DIR}/git-askpass.py"

# Copy icons
for size in 16 24 32 48 64 128 256 512; do
    if [ -f "${SCRIPT_DIR}/src/mint_script_runner/assets/icon-${size}.png" ]; then
        mkdir -p "${ICON_BASE}/${size}x${size}/apps"
        cp "${SCRIPT_DIR}/src/mint_script_runner/assets/icon-${size}.png" \
           "${ICON_BASE}/${size}x${size}/apps/mint-script-runner.png"
    fi
done

if [ -f "${SCRIPT_DIR}/src/mint_script_runner/assets/mint-script-runner.svg" ]; then
    mkdir -p "${ICON_BASE}/scalable/apps"
    cp "${SCRIPT_DIR}/src/mint_script_runner/assets/mint-script-runner.svg" \
       "${ICON_BASE}/scalable/apps/mint-script-runner.svg"
fi

if [ -f "${SCRIPT_DIR}/src/mint_script_runner/assets/mint-script-runner.png" ]; then
    mkdir -p "${HOME}/.local/share/pixmaps"
    cp "${SCRIPT_DIR}/src/mint_script_runner/assets/mint-script-runner.png" \
       "${HOME}/.local/share/pixmaps/mint-script-runner.png"
fi

# Create user bin launcher
cat << 'EOF' > "${BIN_DIR}/mint-script-runner"
#!/usr/bin/env python3
import sys
from mint_script_runner.main import main

if __name__ == "__main__":
    main()
EOF
chmod +x "${BIN_DIR}/mint-script-runner"

# Also create shortcut 'script-runner'
ln -sfn "${BIN_DIR}/mint-script-runner" "${BIN_DIR}/script-runner"

# Create user .desktop file
cat << EOF > "${APP_DIR}/mint-script-runner.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=Mint Script Runner
GenericName=Shell Script Executor
Comment=Drag-and-drop .sh script runner with root elevation and GitHub credentials integration
Exec=${BIN_DIR}/mint-script-runner %f
Icon=mint-script-runner
Terminal=false
Categories=Projects;Utility;System;Development;
Keywords=script;runner;shell;bash;sh;terminal;admin;pkexec;github;git;
MimeType=application/x-shellscript;text/x-shellscript;
StartupNotify=true
StartupWMClass=mint-script-runner
EOF
chmod +x "${APP_DIR}/mint-script-runner.desktop"

# Update desktop & icon caches
if which update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APP_DIR}" >/dev/null 2>&1 || true
fi
if which gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -t -f "${ICON_BASE}" >/dev/null 2>&1 || true
fi

echo "==============================================="
echo "✅ SUCCESS: Mint Script Runner is installed!"
echo "It is now live in your Linux Mint Application Menu (Projects / Administration)."
echo "You can launch it directly from your Menu or run:"
echo "    mint-script-runner"
echo ""
echo "Or install the system-wide .deb with:"
echo "    sudo dpkg -i ${PKG_DEB}"
echo "==============================================="
