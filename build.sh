#!/bin/bash
# Build script for the Delta bot

# Read version from VERSION file
VERSION=$(cat VERSION)
BASE_IMAGE_NAME="hypervault-tradingbot:delta"
IMAGE_NAME="${BASE_IMAGE_NAME}-${VERSION}"

echo "Building Delta bot image: ${BASE_IMAGE_NAME} version ${VERSION}"

# Build the Docker image with two tags - one with version and one without
docker build -t ${BASE_IMAGE_NAME} -t ${IMAGE_NAME} --build-arg VERSION=${VERSION} .

# Check if build was successful
if [ $? -eq 0 ]; then
    echo "Build successful!"
    echo "Images created:"
    echo "- ${BASE_IMAGE_NAME} (latest)"
    echo "- ${IMAGE_NAME} (versioned)"
    echo ""
    echo "You can run the bot with the following command:"
    echo "docker run -d --name delta-bot -p 8080:8080 --env-file .env ${IMAGE_NAME}"
    echo ""
    echo "Or via the HyperVault Trading Bots admin interface."
else
    echo "Build failed."
    exit 1
fi 