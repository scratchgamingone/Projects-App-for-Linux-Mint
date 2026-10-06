#!/bin/bash
set -e

# ==============================================================================
# Linux Mint Facial Recognition (Howdy) Auto-Setup Script
# Configured for ASUS FHD Webcam & Dedicated IR Camera (/dev/video2)
# ==============================================================================

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE}  Linux Mint Facial Recognition Setup (ASUS IR Camera)${NC}"
echo -e "${BLUE}======================================================${NC}\n"

# 1. Require Root / Sudo
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[!] This script must be run with sudo privileges.${NC}"
    echo -e "Please run: ${YELLOW}sudo bash $0${NC}"
    exit 1
fi

REAL_USER="${SUDO_USER:-sam}"
echo -e "${GREEN}[✓] Setting up face unlock for user: ${YELLOW}${REAL_USER}${NC}"

# 2. Add PPA (Ubuntu 24.04 / Mint 22 compatible build)
echo -e "\n${BLUE}[1/5] Adding Howdy PPA (ppa:ubuntuhandbook1/howdy)...${NC}"
if ! grep -rq "ubuntuhandbook1/howdy" /etc/apt/sources.list /etc/apt/sources.list.d/ 2>/dev/null; then
    add-apt-repository -y ppa:ubuntuhandbook1/howdy
else
    echo -e "${GREEN}[✓] PPA is already added.${NC}"
fi

# 3. Update Package List & Install Howdy
echo -e "\n${BLUE}[2/5] Installing Howdy & v4l-utils...${NC}"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y howdy v4l-utils

# 4. Locate and Configure Howdy config.ini
echo -e "\n${BLUE}[3/5] Configuring Howdy for ASUS IR Camera (/dev/video2)...${NC}"
CONFIG_PATH=""
if [ -f "/lib/security/howdy/config.ini" ]; then
    CONFIG_PATH="/lib/security/howdy/config.ini"
elif [ -f "/etc/howdy/config.ini" ]; then
    CONFIG_PATH="/etc/howdy/config.ini"
fi

if [ -n "$CONFIG_PATH" ]; then
    echo -e "Configuring ${CONFIG_PATH}..."
    # Set IR camera device path
    sed -i -E 's|^device_path\s*=.*|device_path = /dev/video2|' "$CONFIG_PATH"
    # Enable automatic unlock without requiring extra Enter confirmation
    sed -i -E 's|^no_confirmation\s*=.*|no_confirmation = true|' "$CONFIG_PATH"
    # Auto-login workaround: sends Enter key on successful face match so LightDM/greeter logs in automatically
    sed -i -E 's|^workaround\s*=.*|workaround = input|' "$CONFIG_PATH"
    # Set default certainty if present
    sed -i -E 's|^certainty\s*=.*|certainty = 3.5|' "$CONFIG_PATH"
    # Ensure detection notice is displayed
    sed -i -E 's|^detection_notice\s*=.*|detection_notice = true|' "$CONFIG_PATH"
    echo -e "${GREEN}[✓] Howdy configured successfully for /dev/video2!${NC}"
else
    echo -e "${RED}[!] Could not locate Howdy config.ini. Please check installation.${NC}"
fi

# 5. Configure LightDM PAM Integration
echo -e "\n${BLUE}[4/5] Verifying PAM Integration for LightDM & Lock Screen...${NC}"

# Determine which PAM module was installed (so or py)
HOWDY_PAM_LINE=""
if [ -f "/lib/security/pam_howdy.so" ]; then
    HOWDY_PAM_LINE="auth sufficient pam_howdy.so"
elif [ -f "/lib/security/howdy/pam.py" ]; then
    HOWDY_PAM_LINE="auth sufficient pam_python.so /lib/security/howdy/pam.py"
fi

if [ -n "$HOWDY_PAM_LINE" ]; then
    # LightDM login screen
    if ! grep -q "howdy" /etc/pam.d/lightdm 2>/dev/null; then
        echo -e "Adding Howdy to /etc/pam.d/lightdm..."
        cp /etc/pam.d/lightdm /etc/pam.d/lightdm.bak
        sed -i "/#%PAM-1.0/a ${HOWDY_PAM_LINE}" /etc/pam.d/lightdm
        echo -e "${GREEN}[✓] LightDM PAM configured.${NC}"
    else
        echo -e "${GREEN}[✓] LightDM already configured for Howdy.${NC}"
    fi
fi

# 6. Face Enrollment
echo -e "\n${BLUE}[5/5] Face Enrollment${NC}"
echo -e "${YELLOW}Please sit in your normal working posture facing the webcam.${NC}"
echo -e "The IR camera will turn on and scan your facial features.\n"

read -p "Press [Enter] when ready to scan your face..."

howdy -U "$REAL_USER" add

echo -e "\n${GREEN}======================================================${NC}"
echo -e "${GREEN}  Facial Recognition Setup Completed!${NC}"
echo -e "${GREEN}======================================================${NC}"
echo -e "• To lock your screen and test: Press ${YELLOW}Ctrl + Alt + L${NC} (or Super + L)."
echo -e "• To add more angles (e.g. smiling, glasses, dim light): run ${YELLOW}sudo howdy add${NC}."
echo -e "• To test the camera feed in real time: run ${YELLOW}sudo howdy test${NC}.\n"
