#!/bin/bash
set -e

echo "=========================================================="
echo "  ASUS Vivobook 14 Flip TP3407SA Speaker Fix Installer"
echo "=========================================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

# Ensure compiled binary exists
if [ ! -f "$SCRIPT_DIR/asus-sound-fix" ]; then
    echo "Compiling hardware activator..."
    gcc -O2 "$SCRIPT_DIR/asus-sound-fix.c" -o "$SCRIPT_DIR/asus-sound-fix"
fi

# 1. Install binary
echo "[1/5] Installing hardware activator to /usr/local/bin..."
sudo cp "$SCRIPT_DIR/asus-sound-fix" /usr/local/bin/asus-sound-fix
sudo chmod 755 /usr/local/bin/asus-sound-fix

# 2. Activate smart amplifier chips immediately
echo "[2/5] Waking up TAS2781 smart amplifiers on I2C bus..."
sudo /usr/local/bin/asus-sound-fix

# 3. Create boot systemd service
echo "[3/5] Installing boot systemd service..."
sudo tee /etc/systemd/system/asus-sound-fix.service > /dev/null << 'EOF'
[Unit]
Description=ASUS Vivobook 14 Flip TP3407SA Speaker Fix (TAS2781)
After=sound.target
Wants=sound.target

[Service]
Type=oneshot
ExecStartPre=/bin/bash -c 'until [ -e /dev/snd/controlC0 ] && [ -e /dev/i2c-0 ]; do sleep 0.5; done'
ExecStart=/usr/local/bin/asus-sound-fix
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

# 4. Create resume-from-sleep systemd service
echo "[4/5] Installing resume-from-sleep service (lid close/open fix)..."
sudo tee /etc/systemd/system/asus-sound-fix-resume.service > /dev/null << 'EOF'
[Unit]
Description=ASUS Vivobook TP3407SA Speaker Wake/Resume Fix
After=suspend.target hibernate.target hybrid-sleep.target suspend-then-hibernate.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/asus-sound-fix

[Install]
WantedBy=suspend.target hibernate.target hybrid-sleep.target suspend-then-hibernate.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable asus-sound-fix.service asus-sound-fix-resume.service

# 5. Apply audio volume and unmute settings
echo "[5/5] Unmuting ALSA and boosting volume to 150%..."
/home/sam/.local/bin/fix-audio-volume.sh

echo ""
echo "=========================================================="
echo "  Fix complete! Playing test sound through speakers now..."
echo "=========================================================="
pw-play /usr/share/mint-artwork/sounds/volume.oga || true
