#!/usr/bin/env bash
# ==============================================================================
# Seerr / Jellyseerr Automated Setup Script for JellyScratch Server
# ==============================================================================
set -e

# Resolve real path in case called via symlink
REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
SEERR_DIR="${SCRIPT_DIR}"
TARGET_USER="${SUDO_USER:-$USER}"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE}     Seerr / Jellyseerr Setup for JellyScratch Server   ${NC}"
echo -e "${BLUE}======================================================${NC}"

# Check for root/sudo if docker or compose is missing
if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
    if [ "$EUID" -ne 0 ]; then
        echo -e "\n${YELLOW}[!] Docker is not installed yet.${NC}"
        echo -e "Please run this setup script with sudo:"
        echo -e "  ${GREEN}sudo $0${NC}\n"
        exit 1
    fi
    echo -e "\n${BLUE}==> Step 1: Installing Docker and Docker Compose plugin...${NC}"
    apt-get update -y
    apt-get install -y docker.io docker-compose-v2 curl

    echo -e "\n${BLUE}==> Step 2: Enabling and starting Docker daemon...${NC}"
    systemctl daemon-reload
    systemctl enable docker
    systemctl restart docker

    if [ -n "$TARGET_USER" ] && [ "$TARGET_USER" != "root" ]; then
        echo -e "${BLUE}==> Adding user '${TARGET_USER}' to the docker group...${NC}"
        usermod -aG docker "$TARGET_USER"
    fi
fi

# Ensure config directory exists with appropriate permissions inside SEERR_DIR only
echo -e "\n${BLUE}==> Step 3: Preparing Seerr configuration storage...${NC}"
mkdir -p "${SEERR_DIR}/config"
if [ -n "$TARGET_USER" ] && [ "$TARGET_USER" != "root" ]; then
    chown -R "${TARGET_USER}:${TARGET_USER}" "${SEERR_DIR}" 2>/dev/null || true
fi
chmod -R 775 "${SEERR_DIR}/config"

# Start the Seerr container using Docker Compose
echo -e "\n${BLUE}==> Step 4: Starting Seerr container...${NC}"
cd "${SEERR_DIR}"
docker compose up -d

# Verification
echo -e "\n${BLUE}==> Step 5: Waiting for Seerr to start...${NC}"
MAX_WAIT=30
WAITED=0
ONLINE=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -s -f http://localhost:5055/api/v1/status >/dev/null 2>&1 || curl -s http://localhost:5055 >/dev/null 2>&1; then
        ONLINE=1
        break
    fi
    sleep 2
    WAITED=$((WAITED + 2))
    echo -n "."
done
echo ""

LOCAL_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7}' || hostname -I | awk '{print $1}')

if [ $ONLINE -eq 1 ]; then
    echo -e "${GREEN}======================================================${NC}"
    echo -e "${GREEN}   ✔ Seerr / Jellyseerr is up and running!            ${NC}"
    echo -e "${GREEN}======================================================${NC}"
    echo -e "\nOpen the web interface in your browser to complete initial setup:"
    echo -e "  Local access:   ${YELLOW}http://localhost:5055${NC}"
    echo -e "  Network access: ${YELLOW}http://${LOCAL_IP}:5055${NC}"
    echo -e "\n${BLUE}Connecting to your JellyScratch Server:${NC}"
    echo -e "  1. On the welcome screen, select '${YELLOW}Jellyfin${NC}' as your Media Server."
    echo -e "  2. For the Jellyfin Host/URL, enter:"
    echo -e "     ${GREEN}http://host.docker.internal:8096${NC}  (or http://${LOCAL_IP}:8096)"
    echo -e "  3. Sign in with your Jellyfin admin username & password."
    echo -e "  4. Select your Jellyfin libraries (Movies, TV Shows) to sync."
    echo -e "  5. (Optional) Connect Radarr (Movies) & Sonarr (TV) under Settings -> Services."
    echo -e "\nTo manage Seerr in the future:"
    echo -e "  Stop:    cd ${SEERR_DIR} && docker compose down"
    echo -e "  Start:   cd ${SEERR_DIR} && docker compose up -d"
    echo -e "  Update:  cd ${SEERR_DIR} && docker compose pull && docker compose up -d\n"
else
    echo -e "${YELLOW}[!] Seerr is starting up in the background.${NC}"
    echo -e "Check status with: ${BLUE}docker compose ps${NC} or ${BLUE}docker compose logs -f${NC}"
    echo -e "Web interface will be available at: ${YELLOW}http://localhost:5055${NC}\n"
fi
