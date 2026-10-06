#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${PROJECT_ROOT}/build"
PKG_DIR="${BUILD_DIR}/pkg"
DEB_NAME="mintsweep_1.0.0_all.deb"

echo "==> Preparing build directory..."
rm -rf "${BUILD_DIR}"
mkdir -p "${PKG_DIR}/DEBIAN"
mkdir -p "${PKG_DIR}/usr/bin"
mkdir -p "${PKG_DIR}/usr/share/mintsweep/src"
mkdir -p "${PKG_DIR}/usr/share/applications"
mkdir -p "${PKG_DIR}/usr/share/icons/hicolor/scalable/apps"

echo "==> Copying metadata and control files..."
cp "${PROJECT_ROOT}/debian/control" "${PKG_DIR}/DEBIAN/"
cp "${PROJECT_ROOT}/debian/postinst" "${PKG_DIR}/DEBIAN/"
chmod 755 "${PKG_DIR}/DEBIAN/postinst"

echo "==> Copying binary and application files..."
cp "${PROJECT_ROOT}/bin/mintsweep" "${PKG_DIR}/usr/bin/mintsweep"
chmod 755 "${PKG_DIR}/usr/bin/mintsweep"

cp "${PROJECT_ROOT}/src/"*.py "${PKG_DIR}/usr/share/mintsweep/src/"

echo "==> Copying desktop launcher and icons..."
cp "${PROJECT_ROOT}/data/mintsweep.desktop" "${PKG_DIR}/usr/share/applications/"
cp "${PROJECT_ROOT}/data/icons/mintsweep.svg" "${PKG_DIR}/usr/share/icons/hicolor/scalable/apps/"

echo "==> Setting file permissions..."
find "${PKG_DIR}" -type d -exec chmod 755 {} +
find "${PKG_DIR}/usr/share" -type f -exec chmod 644 {} +
chmod 755 "${PKG_DIR}/usr/bin/mintsweep"

echo "==> Building .deb package..."
dpkg-deb --build --root-owner-group "${PKG_DIR}" "${PROJECT_ROOT}/${DEB_NAME}"

echo ""
echo "=========================================================="
echo " SUCCESS! Package generated:"
echo "   ${PROJECT_ROOT}/${DEB_NAME}"
echo ""
echo " To install on your Linux Mint system:"
echo "   sudo apt install ./${DEB_NAME}"
echo " Or with dpkg:"
echo "   sudo dpkg -i ./${DEB_NAME}"
echo "=========================================================="
