#!/bin/bash

# Local End-to-End Integration Test Runner
# This script runs the same integration test locally that runs in GitHub Actions

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
log() {
    local color=$1
    local message=$2
    echo -e "${color}$message${NC}"
}

# Check if we're in the right directory
if [ ! -d "orion_sdk" ]; then
    log $RED "ERROR: Must be run from the SDK root directory"
    log $RED "   Current directory: $(pwd)"
    log $RED "   Expected to find: orion_sdk/ directory"
    exit 1
fi

log $BLUE "Orion Local End-to-End Integration Test"
log $BLUE "======================================="

# Check prerequisites
log $YELLOW "Checking prerequisites..."

# Check Cohere API key
if [ -z "$COHERE_API_KEY" ]; then
    log $RED "ERROR: COHERE_API_KEY environment variable not set"
    log $RED "   Set it with: export COHERE_API_KEY='your-key-here'"
    exit 1
fi
log $GREEN "PASS: Cohere API key found"

# Check Docker
if ! command -v docker &> /dev/null; then
    log $RED "ERROR: Docker is not installed"
    exit 1
fi
log $GREEN "PASS: Docker found: $(docker --version)"

# Check Python
if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
    log $RED "ERROR: Python is not installed"
    exit 1
fi

PYTHON_CMD="python"
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
fi
log $GREEN "PASS: Python found: $($PYTHON_CMD --version)"

# Check book samples
if [ ! -d "examples/book-samples" ]; then
    log $RED "ERROR: examples/book-samples directory not found"
    log $RED "   Please create this directory and add text files"
    exit 1
fi

TEXT_COUNT=$(find examples/book-samples -name "*.txt" | wc -l)
if [ $TEXT_COUNT -lt 3 ]; then
    log $RED "ERROR: Need at least 3 text files in examples/book-samples/"
    log $RED "   Found $TEXT_COUNT text files"
    log $RED "   Please add more text files for testing"
    exit 1
fi
log $GREEN "PASS: Found $TEXT_COUNT text files for testing"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    log $YELLOW "Creating virtual environment..."
    $PYTHON_CMD -m venv venv
fi

# Activate virtual environment
log $YELLOW "Setting up environment..."
source venv/bin/activate

# Install dependencies
log $YELLOW "Installing dependencies..."
pip install --upgrade pip > /dev/null 2>&1
pip install -e .[dev] > /dev/null 2>&1
pip install requests > /dev/null 2>&1

log $GREEN "PASS: Environment setup complete"

# Run the integration test
log $BLUE "Starting integration test..."
echo ""

# Export the API key for the test script
export COHERE_API_KEY="$COHERE_API_KEY"

# Run the test
if $PYTHON_CMD integration-tests/test_e2e_integration.py; then
    log $GREEN "PASS: Integration test completed successfully!"
    
    # Show summary if report exists
    if [ -f "integration-tests/last_test_report.json" ]; then
        echo ""
        log $BLUE "Quick Summary:"
        $PYTHON_CMD -c "
import json
try:
    with open('integration-tests/last_test_report.json', 'r') as f:
        results = json.load(f)
    
    uploads = results.get('file_uploads', [])
    success_count = len([u for u in uploads if u.get('status') == 'uploaded'])
    
    print(f'  Uploads: {success_count}/{len(uploads)} successful')
    print(f'  Cosine Search: {\"PASS\" if results.get(\"cosine_search\") else \"FAIL\"}')
    print(f'  Hybrid Search: {\"PASS\" if results.get(\"hybrid_search\") else \"FAIL\"}')
    
except Exception as e:
    print(f'  WARN: Could not read test summary: {e}')
"
    fi
    
    exit 0
else
    log $RED "FAIL: Integration test failed!"
    
    # Show error summary if report exists
    if [ -f "integration-tests/last_test_report.json" ]; then
        echo ""
        log $YELLOW "Failure Summary:"
        $PYTHON_CMD -c "
import json
try:
    with open('integration-tests/last_test_report.json', 'r') as f:
        results = json.load(f)
    
    failed_steps = [k for k, v in results.items() if k != 'file_uploads' and k != 'search_results' and not v]
    if failed_steps:
        print(f'  FAIL: Failed steps: {', '.join(failed_steps)}')
    
    uploads = results.get('file_uploads', [])
    failed_uploads = [u for u in uploads if u.get('status') != 'uploaded']
    if failed_uploads:
        print(f'  FAIL: Failed uploads: {len(failed_uploads)}')
        for upload in failed_uploads:
            print(f'    - {upload.get(\"filename\", \"unknown\")}: {upload.get(\"error\", \"unknown error\")}')
    
except Exception as e:
    print(f'  WARN: Could not read failure details: {e}')
"
    fi
    
    exit 1
fi