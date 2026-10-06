#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${PROJECT_ROOT}/build"
PKG_DIR="${BUILD_DIR}/pkg"
DEB_NAME="mintstatlab_1.0.0_all.deb"

echo "==> [MintStatLab] Preparing build directory..."
rm -rf "${BUILD_DIR}"
mkdir -p "${PKG_DIR}/DEBIAN"
mkdir -p "${PKG_DIR}/usr/bin"
mkdir -p "${PKG_DIR}/usr/share/mintstatlab/src"
mkdir -p "${PKG_DIR}/usr/share/applications"
mkdir -p "${PKG_DIR}/usr/share/icons/hicolor/scalable/apps"

echo "==> [MintStatLab] Copying metadata and control files..."
cp "${PROJECT_ROOT}/debian/control" "${PKG_DIR}/DEBIAN/"
cp "${PROJECT_ROOT}/debian/postinst" "${PKG_DIR}/DEBIAN/"
chmod 755 "${PKG_DIR}/DEBIAN/postinst"

echo "==> [MintStatLab] Copying binary and python source files..."
cp "${PROJECT_ROOT}/bin/mintstatlab" "${PKG_DIR}/usr/bin/mintstatlab"
chmod 755 "${PKG_DIR}/usr/bin/mintstatlab"

cp "${PROJECT_ROOT}/src/"*.py "${PKG_DIR}/usr/share/mintstatlab/src/"

echo "==> [MintStatLab] Copying desktop launcher and icons..."
cp "${PROJECT_ROOT}/data/mintstatlab.desktop" "${PKG_DIR}/usr/share/applications/"
cp "${PROJECT_ROOT}/data/icons/mintstatlab.svg" "${PKG_DIR}/usr/share/icons/hicolor/scalable/apps/"

echo "==> [MintStatLab] Setting package file permissions..."
find "${PKG_DIR}" -type d -exec chmod 755 {} +
find "${PKG_DIR}/usr/share" -type f -exec chmod 644 {} +
chmod 755 "${PKG_DIR}/usr/bin/mintstatlab"

echo "==> [MintStatLab] Building .deb package..."
dpkg-deb --build --root-owner-group "${PKG_DIR}" "${PROJECT_ROOT}/${DEB_NAME}"

echo ""
echo "=========================================================="
echo " ✅ SUCCESS! MintStatLab Debian package generated:"
echo "    ${PROJECT_ROOT}/${DEB_NAME}"
echo ""
echo " To install system-wide:"
echo "    sudo dpkg -i ./${DEB_NAME}"
echo "=========================================================="
