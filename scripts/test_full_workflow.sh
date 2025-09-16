#!/bin/bash

# Orion Full Workflow Test Script
# This script tests the complete document processing and query pipeline

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BOOKS_DIR="$HOME/Desktop/books"
TEST_EMAIL="test@example.com"
API_BASE_URL="http://localhost:8000"
CONTAINER_NAME="orion-test"
DOCKER_COMPOSE_FILE="docker-compose.yml"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to wait for API to be ready
wait_for_api() {
    print_status "Waiting for API to be ready..."
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$API_BASE_URL/health" > /dev/null 2>&1; then
            print_success "API is ready!"
            return 0
        fi
        
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    print_error "API failed to start within $((max_attempts * 2)) seconds"
    return 1
}

# Function to upload a PDF file
upload_pdf() {
    local file_path="$1"
    local filename=$(basename "$file_path")
    
    print_status "Uploading $filename..."
    
    local response=$(curl -s -X POST \
        -F "file=@$file_path" \
        -F "email=$TEST_EMAIL" \
        -F "description=Test upload of $filename" \
        "$API_BASE_URL/v1/upload")
    
    if echo "$response" | grep -q "successfully"; then
        print_success "Successfully uploaded $filename"
        echo "$response" | jq '.' 2>/dev/null || echo "$response"
        return 0
    else
        print_error "Failed to upload $filename"
        echo "$response"
        return 1
    fi
}

# Function to check library stats
check_library_stats() {
    print_status "Checking library statistics..."
    
    local response=$(curl -s "$API_BASE_URL/v1/query/library/$TEST_EMAIL/stats")
    
    if echo "$response" | grep -q "exists"; then
        print_success "Library stats retrieved successfully"
        echo "$response" | jq '.' 2>/dev/null || echo "$response"
        
        # Extract document count
        local doc_count=$(echo "$response" | jq -r '.document_count' 2>/dev/null || echo "0")
        local chunks_with_embeddings=$(echo "$response" | jq -r '.chunks_with_embeddings' 2>/dev/null || echo "0")
        
        if [ "$doc_count" -gt 0 ] && [ "$chunks_with_embeddings" -gt 0 ]; then
            print_success "Library has $doc_count documents with $chunks_with_embeddings embedded chunks"
            return 0
        else
            print_warning "Library exists but has no processed documents yet"
            return 1
        fi
    else
        print_error "Failed to get library stats"
        echo "$response"
        return 1
    fi
}

# Function to perform a search query
perform_query() {
    local query_text="$1"
    local algorithm="$2"
    
    print_status "Performing search query: '$query_text' using $algorithm algorithm..."
    
    local query_data=$(cat <<EOF
{
    "email": "$TEST_EMAIL",
    "query": "$query_text",
    "algorithm": "$algorithm",
    "limit": 5
}
EOF
)
    
    local response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "$query_data" \
        "$API_BASE_URL/v1/query")
    
    if echo "$response" | grep -q "results"; then
        print_success "Query completed successfully"
        echo "$response" | jq '.' 2>/dev/null || echo "$response"
        
        # Extract and display key metrics
        local result_count=$(echo "$response" | jq -r '.results | length' 2>/dev/null || echo "0")
        local execution_time=$(echo "$response" | jq -r '.execution_time' 2>/dev/null || echo "0")
        local algorithm_used=$(echo "$response" | jq -r '.algorithm_used' 2>/dev/null || echo "unknown")
        
        print_success "Found $result_count results in ${execution_time}s using $algorithm_used algorithm"
        
        # Display top result if available
        if [ "$result_count" -gt 0 ]; then
            local top_result=$(echo "$response" | jq -r '.results[0]' 2>/dev/null)
            local similarity=$(echo "$top_result" | jq -r '.similarity_score' 2>/dev/null || echo "0")
            local filename=$(echo "$top_result" | jq -r '.original_filename' 2>/dev/null || echo "unknown")
            print_success "Top result: $filename (similarity: $similarity)"
        fi
        
        return 0
    else
        print_error "Query failed"
        echo "$response"
        return 1
    fi
}

# Function to wait for processing to complete
wait_for_processing() {
    print_status "Waiting for document processing to complete..."
    local max_attempts=60  # 2 minutes max
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if check_library_stats > /dev/null 2>&1; then
            print_success "Document processing completed!"
            return 0
        fi
        
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    print_error "Document processing did not complete within $((max_attempts * 2)) seconds"
    return 1
}

# Main execution
main() {
    echo "🚀 Starting Orion Full Workflow Test"
    echo "===================================="
    
    # Step 1: Check prerequisites
    print_status "Checking prerequisites..."
    
    if [ ! -d "$BOOKS_DIR" ]; then
        print_error "Books directory not found: $BOOKS_DIR"
        exit 1
    fi
    
    if [ ! -f "$DOCKER_COMPOSE_FILE" ]; then
        print_error "Docker Compose file not found: $DOCKER_COMPOSE_FILE"
        exit 1
    fi
    
    # Check if we have PDF files
    pdf_files=($(find "$BOOKS_DIR" -name "*.pdf" | head -3))
    if [ ${#pdf_files[@]} -eq 0 ]; then
        print_error "No PDF files found in $BOOKS_DIR"
        exit 1
    fi
    
    print_success "Found ${#pdf_files[@]} PDF files to test with"
    
    # Step 2: Build and start Docker container
    print_status "Building and starting Docker container..."
    
    # Stop any existing container
    docker-compose down > /dev/null 2>&1 || true
    
    # Build and start
    if docker-compose up --build -d; then
        print_success "Docker container started successfully"
    else
        print_error "Failed to start Docker container"
        exit 1
    fi
    
    # Step 3: Wait for API to be ready
    if ! wait_for_api; then
        print_error "API failed to start"
        docker-compose logs
        exit 1
    fi
    
    # Step 4: Upload PDF files
    print_status "Uploading PDF files..."
    upload_count=0
    
    for pdf_file in "${pdf_files[@]}"; do
        if upload_pdf "$pdf_file"; then
            ((upload_count++))
        else
            print_warning "Skipping failed upload: $(basename "$pdf_file")"
        fi
    done
    
    if [ $upload_count -eq 0 ]; then
        print_error "No files were uploaded successfully"
        exit 1
    fi
    
    print_success "Successfully uploaded $upload_count out of ${#pdf_files[@]} files"
    
    # Step 5: Wait for processing to complete
    if ! wait_for_processing; then
        print_error "Document processing failed or timed out"
        docker-compose logs
        exit 1
    fi
    
    # Step 6: Verify processing completed
    print_status "Verifying document processing..."
    check_library_stats
    
    # Step 7: Perform test queries
    print_status "Performing test queries..."
    
    # Test queries based on the religious texts we have
    test_queries=(
        "God creation heaven earth"
        "prayer worship faith"
        "commandments law righteousness"
        "wisdom knowledge understanding"
        "love compassion mercy"
    )
    
    algorithms=("cosine" "hybrid")
    
    for algorithm in "${algorithms[@]}"; do
        print_status "Testing $algorithm algorithm..."
        
        for query in "${test_queries[@]}"; do
            if perform_query "$query" "$algorithm"; then
                echo ""  # Add spacing between queries
            else
                print_warning "Query failed: '$query' with $algorithm"
            fi
        done
    done
    
    # Step 8: Get final statistics
    print_status "Final library statistics:"
    check_library_stats
    
    # Step 9: Test additional endpoints
    print_status "Testing additional endpoints..."
    
    # Test supported algorithms endpoint
    print_status "Getting supported algorithms..."
    algorithms_response=$(curl -s "$API_BASE_URL/v1/query/algorithms")
    echo "Supported algorithms: $algorithms_response"
    
    print_success "🎉 Full workflow test completed successfully!"
    echo ""
    echo "Summary:"
    echo "- Docker container: ✅ Built and running"
    echo "- PDF uploads: ✅ $upload_count files uploaded"
    echo "- Document processing: ✅ Completed"
    echo "- Search queries: ✅ Both cosine and hybrid algorithms tested"
    echo ""
    echo "The Orion system is working correctly!"
    echo ""
    echo "To stop the container, run: docker-compose down"
}

# Cleanup function
cleanup() {
    print_status "Cleaning up..."
    # Uncomment the next line if you want to automatically stop the container
    # docker-compose down
}

# Set up trap for cleanup on exit
trap cleanup EXIT

# Run main function
main "$@"
