#!/bin/bash
# Version updater script for Delta bot

# Check if a version argument was provided
if [ -z "$1" ]; then
  echo "Usage: $0 <new_version>"
  echo "Example: $0 1.1.0"
  exit 1
fi

NEW_VERSION=$1
CURRENT_VERSION=$(cat VERSION)

echo "Updating version from $CURRENT_VERSION to $NEW_VERSION..."

# Update VERSION file
echo "$NEW_VERSION" > VERSION

echo "Version updated successfully!"
echo "To build the new version, run: ./build.sh" 