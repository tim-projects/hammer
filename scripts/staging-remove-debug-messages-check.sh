#!/bin/bash
# staging-remove-debug-messages-check.sh
# Script to scan for debug messages before promoting to main
# Ignores tests folder, hidden folders, log folders, tasks folders, and dependency directories

echo "Scanning for debug messages (excluding tests, hidden folders, log folders, tasks folders, and dependency directories)..."

# Find all relevant files, excluding specified directories
# Then search for debug patterns in those files

# Create a temporary file to hold the list of files to search
TEMP_FILE=$(mktemp)

# Clean up temp file on exit
trap "rm -f $TEMP_FILE" EXIT

# Find files to search (excluding ignored directories)
find . -type f \
    \( -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.tsx" -o -name "*.java" -o -name "*.cpp" -o -name "*.c" -o -name "*.cs" -o -name "*.go" -o -name "*.rs" \) \
    ! -path "./tests/*" \
    ! -path "*/.*/*" \
    ! -path "./.*" \
    ! -path "./log/*" \
    ! -path "./logs/*" \
    ! -path "./.tasks/*" \
    ! -path "./tasks/*" \
    ! -path "*/log/*" \
    ! -path "*/logs/*" \
    ! -path "*/.tasks/*" \
    ! -path "*/tasks/*" \
    ! -path "./venv/*" \
    ! -path "*/venv/*" \
    ! -path "./node_modules/*" \
    ! -path "*/node_modules/*" \
    ! -path "./__pycache__/*" \
    ! -path "*/__pycache__/*" \
    ! -path "./.git/*" \
    ! -path "*/.git/*" \
    > "$TEMP_FILE"

# Check if any files were found
if [ ! -s "$TEMP_FILE" ]; then
    echo "No files to scan."
    exit 0
fi

# Define debug patterns to search for - focus on likely accidental debug code
DEBUG_PATTERNS=(
    "pdb.set_trace()"
    "breakpoint()"
    "debugger;"
    "TODO:"
    "FIXME:"
    "DEBUG:"
)

# Search for debug patterns in the found files
FOUND_DEBUG=false
for pattern in "${DEBUG_PATTERNS[@]}"; do
    if grep -n "$pattern" "$TEMP_FILE" | grep -v "^Binary file" > /dev/null; then
        echo ""
        echo "Found pattern: $pattern"
        grep -n "$pattern" "$TEMP_FILE" | grep -v "^Binary file"
        FOUND_DEBUG=true
    fi
done

# Also look for print statements that might be debug (simple heuristic)
# Look for print statements that contain typical debug variable names or values
if grep -n "print(" "$TEMP_FILE" | grep -v "^Binary file" | grep -i -E "print.*tmp|print.*temp|print.*debug|print.*test|print.*var|print.*data|print.*val|print.*result|print.*err|print.*fail|print.*success|print.*[0-9]" > /dev/null; then
    echo ""
    echo "Found potentially debug-like print statements:"
    grep -n "print(" "$TEMP_FILE" | grep -v "^Binary file" | grep -i -E "print.*tmp|print.*temp|print.*debug|print.*test|print.*var|print.*data|print.*val|print.*result|print.*err|print.*fail|print.*success|print.*[0-9]"
    FOUND_DEBUG=true
fi

# Also check for console.log that seems debug-like
if grep -n "console\.log" "$TEMP_FILE" | grep -v "^Binary file" | grep -i -E "console\.log.*tmp|console\.log.*temp|console\.log.*debug|console\.log.*test|console\.log.*var|console\.log.*data|console\.log.*val|console\.log.*result|console\.log.*err|console\.log.*fail|console\.log.*success|console\.log.*[0-9]" > /dev/null; then
    echo ""
    echo "Found potentially debug-like console.log statements:"
    grep -n "console\.log" "$TEMP_FILE" | grep -v "^Binary file" | grep -i -E "console\.log.*tmp|console\.log.*temp|console\.log.*debug|console\.log.*test|console\.log.*var|console\.log.*data|console\.log.*val|console\.log.*result|console\.log.*err|console\.log.*fail|console\.log.*success|console\.log.*[0-9]"
    FOUND_DEBUG=true
fi

# Clean up
rm -f "$TEMP_FILE"
trap - EXIT

if [ "$FOUND_DEBUG" = true ]; then
    echo ""
    echo "WARNING: Debug messages found! Please review and remove them before promoting to main."
    exit 1
else
    echo ""
    echo "No debug messages found. OK to proceed."
    exit 0
fi