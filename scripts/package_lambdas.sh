#!/bin/bash
# Script to package Lambda functions with dependencies
# Requirements: 5.4, 6.1

set -e

echo "=========================================="
echo "Packaging Lambda Functions"
echo "=========================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if running from project root
if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}Error: Must run from project root directory${NC}"
    exit 1
fi

# Create build directory
BUILD_DIR="build"
echo -e "${YELLOW}Creating build directory...${NC}"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Function to package a Lambda function
package_lambda() {
    local function_name=$1
    local source_dir=$2
    
    echo -e "\n${YELLOW}Packaging ${function_name}...${NC}"
    
    # Create function-specific build directory
    local function_build_dir="$BUILD_DIR/$function_name"
    mkdir -p "$function_build_dir"
    
    # Copy function code
    echo "  - Copying function code from $source_dir"
    cp -r "$source_dir"/* "$function_build_dir/"
    
    # Copy shared modules
    echo "  - Copying shared modules"
    cp -r src/shared "$function_build_dir/"
    
    # Install dependencies
    echo "  - Installing dependencies"
    pip install -r requirements.txt -t "$function_build_dir" --quiet
    
    # Remove unnecessary files to reduce package size
    echo "  - Cleaning up unnecessary files"
    find "$function_build_dir" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$function_build_dir" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
    find "$function_build_dir" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
    find "$function_build_dir" -type f -name "*.pyc" -delete 2>/dev/null || true
    find "$function_build_dir" -type f -name "*.pyo" -delete 2>/dev/null || true
    
    # Create deployment package
    echo "  - Creating deployment package"
    cd "$function_build_dir"
    zip -r "../${function_name}.zip" . -q
    cd - > /dev/null
    
    local package_size=$(du -h "$BUILD_DIR/${function_name}.zip" | cut -f1)
    echo -e "${GREEN}  ✓ Package created: $BUILD_DIR/${function_name}.zip (${package_size})${NC}"
}

# Package recommendation handler
package_lambda "recommendation-handler" "src/recommendation_handler"

# Package data ingestion handler
package_lambda "data-ingestion" "src/data_ingestion"

echo -e "\n${GREEN}=========================================="
echo "Lambda packaging complete!"
echo "==========================================${NC}"
echo ""
echo "Deployment packages created in $BUILD_DIR/:"
ls -lh "$BUILD_DIR"/*.zip

echo -e "\n${YELLOW}Next steps:${NC}"
echo "  1. Run ./scripts/deploy_stack.sh to deploy infrastructure"
echo "  2. Run ./scripts/ingest_psalms.sh to load initial data"
