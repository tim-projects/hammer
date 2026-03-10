#!/bin/bash

# Exit on error
set -e

# Check for python3
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed."
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
# Using --break-system-packages for environments that require it (like recent Debian/Ubuntu)
# but attempting standard install first.
pip3 install python-frontmatter --break-system-packages || pip3 install python-frontmatter || {
    echo "Warning: Standard pip install failed. If you are on a managed environment, please install dependencies manually."
}

# Define source and destination
SOURCE_FILE="tasks.py"
DEST_PATH="/usr/local/bin/tasks"

# Check if script exists
if [ ! -f "$SOURCE_FILE" ]; then
    echo "Error: $SOURCE_FILE not found in current directory."
    exit 1
fi

# Copy and make executable
echo "Installing tasks-ai to $DEST_PATH..."
sudo cp "$SOURCE_FILE" "$DEST_PATH"
sudo chmod +x "$DEST_PATH"

echo "Installation complete! You can now use 'tasks' from anywhere."
