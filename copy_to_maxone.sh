#!/usr/bin/env bash
# ==============================================================================
# Copy / Sync all Projects to Maxone External Hard Drive
# ==============================================================================

MAXONE_PATH="/media/sam/1A164C0F164BEA79"
TARGET_DIR="$MAXONE_PATH/Projects"
SOURCE_DIR="/home/sam/Projects"

echo "=========================================================="
echo "   Omni Projects Backup -> Maxone External Hard Drive    "
echo "=========================================================="

if [ ! -d "$MAXONE_PATH" ]; then
    echo "❌ ERROR: Maxone hard drive is not mounted at $MAXONE_PATH"
    echo "Please connect the Maxone USB hard drive and try again."
    read -p "Press Enter to exit..."
    exit 1
fi

echo "✓ Maxone drive detected at: $MAXONE_PATH"
echo "✓ Source: $SOURCE_DIR"
echo "✓ Destination: $TARGET_DIR"
echo ""

mkdir -p "$TARGET_DIR"

echo "⏳ Copying/Syncing files (skipping unchanged files)..."
rsync -rlth --progress \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.git' \
    "$SOURCE_DIR/" "$TARGET_DIR/"

echo ""
echo "=========================================================="
echo "✅ All projects successfully copied to Maxone hard drive!"
echo "   Location: $TARGET_DIR"
echo "=========================================================="
read -p "Press Enter to close..."
