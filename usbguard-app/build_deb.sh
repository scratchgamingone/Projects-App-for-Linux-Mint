#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}"
SRC_DIR="${PROJECT_DIR}/src"
PKG_DIR="${PROJECT_DIR}/debian-pkg"
OUTPUT_DEB="${PROJECT_DIR}/usbguard-manager_1.0.0_all.deb"

echo "=== Preparing debian package structure ==="

# Create directories
mkdir -p "${PKG_DIR}/DEBIAN"
mkdir -p "${PKG_DIR}/usr/bin"
mkdir -p "${PKG_DIR}/usr/share/usbguard-manager"
mkdir -p "${PKG_DIR}/usr/share/applications"
mkdir -p "${PKG_DIR}/usr/share/icons/hicolor/scalable/apps"
mkdir -p "${PKG_DIR}/usr/lib/usbguard-manager"
mkdir -p "${PKG_DIR}/usr/share/polkit-1/actions"
mkdir -p "${PKG_DIR}/etc/usbguard/IPCAccessControl.d"

# Copy python app files
cp -v "${SRC_DIR}/main.py" "${PKG_DIR}/usr/share/usbguard-manager/"
cp -v "${SRC_DIR}/backend.py" "${PKG_DIR}/usr/share/usbguard-manager/"
cp -v "${SRC_DIR}/models.py" "${PKG_DIR}/usr/share/usbguard-manager/"
cp -v "${SRC_DIR}/watcher.py" "${PKG_DIR}/usr/share/usbguard-manager/"
cp -v "${SRC_DIR}/ui.py" "${PKG_DIR}/usr/share/usbguard-manager/"
cp -v "${SRC_DIR}/dialogs.py" "${PKG_DIR}/usr/share/usbguard-manager/"

# Copy launcher
cp -v "${SRC_DIR}/usbguard-manager" "${PKG_DIR}/usr/bin/"
chmod 755 "${PKG_DIR}/usr/bin/usbguard-manager"

# Copy helper
cp -v "${SRC_DIR}/usbguard-helper" "${PKG_DIR}/usr/lib/usbguard-manager/"
chmod 755 "${PKG_DIR}/usr/lib/usbguard-manager/usbguard-helper"

# Copy desktop file
cp -v "${SRC_DIR}/usbguard-manager.desktop" "${PKG_DIR}/usr/share/applications/"
chmod 644 "${PKG_DIR}/usr/share/applications/usbguard-manager.desktop"

# Copy polkit policy
cp -v "${SRC_DIR}/org.usbguard.manager.policy" "${PKG_DIR}/usr/share/polkit-1/actions/"
chmod 644 "${PKG_DIR}/usr/share/polkit-1/actions/org.usbguard.manager.policy"

# Copy icon
cp -v "${SRC_DIR}/usbguard-manager.svg" "${PKG_DIR}/usr/share/icons/hicolor/scalable/apps/"
chmod 644 "${PKG_DIR}/usr/share/icons/hicolor/scalable/apps/usbguard-manager.svg"

# Ensure permissions on maintainer scripts
chmod 755 "${PKG_DIR}/DEBIAN/postinst"
chmod 755 "${PKG_DIR}/DEBIAN/postrm"

# Fix permissions on package files
chmod -R u=rwX,go=rX "${PKG_DIR}/usr"

echo "=== Building Debian Package with dpkg-deb ==="
dpkg-deb --build --root-owner-group "${PKG_DIR}" "${OUTPUT_DEB}"

echo "=== Package built successfully at: ${OUTPUT_DEB} ==="
ls -lh "${OUTPUT_DEB}"
dpkg-deb -I "${OUTPUT_DEB}"
dpkg-deb -c "${OUTPUT_DEB}"
