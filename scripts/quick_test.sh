#!/bin/bash

# Quick Test Script for Orion
# This is a simplified version for quick testing

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

API_BASE_URL="http://localhost:8000"
TEST_EMAIL="test@example.com"
BOOKS_DIR="sdk/examples/book-samples"

echo -e "${BLUE}🚀 Orion Quick Test${NC}"
echo "==================="

# Check if API is running
echo -e "${BLUE}Checking API status...${NC}"
if curl -s "$API_BASE_URL/health" > /dev/null; then
    echo -e "${GREEN}✅ API is running${NC}"
else
    echo -e "${RED}❌ API is not running. Start with: docker-compose up -d${NC}"
    exit 1
fi

# Clear any existing uploads for clean test
echo -e "${BLUE}Cleaning up previous uploads...${NC}"
rm -rf $HOME/Desktop/orion/$TEST_EMAIL 2>/dev/null || true
echo -e "${GREEN}✅ Clean slate ready${NC}"

# Upload Romeo and Juliet specifically
echo -e "${BLUE}Uploading Romeo and Juliet...${NC}"
text_file="$BOOKS_DIR/romeo-and-juliet.txt"
if [ -f "$text_file" ]; then
    response=$(curl -s -X POST \
        -F "file=@$text_file" \
        -F "email=$TEST_EMAIL" \
        "$API_BASE_URL/v1/upload")
    
    if echo "$response" | grep -q "successfully"; then
        echo -e "${GREEN}✅ Upload successful${NC}"
    else
        echo -e "${RED}❌ Upload failed${NC}"
        echo "$response"
    fi
else
    echo -e "${RED}❌ Romeo and Juliet not found: $text_file${NC}"
    exit 1
fi

# Wait a bit for processing
echo -e "${BLUE}Waiting for processing...${NC}"
sleep 60

# Check library stats
echo -e "${BLUE}Checking library stats...${NC}"
stats=$(curl -s "$API_BASE_URL/v1/query/library/$TEST_EMAIL/stats")
echo "$stats" | jq '.' 2>/dev/null || echo "$stats"

# Perform a simple query
echo -e "${BLUE}Performing test query...${NC}"
query_response=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d '{"email":"'$TEST_EMAIL'","query":"love","algorithm":"cosine","limit":3}' \
    "$API_BASE_URL/v1/query")

if echo "$query_response" | grep -q "results"; then
    echo -e "${GREEN}✅ Query successful${NC}"
    result_count=$(echo "$query_response" | jq '.results | length' 2>/dev/null)
    echo "Results found: $result_count"
    
    if [ "$result_count" -gt 0 ]; then
        echo -e "${BLUE}📄 Search Results:${NC}"
        echo "$query_response" | jq -r '.results[] | "
🔍 Rank \(.rank) | Score: \(.similarity_score | .*100 | floor)%
📁 File: \(.original_filename) | Chunk: \(.chunk_index)
📝 Text: \(.text | .[0:200])...\n"' 2>/dev/null || echo "Could not parse results"
    else
        echo -e "${YELLOW}No search results found${NC}"
    fi
else
    echo -e "${RED}❌ Query failed${NC}"
    echo "$query_response"
fi

echo -e "${GREEN}🎉 Quick test completed!${NC}"
