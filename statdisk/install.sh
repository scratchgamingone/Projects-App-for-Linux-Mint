#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_DEB="${SCRIPT_DIR}/statdisk_1.0.0_all.deb"

echo "==============================================="
echo "          StatDisk Installer                   "
echo "==============================================="

if [ "$(id -u)" -eq 0 ]; then
    echo "Installing system-wide .deb package via dpkg..."
    if [ ! -f "${PKG_DEB}" ]; then
        "${SCRIPT_DIR}/build_deb.sh"
    fi
    dpkg -i "${PKG_DEB}" || apt-get install -f -y
    echo "System-wide installation complete! StatDisk is in your Application Menu."
    exit 0
fi

# User-level installation (No sudo required)
echo "Installing for current user ($(whoami))..."
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"
ICON_BASE="${HOME}/.local/share/icons/hicolor"
SITE_PKG_DIR="${HOME}/.local/lib/python3.12/site-packages/statdisk"

mkdir -p "${BIN_DIR}" "${APP_DIR}" "${SITE_PKG_DIR}"

# Copy application source into user site-packages
rm -rf "${SITE_PKG_DIR}"/*
cp -r "${SCRIPT_DIR}/src/statdisk/"* "${SITE_PKG_DIR}/"

# Copy icons
for size in 16 24 32 48 64 128 256 512; do
    if [ -f "${SCRIPT_DIR}/src/statdisk/assets/icon-${size}.png" ]; then
        mkdir -p "${ICON_BASE}/${size}x${size}/apps"
        cp "${SCRIPT_DIR}/src/statdisk/assets/icon-${size}.png" \
           "${ICON_BASE}/${size}x${size}/apps/statdisk.png"
    fi
done

if [ -f "${SCRIPT_DIR}/src/statdisk/assets/statdisk.svg" ]; then
    mkdir -p "${ICON_BASE}/scalable/apps"
    cp "${SCRIPT_DIR}/src/statdisk/assets/statdisk.svg" \
       "${ICON_BASE}/scalable/apps/statdisk.svg"
fi

# Create user bin launcher
cat << 'EOF' > "${BIN_DIR}/statdisk"
#!/usr/bin/env python3
import sys
from statdisk.main import main

if __name__ == "__main__":
    main()
EOF
chmod +x "${BIN_DIR}/statdisk"

# Create user .desktop file
cat << EOF > "${APP_DIR}/statdisk.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=StatDisk
GenericName=Disk Space & Statistical Analyzer
Comment=Interactive storage visualizer with advanced statistical modeling, heavy-tail distributions, and inequality metrics
Exec=${BIN_DIR}/statdisk %U
Icon=statdisk
Terminal=false
Categories=Projects;Utility;System;FileTools;Science;Math;
Keywords=disk;storage;usage;space;analyzer;squirreldisk;statistics;distribution;outliers;lorenz;gini;pareto;
StartupNotify=true
StartupWMClass=io.github.statdisk.analyzer
MimeType=inode/directory;
EOF
chmod +x "${APP_DIR}/statdisk.desktop"

# Update desktop & icon caches
if which update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APP_DIR}" >/dev/null 2>&1 || true
fi
if which gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -t -f "${ICON_BASE}" >/dev/null 2>&1 || true
fi

echo "==============================================="
echo "SUCCESS: StatDisk is installed!"
echo "It has been added to your Linux Mint Application Menu."
echo "You can launch it directly from the Menu or run:"
echo "    statdisk"
echo ""
echo "Or install the system-wide .deb with:"
echo "    sudo dpkg -i /home/sam/statdisk_1.0.0_all.deb"
echo "==============================================="
