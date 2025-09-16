#!/bin/bash

# Simple wrapper script to run the full workflow test
# This script provides a clean interface and handles common setup

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🧪 Orion System Test Runner${NC}"
echo "============================"

# Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ Please run this script from the orion project root directory${NC}"
    exit 1
fi

# Check for PDF files
if [ ! -d "$HOME/Desktop/books" ] || [ -z "$(find "$HOME/Desktop/books" -name "*.pdf" | head -1)" ]; then
    echo -e "${RED}❌ No PDF files found in $HOME/Desktop/books${NC}"
    echo "Please add some PDF files to test with."
    exit 1
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  No .env file found${NC}"
    echo "Creating a template .env file..."
    cat > .env << EOF
# Cohere API Configuration
COHERE_API_KEY=your_cohere_api_key_here

# Application Configuration
LOG_LEVEL=INFO
DEBUG=false

# File Processing Configuration
MAX_FILE_SIZE=52428800
CHUNK_SIZE=512
CHUNK_OVERLAP_PERCENT=0.1

# Storage Configuration
VECTOR_STORAGE_TYPE=json
EOF
    echo -e "${YELLOW}⚠️  Please edit .env and add your Cohere API key${NC}"
    echo "Then run this script again."
    exit 1
fi

# Check if Cohere API key is set
if ! grep -q "COHERE_API_KEY=.*[a-zA-Z0-9]" .env; then
    echo -e "${RED}❌ Please set your COHERE_API_KEY in the .env file${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All prerequisites met${NC}"

# Ask user what they want to do
echo ""
echo "What would you like to do?"
echo "1) Run full workflow test (recommended)"
echo "2) Run quick test"
echo "3) Check system status only"
echo "4) View logs"
echo ""
read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        echo -e "${BLUE}Running full workflow test...${NC}"
        ./scripts/test_full_workflow.sh
        ;;
    2)
        echo -e "${BLUE}Running quick test...${NC}"
        # Start container if not running
        if ! docker-compose ps | grep -q "Up"; then
            echo "Starting Docker container..."
            docker-compose up -d
            sleep 10
        fi
        ./scripts/quick_test.sh
        ;;
    3)
        echo -e "${BLUE}Checking system status...${NC}"
        ./scripts/check_status.sh
        ;;
    4)
        echo -e "${BLUE}Viewing logs...${NC}"
        if docker-compose ps | grep -q "Up"; then
            docker-compose logs --tail=50 -f
        else
            echo -e "${RED}❌ Container is not running${NC}"
        fi
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}🎉 Test runner completed!${NC}"
echo ""
echo "Useful commands:"
echo "  ./scripts/check_status.sh    - Check system status"
echo "  docker-compose logs          - View logs"
echo "  docker-compose down          - Stop the system"
echo "  docker-compose up -d         - Start the system"
