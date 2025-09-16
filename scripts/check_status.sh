#!/bin/bash

# Status Check Script for Orion
# Checks the current status of the system

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

API_BASE_URL="http://localhost:8000"
TEST_EMAIL="test@example.com"

echo -e "${BLUE}🔍 Orion System Status Check${NC}"
echo "============================="

# Check Docker container
echo -e "${BLUE}Docker Container Status:${NC}"
if docker-compose ps | grep -q "Up"; then
    echo -e "${GREEN}✅ Container is running${NC}"
else
    echo -e "${RED}❌ Container is not running${NC}"
    echo "Start with: docker-compose up -d"
fi

# Check API health
echo -e "\n${BLUE}API Health:${NC}"
if curl -s "$API_BASE_URL/health" > /dev/null; then
    echo -e "${GREEN}✅ API is responding${NC}"
    
    # Check endpoints
    echo -e "\n${BLUE}API Endpoints:${NC}"
    
    # Check algorithms endpoint
    algorithms=$(curl -s "$API_BASE_URL/v1/query/algorithms" 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ /v1/query/algorithms${NC} - $algorithms"
    else
        echo -e "${RED}❌ /v1/query/algorithms${NC}"
    fi
    
    # Check library stats
    stats=$(curl -s "$API_BASE_URL/v1/query/library/$TEST_EMAIL/stats" 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ /v1/query/library/{email}/stats${NC}"
        
        # Parse stats
        exists=$(echo "$stats" | jq -r '.exists' 2>/dev/null || echo "false")
        doc_count=$(echo "$stats" | jq -r '.document_count' 2>/dev/null || echo "0")
        chunk_count=$(echo "$stats" | jq -r '.chunks_with_embeddings' 2>/dev/null || echo "0")
        
        if [ "$exists" = "true" ] && [ "$doc_count" -gt 0 ] && [ "$chunk_count" -gt 0 ]; then
            echo -e "   ${GREEN}📚 Library: $doc_count documents, $chunk_count embedded chunks${NC}"
        elif [ "$exists" = "true" ]; then
            echo -e "   ${YELLOW}📚 Library exists but no processed documents${NC}"
        else
            echo -e "   ${YELLOW}📚 No library found for $TEST_EMAIL${NC}"
        fi
    else
        echo -e "${RED}❌ /v1/query/library/{email}/stats${NC}"
    fi
    
else
    echo -e "${RED}❌ API is not responding${NC}"
fi

# Check file system
echo -e "\n${BLUE}File System:${NC}"
orion_dir="$HOME/Desktop/orion"
if [ -d "$orion_dir" ]; then
    echo -e "${GREEN}✅ Orion data directory exists: $orion_dir${NC}"
    
    # Check user directory
    user_dir="$orion_dir/$TEST_EMAIL"
    if [ -d "$user_dir" ]; then
        echo -e "${GREEN}✅ User directory exists${NC}"
        
        # Count files in each subdirectory
        for subdir in raw_uploads processed_text raw_chunks processed_vectors; do
            dir_path="$user_dir/$subdir"
            if [ -d "$dir_path" ]; then
                file_count=$(find "$dir_path" -type f | wc -l)
                echo -e "   📁 $subdir: $file_count files"
            fi
        done
    else
        echo -e "${YELLOW}⚠️  No user directory found${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Orion data directory not found${NC}"
fi

# Check logs
echo -e "\n${BLUE}Recent Logs:${NC}"
if docker-compose ps | grep -q "Up"; then
    echo "Last 5 log entries:"
    docker-compose logs --tail=5
else
    echo -e "${YELLOW}⚠️  Container not running, no logs available${NC}"
fi

echo -e "\n${BLUE}Status check completed!${NC}"
