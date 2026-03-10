#!/bin/bash

# Exit on error
set -e

# Default values
MODE="local"
DEST_DIR="$HOME/.local/bin"

# Parse arguments
for arg in "$@"; do
  case $arg in
    -g|--system)
      MODE="system"
      DEST_DIR="/usr/local/bin"
      ;;
    -l|--local)
      MODE="local"
      DEST_DIR="$HOME/.local/bin"
      ;;
  esac
done

# If system mode, check for root
if [ "$MODE" == "system" ] && [ "$EUID" -ne 0 ]; then
    echo "Error: Global installation (-g) requires root privileges. Please run with sudo."
    exit 1
fi

# Check for python3
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed. Tasks AI requires Python 3."
    exit 1
fi

# Define source and destination
SOURCE_FILE="tasks.py"
DEST_PATH="$DEST_DIR/tasks-ai"

# Check if script exists
if [ ! -f "$SOURCE_FILE" ]; then
    echo "Error: $SOURCE_FILE not found in current directory."
    exit 1
fi

# Ensure destination directory exists
if [ ! -d "$DEST_DIR" ]; then
    echo "Creating directory $DEST_DIR..."
    mkdir -p "$DEST_DIR"
fi

# Copy and make executable
echo "Installing Tasks AI to $DEST_PATH..."
cp "$SOURCE_FILE" "$DEST_PATH"
chmod +x "$DEST_PATH"

echo "--------------------------------------------------"
echo "Installation complete!"
if [ "$MODE" == "local" ]; then
    # Check if DEST_DIR is in PATH
    if [[ ":$PATH:" != *":$DEST_DIR:"* ]]; then
        echo "Warning: $DEST_DIR is not in your PATH."
        echo "Add this to your .bashrc or .zshrc:"
        echo "  export PATH=\$PATH:\$HOME/.local/bin"
    fi
fi
echo "You can now run: tasks-ai -h"
echo "--------------------------------------------------"
