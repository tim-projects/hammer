#!/bin/bash
# Test environment setup and management script
# Usage:
#   ./scripts/test-setup.sh reset    - Reset dev environment (/tmp/.tasks)
#   ./scripts/test-setup.sh init    - Initialize dev environment with config
#   ./scripts/test-setup.sh clean   - Clean up any stale test repos in /tmp

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

reset_dev() {
    echo "Resetting dev environment..."
    rm -rf /tmp/.tasks
    mkdir -p /tmp/.tasks
    echo "Dev environment reset."
}

init_dev() {
    echo "Initializing dev environment with config..."
    
    # Create config in dev location
    mkdir -p /tmp/.tasks
    
    cat > /tmp/.tasks/config.yaml << 'EOF'
repo:
  lint: /bin/true
  test: /bin/true
  type_check: /bin/true
  format: /bin/true
  skip_push: true
EOF
    
    # Initialize tasks
    cd "$PROJECT_ROOT"
    python tasks.py --dev init
    
    echo "Dev environment initialized with config."
}

clean_temp_repos() {
    echo "Cleaning up stale test repos in /tmp..."
    
    # Find and remove any temp test repos
    for dir in /tmp/tmp*/repo; do
        if [ -d "$dir" ]; then
            echo "Removing stale test repo: $dir"
            rm -rf "$(dirname "$dir")"
        fi
    done
    
    echo "Cleanup complete."
}

case "${1:-}" in
    reset)
        reset_dev
        ;;
    init)
        init_dev
        ;;
    clean)
        clean_temp_repos
        ;;
    *)
        echo "Usage: $0 {reset|init|clean}"
        echo ""
        echo "Commands:"
        echo "  reset - Reset dev environment (/tmp/.tasks) - USE WITH CAUTION"
        echo "  init  - Initialize dev environment with config"
        echo "  clean - Clean up stale test repos in /tmp"
        exit 1
        ;;
esac
