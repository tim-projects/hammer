#!/bin/bash
# Reset the --dev environment (/tmp/.tasks)

echo "Resetting --dev environment..."

rm -rf /tmp/.tasks
mkdir -p /tmp/.tasks

echo "Dev environment reset. Run 'python tasks.py --dev init' to reinitialize."