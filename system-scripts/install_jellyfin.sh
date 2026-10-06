#!/usr/bin/env bash
# ==============================================================================
# Jellyfin Automated Installer for Ubuntu / Linux Mint
# ==============================================================================
set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE}       Jellyfin Media Server Automatic Installer      ${NC}"
echo -e "${BLUE}======================================================${NC}"

# Check for root / sudo
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[ERROR] This installer must be run as root or with sudo.${NC}"
  echo -e "Please run: ${YELLOW}sudo ./install_jellyfin.sh${NC}"
  exit 1
fi

echo -e "\n${BLUE}==> Step 1: Installing essential system dependencies...${NC}"
apt-get update -y
apt-get install -y curl gnupg ca-certificates software-properties-common

# Ensure universe repository is enabled (standard dependency requirement for ffmpeg)
if ! grep -q "^deb.*universe" /etc/apt/sources.list /etc/apt/sources.list.d/* 2>/dev/null; then
    echo -e "${BLUE}==> Enabling universe repository...${NC}"
    add-apt-repository -y universe
    apt-get update -y
fi

echo -e "\n${BLUE}==> Step 2: Running official Jellyfin repository installer...${NC}"
curl -fsSL https://repo.jellyfin.org/install-debuntu.sh | bash

echo -e "\n${BLUE}==> Step 3: Enabling and starting Jellyfin service...${NC}"
systemctl daemon-reload
systemctl enable jellyfin
systemctl restart jellyfin

# Check if UFW firewall is active and allow port 8096
if ufw status | grep -qw "active"; then
    echo -e "${BLUE}==> Opening port 8096 in UFW firewall...${NC}"
    ufw allow 8096/tcp comment 'Jellyfin Media Server'
fi

# Verification
if systemctl is-active --quiet jellyfin; then
    LOCAL_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7}' || echo "localhost")
    echo -e "\n${GREEN}======================================================${NC}"
    echo -e "${GREEN}   ✔ Jellyfin Media Server installed successfully!    ${NC}"
    echo -e "${GREEN}======================================================${NC}"
    echo -e "\nYou can now access the Jellyfin Web UI at:"
    echo -e "  Local:   ${YELLOW}http://localhost:8096${NC}"
    echo -e "  Network: ${YELLOW}http://${LOCAL_IP}:8096${NC}"
    echo -e "\nNext steps:"
    echo -e "  1. Open http://localhost:8096 in your browser to complete initial setup."
    echo -e "  2. Go to: Dashboard -> API Keys -> click '+' to generate an API key."
    echo -e "  3. Use that API key with the Discord Webhook monitor script.\n"
else
    echo -e "\n${RED}[!] Jellyfin service did not report active status.${NC}"
    echo -e "Run 'systemctl status jellyfin' or 'journalctl -u jellyfin -n 50' for details."
fi
