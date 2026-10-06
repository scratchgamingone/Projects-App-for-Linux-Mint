#!/usr/bin/env bash
set -e

SPICETIFY_CONFIG_DIR="${SPICETIFY_CONFIG_DIR:-$HOME/.config/spicetify}"
EXTENSIONS_DIR="$SPICETIFY_CONFIG_DIR/Extensions"

echo "=================================================="
echo "🗑️ Uninstalling AudioStats Spicetify Extension"
echo "=================================================="

# Remove from config
spicetify config extensions audioStats.js- || true

# Remove symlink/file
if [ -f "$EXTENSIONS_DIR/audioStats.js" ] || [ -L "$EXTENSIONS_DIR/audioStats.js" ]; then
  rm -f "$EXTENSIONS_DIR/audioStats.js"
  echo "🧹 Removed $EXTENSIONS_DIR/audioStats.js"
fi

echo "🚀 Re-applying Spicetify modifications..."
spicetify apply

echo "=================================================="
echo "✅ AudioStats Extension uninstalled successfully."
echo "=================================================="
