#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$SCRIPT_DIR/pkg"
DEB_NAME="omniboot-usb_1.0.0_amd64.deb"

echo "=== Cleaning previous build directory ==="
rm -rf "$PKG_ROOT" "$SCRIPT_DIR/$DEB_NAME"

echo "=== Creating directory structure ==="
mkdir -p "$PKG_ROOT/DEBIAN"
mkdir -p "$PKG_ROOT/usr/bin"
mkdir -p "$PKG_ROOT/usr/lib/omniboot-usb/ventoy"
mkdir -p "$PKG_ROOT/usr/share/applications"
mkdir -p "$PKG_ROOT/usr/share/icons/hicolor/scalable/apps"
mkdir -p "$PKG_ROOT/usr/share/polkit-1/actions"

echo "=== Copying packaging control files ==="
cp "$SCRIPT_DIR/debian-control" "$PKG_ROOT/DEBIAN/control"
cp "$SCRIPT_DIR/debian-postinst" "$PKG_ROOT/DEBIAN/postinst"
chmod 755 "$PKG_ROOT/DEBIAN/postinst"

echo "=== Copying executables and python modules ==="
cp "$SCRIPT_DIR/omniboot-usb-bin" "$PKG_ROOT/usr/bin/omniboot-usb"
chmod 755 "$PKG_ROOT/usr/bin/omniboot-usb"

cp "$SCRIPT_DIR/main.py" "$PKG_ROOT/usr/lib/omniboot-usb/"
cp "$SCRIPT_DIR/backend.py" "$PKG_ROOT/usr/lib/omniboot-usb/"
cp "$SCRIPT_DIR/detector.py" "$PKG_ROOT/usr/lib/omniboot-usb/"
chmod 755 "$PKG_ROOT/usr/lib/omniboot-usb/main.py"
chmod 755 "$PKG_ROOT/usr/lib/omniboot-usb/backend.py"
chmod 644 "$PKG_ROOT/usr/lib/omniboot-usb/detector.py"

echo "=== Bundling Ventoy engine ==="
if [ -d "$SCRIPT_DIR/ventoy-1.1.17" ]; then
    cp -r "$SCRIPT_DIR/ventoy-1.1.17/boot" "$PKG_ROOT/usr/lib/omniboot-usb/ventoy/"
    cp -r "$SCRIPT_DIR/ventoy-1.1.17/tool" "$PKG_ROOT/usr/lib/omniboot-usb/ventoy/"
    cp -r "$SCRIPT_DIR/ventoy-1.1.17/ventoy" "$PKG_ROOT/usr/lib/omniboot-usb/ventoy/"
    cp "$SCRIPT_DIR/ventoy-1.1.17/Ventoy2Disk.sh" "$PKG_ROOT/usr/lib/omniboot-usb/ventoy/"
    chmod +x "$PKG_ROOT/usr/lib/omniboot-usb/ventoy/Ventoy2Disk.sh"
    chmod +x -R "$PKG_ROOT/usr/lib/omniboot-usb/ventoy/tool"
else
    echo "ERROR: ventoy-1.1.17 directory not found!"
    exit 1
fi

echo "=== Copying desktop, icon, and polkit files ==="
cp "$SCRIPT_DIR/omniboot-usb.desktop" "$PKG_ROOT/usr/share/applications/"
chmod 644 "$PKG_ROOT/usr/share/applications/omniboot-usb.desktop"

cp "$SCRIPT_DIR/omniboot-usb.svg" "$PKG_ROOT/usr/share/icons/hicolor/scalable/apps/"
cp "$SCRIPT_DIR/omniboot-usb.svg" "$PKG_ROOT/usr/lib/omniboot-usb/"
chmod 644 "$PKG_ROOT/usr/share/icons/hicolor/scalable/apps/omniboot-usb.svg"

cp "$SCRIPT_DIR/org.omniboot.policy" "$PKG_ROOT/usr/share/polkit-1/actions/"
chmod 644 "$PKG_ROOT/usr/share/polkit-1/actions/org.omniboot.policy"

echo "=== Setting root ownership for package files ==="
# dpkg-deb supports --root-owner-group so fakechroot/fakeroot is not strictly required
echo "=== Building .deb package with dpkg-deb ==="
dpkg-deb --build --root-owner-group "$PKG_ROOT" "$SCRIPT_DIR/$DEB_NAME"

echo "=== Build Complete! Package created at: $SCRIPT_DIR/$DEB_NAME ==="
ls -lh "$SCRIPT_DIR/$DEB_NAME"
