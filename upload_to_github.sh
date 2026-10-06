#!/usr/bin/env bash
# ==============================================================================
# Upload / Sync All Linux Mint Projects to GitHub
# Target: https://github.com/scratchgamingone/Projects-App-for-Linux-Mint
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

DEFAULT_REPO_NAME="scratchgamingone/Projects-App-for-Linux-Mint"
HTTPS_REMOTE_URL="https://github.com/${DEFAULT_REPO_NAME}.git"
SSH_REMOTE_URL="git@github.com:${DEFAULT_REPO_NAME}.git"
WEB_URL="https://github.com/${DEFAULT_REPO_NAME}"

# Parse optional arguments
USER_COMMIT_FLAG=""
AUTO_CONFIRM=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        -m|--message)
            USER_COMMIT_FLAG="$2"
            shift 2
            ;;
        -y|--yes)
            AUTO_CONFIRM=true
            shift
            ;;
        -h|--help)
            echo "Usage: ./upload_to_github.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -m, --message \"MSG\"   Specify commit message (bypasses prompt)"
            echo "  -y, --yes             Accept defaults without interactive prompts"
            echo "  -h, --help            Show this help dialog"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run ./upload_to_github.sh --help for options."
            exit 1
            ;;
    esac
done

# ANSI Colors
BOLD="\033[1m"
GREEN="\033[0;32m"
CYAN="\033[0;36m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
MAGENTA="\033[0;35m"
NC="\033[0m" # No Color

echo -e "${CYAN}================================================================${NC}"
echo -e "${BOLD}${CYAN}   🚀 Linux Mint Projects -> GitHub Upload & Sync Manager       ${NC}"
echo -e "${CYAN}================================================================${NC}"
echo -e "  Directory:  ${BOLD}${SCRIPT_DIR}${NC}"
echo -e "  Repository: ${BOLD}${WEB_URL}${NC}"
echo -e "${CYAN}----------------------------------------------------------------${NC}\n"

# 1. Check for Git
if ! command -v git >/dev/null 2>&1; then
    echo -e "${RED}❌ Git is not installed.${NC}"
    echo -e "Please install Git: ${BOLD}sudo apt update && sudo apt install git -y${NC}"
    exit 1
fi

# 2. Check Git User Identity
GIT_USER=$(git config user.name 2>/dev/null || true)
GIT_EMAIL=$(git config user.email 2>/dev/null || true)

if [ -z "${GIT_USER}" ] || [ -z "${GIT_EMAIL}" ]; then
    echo -e "${YELLOW}⚙️  Git author identity is not configured yet.${NC}"
    echo -e "Git requires a Name and Email to record who made the commit.\n"

    if [ -z "${GIT_USER}" ]; then
        if [ "${AUTO_CONFIRM}" = true ] || [ ! -t 0 ]; then
            GIT_USER="scratchgamingone"
        else
            read -p "Enter your GitHub username or display name [scratchgamingone]: " INPUT_USER || true
            GIT_USER="${INPUT_USER:-scratchgamingone}"
        fi
        git config --global user.name "${GIT_USER}"
    fi

    if [ -z "${GIT_EMAIL}" ]; then
        SUGGESTED_EMAIL="${GIT_USER}@users.noreply.github.com"
        if [ "${AUTO_CONFIRM}" = true ] || [ ! -t 0 ]; then
            GIT_EMAIL="${SUGGESTED_EMAIL}"
        else
            read -p "Enter your email [${SUGGESTED_EMAIL}]: " INPUT_EMAIL || true
            GIT_EMAIL="${INPUT_EMAIL:-$SUGGESTED_EMAIL}"
        fi
        git config --global user.email "${GIT_EMAIL}"
    fi
    echo -e "${GREEN}✓ Author identity configured: ${GIT_USER} <${GIT_EMAIL}>${NC}\n"
else
    echo -e "${GREEN}✓ Author: ${GIT_USER} <${GIT_EMAIL}>${NC}"
fi

# 3. Enable Git Credential Storage (remembers GitHub PAT so user doesn't re-type)
CURRENT_HELPER=$(git config --global credential.helper || true)
if [ -z "${CURRENT_HELPER}" ]; then
    echo -e "${CYAN}💡 Enabling Git credential store to remember your GitHub token.${NC}"
    git config --global credential.helper store
fi

# 4. Handle Nested .git folders (e.g. roblox-caffeine)
# Embedded .git folders make Git treat them as empty submodules instead of uploading the files!
while IFS= read -r nested_git; do
    if [ -d "${nested_git}" ]; then
        parent_dir="$(dirname "${nested_git}")"
        backup_dir="${parent_dir}/.git_backup"
        echo -e "${YELLOW}⚠️  Detected embedded Git repository in: ${parent_dir}${NC}"
        echo -e "   Moving to ${backup_dir} so its project files upload properly to GitHub..."
        mv "${nested_git}" "${backup_dir}"
    fi
done < <(find "${SCRIPT_DIR}" -mindepth 2 -type d -name ".git" 2>/dev/null || true)

# 5. Fix Symlinks: Ensure project symlinks are relative for cross-system portability
if [ -L "${SCRIPT_DIR}/check_dependencies.sh" ]; then
    ln -sfn install_or_update_all_projects.sh "${SCRIPT_DIR}/check_dependencies.sh"
fi
if [ -L "${SCRIPT_DIR}/install_or_update_projects.sh" ]; then
    ln -sfn install_or_update_all_projects.sh "${SCRIPT_DIR}/install_or_update_projects.sh"
fi
if [ -L "${SCRIPT_DIR}/update_dependencies.sh" ]; then
    ln -sfn install_or_update_all_projects.sh "${SCRIPT_DIR}/update_dependencies.sh"
fi

# 6. Initialize Git repository if needed
if [ ! -d "${SCRIPT_DIR}/.git" ]; then
    echo -e "${CYAN}📦 Initializing new Git repository in ${SCRIPT_DIR}...${NC}"
    git init -b main
else
    # Ensure branch name is main
    CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "main")
    if [ -z "${CURRENT_BRANCH}" ] || [ "${CURRENT_BRANCH}" != "main" ]; then
        git branch -M main 2>/dev/null || true
    fi
fi

# 7. Configure Remote Origin
CURRENT_REMOTE=$(git remote get-url origin 2>/dev/null || true)
if [ -z "${CURRENT_REMOTE}" ]; then
    echo -e "${CYAN}🔗 Setting remote 'origin' to: ${HTTPS_REMOTE_URL}${NC}"
    git remote add origin "${HTTPS_REMOTE_URL}"
elif [ "${CURRENT_REMOTE}" != "${HTTPS_REMOTE_URL}" ] && [ "${CURRENT_REMOTE}" != "${SSH_REMOTE_URL}" ]; then
    echo -e "${YELLOW}Existing remote origin points to: ${CURRENT_REMOTE}${NC}"
    if [ ! -t 0 ]; then
        CONFIRM_REMOTE="y"
    else
        read -p "Update remote origin to ${HTTPS_REMOTE_URL}? [Y/n]: " CONFIRM_REMOTE || true
    fi
    if [[ ! "${CONFIRM_REMOTE}" =~ ^[Nn]$ ]]; then
        git remote set-url origin "${HTTPS_REMOTE_URL}"
        echo -e "${GREEN}✓ Updated remote origin to ${HTTPS_REMOTE_URL}${NC}"
    fi
fi

# 8. Check and Stage Files
echo -e "\n${CYAN}🔍 Inspecting project files and staging changes...${NC}"
git add -A

# Check if there are staged changes
if git diff --cached --quiet; then
    echo -e "${GREEN}✓ Working tree is clean. No uncommitted changes.${NC}"
    
    # Check if we are ahead of remote
    git fetch origin main 2>/dev/null || true
    AHEAD_COUNT=$(git rev-list --count origin/main..main 2>/dev/null || echo "1")
    if [ "${AHEAD_COUNT}" -eq 0 ]; then
        echo -e "${GREEN}🎉 All local commits are already up to date on GitHub!${NC}"
        echo -e "   View repo: ${BOLD}${WEB_URL}${NC}"
        exit 0
    fi
else
    # Show staged files summary
    CHANGES_COUNT=$(git status --porcelain | wc -l)
    echo -e "${CYAN}📁 Staged ${BOLD}${CHANGES_COUNT}${NC}${CYAN} files/directories for commit.${NC}"

    # Default commit message
    COMMIT_COUNT=$(git rev-list --count HEAD 2>/dev/null || echo "0")
    if [ "${COMMIT_COUNT}" -eq 0 ]; then
        DEFAULT_MSG="Initial commit: Linux Mint Projects Collection"
    else
        DEFAULT_MSG="Update projects: $(date '+%Y-%m-%d %H:%M:%S')"
    fi

    if [ -n "${USER_COMMIT_FLAG}" ]; then
        COMMIT_MSG="${USER_COMMIT_FLAG}"
    elif [ "${AUTO_CONFIRM}" = true ] || [ ! -t 0 ]; then
        COMMIT_MSG="${DEFAULT_MSG}"
    else
        echo ""
        read -p "Enter commit message [${DEFAULT_MSG}]: " USER_MSG || true
        COMMIT_MSG="${USER_MSG:-$DEFAULT_MSG}"
    fi

    echo -e "\n${CYAN}💾 Committing changes...${NC}"
    git commit -m "${COMMIT_MSG}"
fi

# 9. Authentication Guidance Banner
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "${HTTPS_REMOTE_URL}")
echo -e "\n${CYAN}----------------------------------------------------------------${NC}"
echo -e "${BOLD}${MAGENTA}🔑 GitHub Authentication Note:${NC}"
if [[ "${REMOTE_URL}" =~ ^https:// ]]; then
    echo -e " GitHub requires a ${BOLD}Personal Access Token (PAT)${NC} instead of an account password."
    echo -e " If Git prompts you for credentials:"
    echo -e "   1. Username: ${BOLD}scratchgamingone${NC}"
    echo -e "   2. Password: ${BOLD}Your GitHub Personal Access Token (classic)${NC}"
    echo -e " To create a token: ${CYAN}https://github.com/settings/tokens${NC} (Check the ${BOLD}'repo'${NC} scope)"
    echo -e " (Your token will be saved on this PC so you only have to paste it once)."
fi
echo -e "${CYAN}----------------------------------------------------------------${NC}\n"

# 10. Push to GitHub
echo -e "${CYAN}🚀 Pushing branch 'main' to GitHub (origin)...${NC}"

# If remote already has commits on main, rebase gently first
if git ls-remote --exit-code origin main >/dev/null 2>&1; then
    echo -e "Checking remote commits..."
    git pull --rebase origin main 2>/dev/null || true
fi

# Perform git push
if git push -u origin main; then
    echo ""
    echo -e "${GREEN}================================================================${NC}"
    echo -e "${BOLD}${GREEN}   ✅ All project files uploaded successfully to GitHub!       ${NC}"
    echo -e "${GREEN}================================================================${NC}"
    echo -e "  🌐 View your repository online:"
    echo -e "     ${BOLD}${CYAN}${WEB_URL}${NC}"
    echo -e "${GREEN}================================================================${NC}"
else
    echo ""
    echo -e "${RED}================================================================${NC}"
    echo -e "${BOLD}${RED}   ❌ Push failed. Troubleshooting:                            ${NC}"
    echo -e "${RED}================================================================${NC}"
    echo -e "1. ${BOLD}Permission Denied (403) / Authentication Failed:${NC}"
    echo -e "   - ${BOLD}If using a Fine-Grained Token (github_pat_...):${NC}"
    echo -e "     Go to GitHub Settings -> Developer settings -> Fine-grained tokens"
    echo -e "     Edit your token -> under 'Repository permissions', set ${BOLD}'Contents'${NC} to ${BOLD}'Read and write'${NC}!"
    echo -e "   - ${BOLD}If creating a Classic Token (ghp_...):${NC}"
    echo -e "     Go to: ${CYAN}https://github.com/settings/tokens/new${NC}"
    echo -e "     Check the ${BOLD}'repo'${NC} checkbox (Full control of repositories)."
    echo -e "     Copy token and save it."
    echo -e ""
    echo -e "2. ${BOLD}Prefer SSH Key?${NC}"
    echo -e "   Run: ${BOLD}git remote set-url origin ${SSH_REMOTE_URL}${NC}"
    echo -e "${RED}================================================================${NC}"
    exit 1
fi
