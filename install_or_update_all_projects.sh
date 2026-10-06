#!/usr/bin/env bash
# ==============================================================================
# Omni Projects: Install or Update All Projects & Dependencies
# ==============================================================================
# Usage:
#   ./install_or_update_all_projects.sh             # Full install & update all
#   ./install_or_update_all_projects.sh -p          # Projects & desktop apps only (no sudo)
#   ./install_or_update_all_projects.sh -d          # Dependencies only
#   ./install_or_update_all_projects.sh -c          # Audit check only
#   ./install_or_update_all_projects.sh -n          # Dry-run simulation
# ==============================================================================

set -euo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/install_or_update_all_projects.py"

if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Error: Python 3 is required."
    echo "Please install python3: sudo apt install python3"
    exit 1
fi

chmod +x "${PYTHON_SCRIPT}"
exec python3 "${PYTHON_SCRIPT}" "$@"
