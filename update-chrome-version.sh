#!/bin/bash

# Script to update Chrome to latest stable version
# Usage: ./update-chrome-version.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION_FILE="$SCRIPT_DIR/chrome-version.txt"

echo "Fetching latest Chrome stable version..."

# Get latest stable version from Google's API
API_RESPONSE=$(curl -s "https://versionhistory.googleapis.com/v1/chrome/platforms/linux/channels/stable/versions/all/releases?filter=endtime=none&order_by=version%20desc")

if [ -z "$API_RESPONSE" ]; then
    echo "Error: Could not connect to Chrome version API"
    exit 1
fi

LATEST_VERSION=$(echo "$API_RESPONSE" | grep -o '"version": "[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$LATEST_VERSION" ]; then
    echo "Error: Could not parse Chrome version from API response"
    echo "API Response: $API_RESPONSE"
    exit 1
fi

# Chrome package versions have -1 suffix
NEW_VERSION="${LATEST_VERSION}-1"

# Read current version if file exists
if [ -f "$VERSION_FILE" ]; then
    CURRENT_VERSION=$(cat "$VERSION_FILE")
    echo "Current version: $CURRENT_VERSION"
    
    if [ "$CURRENT_VERSION" = "$NEW_VERSION" ]; then
        echo "Already using latest version: $NEW_VERSION"
        exit 0
    fi
else
    echo "Version file does not exist, creating..."
fi

# Update version file
echo "$NEW_VERSION" > "$VERSION_FILE"
echo "Updated to latest Chrome version: $NEW_VERSION"

# Show git diff if in a git repo
if git rev-parse --git-dir > /dev/null 2>&1; then
    echo ""
    echo "Git diff:"
    git diff "$VERSION_FILE" || true
fi

echo ""
echo "To rebuild Docker image with new Chrome version:"
echo "docker compose build"