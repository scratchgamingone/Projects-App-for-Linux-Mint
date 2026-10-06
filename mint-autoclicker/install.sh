#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_DEB="${SCRIPT_DIR}/mint-autoclicker_1.1.0_all.deb"

echo "==============================================="
echo "       Mint Auto Clicker Installer            "
echo "==============================================="

if [ "$(id -u)" -eq 0 ]; then
    echo "Installing system-wide .deb package via dpkg..."
    if [ ! -f "${PKG_DEB}" ]; then
        "${SCRIPT_DIR}/build_deb.sh"
    fi
    dpkg -i "${PKG_DEB}" || apt-get install -f -y
    echo "System-wide installation complete! Mint Auto Clicker is in your Application Menu."
    exit 0
fi

# User-level installation (No sudo required)
echo "Installing for current user ($(whoami))..."
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"
ICON_BASE="${HOME}/.local/share/icons/hicolor"
SITE_PKG_DIR="${HOME}/.local/lib/python3.12/site-packages/mint_autoclicker"

mkdir -p "${BIN_DIR}" "${APP_DIR}" "${SITE_PKG_DIR}"

# Copy application source into user site-packages
rm -rf "${SITE_PKG_DIR}"/*
cp -r "${SCRIPT_DIR}/src/mint_autoclicker/"* "${SITE_PKG_DIR}/"

# Copy icons
for size in 16 24 32 48 64 128 256 512; do
    if [ -f "${SCRIPT_DIR}/src/mint_autoclicker/assets/icon-${size}.png" ]; then
        mkdir -p "${ICON_BASE}/${size}x${size}/apps"
        cp "${SCRIPT_DIR}/src/mint_autoclicker/assets/icon-${size}.png" \
           "${ICON_BASE}/${size}x${size}/apps/mint-autoclicker.png"
    fi
done

if [ -f "${SCRIPT_DIR}/src/mint_autoclicker/assets/mint-autoclicker.svg" ]; then
    mkdir -p "${ICON_BASE}/scalable/apps"
    cp "${SCRIPT_DIR}/src/mint_autoclicker/assets/mint-autoclicker.svg" \
       "${ICON_BASE}/scalable/apps/mint-autoclicker.svg"
fi

# Create user bin launcher
cat << 'EOF' > "${BIN_DIR}/mint-autoclicker"
#!/usr/bin/env python3
import sys
from mint_autoclicker.main import main

if __name__ == "__main__":
    main()
EOF
chmod +x "${BIN_DIR}/mint-autoclicker"

# Create user .desktop file
cat << EOF > "${APP_DIR}/mint-autoclicker.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=Mint Auto Clicker
GenericName=Auto Clicker
Comment=Fast customizable auto clicker for games, clicking simulators, and repetitive tasks
Exec=${BIN_DIR}/mint-autoclicker
Icon=mint-autoclicker
Terminal=false
Categories=Projects;Utility;Game;
Keywords=autoclicker;clicker;gaming;simulator;mouse;roblox;automation;
StartupNotify=true
StartupWMClass=mint-autoclicker
EOF
chmod +x "${APP_DIR}/mint-autoclicker.desktop"

# Update desktop & icon caches
if which update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APP_DIR}" >/dev/null 2>&1 || true
fi
if which gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -t -f "${ICON_BASE}" >/dev/null 2>&1 || true
fi

echo "==============================================="
echo "SUCCESS: Mint Auto Clicker is installed!"
echo "It has been added to your Linux Mint Application Menu."
echo "You can launch it directly from the Menu or run:"
echo "    mint-autoclicker"
echo ""
echo "Or install the system-wide .deb with:"
echo "    sudo dpkg -i /home/sam/mint-autoclicker_1.1.0_all.deb"
echo "==============================================="
