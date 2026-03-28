#!/bin/bash

# Exit on error
set -e

# Default values
MODE="local"
DEST_DIR="$HOME/.local/bin"
UNINSTALL=false

# Parse arguments
for arg in "$@"; do
  case $arg in
    -g|--system)
      MODE="system"
      DEST_DIR="/usr/local/bin"
      ;;
    -u|--user)
      MODE="local"
      DEST_DIR="$HOME/.local/bin"
      ;;
    --uninstall)
      UNINSTALL=true
      ;;
    -h|--help)
      echo "Usage: install.sh [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  -u, --user      Install locally to ~/.local/bin (default)"
      echo "  -g, --system    Install system-wide to /usr/local/bin (requires sudo)"
      echo "  --uninstall     Remove existing installation"
      echo "  -h, --help      Show this help message"
      exit 0
      ;;
  esac
done

# If no mode specified and no uninstall, ask user
if [ "$MODE" == "local" ] && [ -z "$1" ]; then
  echo "Select installation mode:"
  echo "  1) User (installs to ~/.local/bin)"
  echo "  2) System-wide (installs to /usr/local/bin - requires sudo)"
  read -p "Enter choice [1]: " choice
  choice=${choice:-1}
  if [ "$choice" == "2" ]; then
    MODE="system"
    DEST_DIR="/usr/local/bin"
  fi
fi

# If system mode, check for sudo
if [ "$MODE" == "system" ] && [ "$EUID" -ne 0 ]; then
  echo "Error: System-wide installation requires root privileges."
  echo "Please run with sudo: sudo $0 $@"
  exit 1
fi

# Check for existing installations and remove them
remove_existing() {
  local path="$1"
  if [ -f "$path" ]; then
    echo "Removing existing installation at $path..."
    rm -f "$path"
  fi
}

echo "Checking for existing installations..."
remove_existing "$HOME/.local/bin/tasks-ai"
remove_existing "/usr/local/bin/tasks-ai"
remove_existing "$HOME/.local/bin/tasks"
remove_existing "/usr/local/bin/tasks"
remove_existing "$HOME/.local/bin/repo"
remove_existing "/usr/local/bin/repo"
remove_existing "$HOME/.local/bin/check"
remove_existing "/usr/local/bin/check"
echo "Done."

# Handle uninstall
if [ "$UNINSTALL" == "true" ]; then
  echo "Uninstallation complete!"
  exit 0
fi

# Check for python3
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed. Tasks AI requires Python 3."
    exit 1
fi

# Define source and destination
SOURCE_FILES=("tasks.py" "tasks_ai" "repo.py" "check.py")
DEST_DIR="$DEST_DIR"

# Ensure destination directory exists
if [ ! -d "$DEST_DIR" ]; then
    echo "Creating directory $DEST_DIR..."
    mkdir -p "$DEST_DIR"
fi

# Copy files
echo "Installing Tasks AI..."
for src in "${SOURCE_FILES[@]}"; do
    if [ -d "$src" ]; then
        cp -r "$src" "$DEST_DIR/"
    else
        cp "$src" "$DEST_DIR/"
    fi
done

# Set executable for the entry point
chmod +x "$DEST_DIR/tasks.py"

if [ -L "$DEST_DIR/tasks-ai" ]; then
    rm "$DEST_DIR/tasks-ai"
fi
if [ -L "$DEST_DIR/tasks" ]; then
    rm "$DEST_DIR/tasks"
fi
ln -s "$DEST_DIR/tasks.py" "$DEST_DIR/tasks"

if [ -f "$DEST_DIR/repo.py" ]; then
    chmod +x "$DEST_DIR/repo.py"
fi
if [ -L "$DEST_DIR/repo" ]; then
    rm "$DEST_DIR/repo"
fi
ln -s "$DEST_DIR/repo.py" "$DEST_DIR/repo"
ln -s "$DEST_DIR/repo.py" "$DEST_DIR/r"

if [ -f "$DEST_DIR/check.py" ]; then
    chmod +x "$DEST_DIR/check.py"
fi
if [ -L "$DEST_DIR/check" ]; then
    rm "$DEST_DIR/check"
fi
ln -s "$DEST_DIR/check.py" "$DEST_DIR/check"

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
echo "You can now run: tasks -h"
echo "                 check lint"
echo "--------------------------------------------------"