#!/bin/bash

# Production entrypoint script for Orion API

set -e

echo "🚀 Starting Orion API..."

# Wait for any initialization
echo "⏳ Initializing..."

# Create necessary directories
mkdir -p /app/uploads
mkdir -p /app/logs

# Set proper permissions
chown -R orion:orion /app/uploads /app/logs

# Start the application
echo "🎯 Starting FastAPI application..."
exec uvicorn src.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    --access-log \
    --log-level info
