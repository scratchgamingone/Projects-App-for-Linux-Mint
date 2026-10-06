#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPICETIFY_CONFIG_DIR="${SPICETIFY_CONFIG_DIR:-$HOME/.config/spicetify}"
EXTENSIONS_DIR="$SPICETIFY_CONFIG_DIR/Extensions"

echo "=================================================="
echo "📊 Installing AudioStats Spicetify Extension"
echo "=================================================="

# Ensure Spicetify is installed
if ! command -v spicetify &> /dev/null; then
  echo "❌ Error: 'spicetify' command not found. Please ensure Spicetify CLI is in your PATH."
  exit 1
fi

# Ensure Extensions directory exists
mkdir -p "$EXTENSIONS_DIR"

# Symlink or copy the extension file
TARGET_FILE="$EXTENSIONS_DIR/audioStats.js"
SOURCE_FILE="$SCRIPT_DIR/audioStats.js"

echo "🔗 Symlinking extension into $TARGET_FILE..."
ln -sf "$SOURCE_FILE" "$TARGET_FILE"

# Add extension to Spicetify config if not already present
echo "⚙️ Configuring Spicetify extensions..."
spicetify config extensions audioStats.js

echo "🚀 Applying Spicetify modifications..."
spicetify apply

echo "=================================================="
echo "✅ AudioStats Extension installed and applied successfully!"
echo "   Restart Spotify or check the playbar and topbar for the 📊 button."
echo "=================================================="
