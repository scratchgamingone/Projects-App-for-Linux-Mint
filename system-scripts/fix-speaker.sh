#!/usr/bin/env bash
set -e

# Ensure running with sudo/root privileges
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run this script with sudo: sudo ./fix-speaker.sh"
  exit 1
fi

echo "=========================================================="
echo "   ASUS Vivobook 14 Flip (TP3407) Audio Amplifier Fix     "
echo "=========================================================="

SRC_FIRMWARE="/lib/firmware/ti/audio/tas2781/TAS2XXX10A40.bin.zst"
if [ ! -f "$SRC_FIRMWARE" ]; then
  echo "[-] Error: Expected source firmware $SRC_FIRMWARE not found!"
  exit 1
fi

echo "[+] Found TP3407 amplifier firmware in system: $SRC_FIRMWARE"

# 1. Create missing symlinks in /lib/firmware/ti/audio/tas2781/
echo "[+] Creating missing firmware links in /lib/firmware/ti/audio/tas2781/..."
ln -sf TAS2XXX10A40.bin.zst /lib/firmware/ti/audio/tas2781/TAS2XXX10A4.bin.zst

# Decompress to provide uncompressed fallback as requested by kernel
echo "[+] Generating uncompressed TAS2XXX10A4.bin..."
zstd -dc "$SRC_FIRMWARE" > /lib/firmware/ti/audio/tas2781/TAS2XXX10A4.bin
chmod 644 /lib/firmware/ti/audio/tas2781/TAS2XXX10A4.bin

# 2. Create matching links in /lib/firmware/
echo "[+] Creating missing firmware links in /lib/firmware/..."
ln -sf ti/audio/tas2781/TAS2XXX10A40.bin.zst /lib/firmware/TAS2XXX10A4.bin.zst
ln -sf ti/audio/tas2781/TAS2XXX10A4.bin /lib/firmware/TAS2XXX10A4.bin

# Verify files
echo "[+] Firmware files verified:"
ls -la /lib/firmware/ti/audio/tas2781/TAS2XXX10A4* /lib/firmware/TAS2XXX10A4*

# 3. Update initramfs
echo "[+] Updating initramfs so firmware is available during early boot..."
update-initramfs -u

echo ""
echo "=========================================================="
echo "  [SUCCESS] Amplifier firmware linked and initramfs updated!"
echo "  Please REBOOT your laptop now to activate the speakers:  "
echo "      sudo reboot                                         "
echo "=========================================================="
