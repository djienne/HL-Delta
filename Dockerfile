FROM python:3.10-slim

# Set build arguments
ARG VERSION=1.0.0

# Set working directory
WORKDIR /app

# Add metadata labels
LABEL maintainer="HyperVault Team <admin@draxdev.xyz>"
LABEL version="${VERSION}"
LABEL description="HyperVault Delta Bot for automated delta-neutral trading"
LABEL org.opencontainers.image.title="HyperVault Delta"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.vendor="HyperVault"

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libc6-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV API_HOST=0.0.0.0
ENV API_PORT=8080
ENV AUTOSTART_BOT=true
ENV BOT_VERSION=${VERSION}
ENV API_ENABLED=true

# Expose API port
EXPOSE 8080

# Define entrypoint that runs the delta bot
ENTRYPOINT ["python", "entrypoint.py"] 