#!/bin/bash
set -e

echo "=== Fixing ASUS Vivobook TP3407SA Built-in Speaker Driver ==="

# 1. Create the missing firmware symlink for TAS2781 smart amplifier
echo "[1/2] Linking TAS2781 firmware..."
sudo ln -sf /lib/firmware/ti/audio/tas2781/TAS2XXX10A40.bin.zst /lib/firmware/TAS2XXX10A4.bin.zst
sudo ln -sf TAS2XXX10A40.bin.zst /lib/firmware/ti/audio/tas2781/TAS2XXX10A4.bin.zst

echo "Firmware files verified:"
ls -l /lib/firmware/TAS2XXX10A4*

# 2. Reboot into the updated 7.0 kernel
echo ""
echo "[2/2] Kernel 7.0.0-38-generic is already installed with the fixed driver."
echo "A reboot into kernel 7.0 is required to initialize the smart amplifier hardware."
echo ""
read -p "Reboot system now? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    systemctl reboot
fi
