#!/bin/bash

# Docker setup validation script
echo "🐳 Docker Setup Validation"
echo "=========================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    echo "   Please install Docker Desktop from: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Docker daemon is not running"
    echo "   Please start Docker Desktop"
    exit 1
fi

echo "✅ Docker is installed and running"

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose is not installed"
    echo "   Please install docker-compose"
    exit 1
fi

echo "✅ docker-compose is available"

# Validate Dockerfile syntax
echo "🔍 Validating Dockerfile..."
if docker build --dry-run . &> /dev/null; then
    echo "✅ Dockerfile syntax is valid"
else
    echo "❌ Dockerfile has syntax errors"
    exit 1
fi

# Validate docker-compose.yml
echo "🔍 Validating docker-compose.yml..."
if docker-compose config &> /dev/null; then
    echo "✅ docker-compose.yml is valid"
else
    echo "❌ docker-compose.yml has syntax errors"
    exit 1
fi

echo ""
echo "🎉 Docker setup is ready!"
echo ""
echo "To build and run:"
echo "  make build"
echo "  make run"
echo ""
echo "To run development version:"
echo "  make dev"
