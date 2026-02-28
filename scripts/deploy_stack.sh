#!/bin/bash
# Script to deploy infrastructure stack using AWS CDK
# Requirements: 5.4, 6.1

set -e

echo "=========================================="
echo "Deploying Psalm RAG Infrastructure"
echo "=========================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if running from project root
if [ ! -f "app.py" ]; then
    echo -e "${RED}Error: Must run from project root directory${NC}"
    exit 1
fi

# Check for required tools
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI not found. Please install AWS CLI.${NC}"
    exit 1
fi

if ! command -v cdk &> /dev/null; then
    echo -e "${RED}Error: AWS CDK CLI not found. Please install: npm install -g aws-cdk${NC}"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 not found. Please install Python 3.11+${NC}"
    exit 1
fi

echo -e "${GREEN}  ✓ All prerequisites found${NC}"

# Check AWS credentials
echo -e "\n${YELLOW}Checking AWS credentials...${NC}"
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}Error: AWS credentials not configured. Run 'aws configure'${NC}"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region || echo "us-east-1")
echo -e "${GREEN}  ✓ AWS Account: ${ACCOUNT_ID}${NC}"
echo -e "${GREEN}  ✓ AWS Region: ${REGION}${NC}"

# Install Python dependencies
echo -e "\n${YELLOW}Installing Python dependencies...${NC}"
pip install -r requirements.txt --quiet
pip install -r requirements-cdk.txt --quiet
echo -e "${GREEN}  ✓ Dependencies installed${NC}"

# Check if CDK is bootstrapped
echo -e "\n${YELLOW}Checking CDK bootstrap status...${NC}"
if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region "$REGION" &> /dev/null; then
    echo -e "${YELLOW}CDK not bootstrapped in this account/region.${NC}"
    read -p "Bootstrap CDK now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Bootstrapping CDK...${NC}"
        cdk bootstrap "aws://${ACCOUNT_ID}/${REGION}"
        echo -e "${GREEN}  ✓ CDK bootstrapped${NC}"
    else
        echo -e "${RED}Error: CDK must be bootstrapped before deployment${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}  ✓ CDK already bootstrapped${NC}"
fi

# Synthesize CloudFormation template
echo -e "\n${YELLOW}Synthesizing CloudFormation template...${NC}"
cdk synth
echo -e "${GREEN}  ✓ Template synthesized${NC}"

# Show what will be deployed
echo -e "\n${YELLOW}Checking for infrastructure changes...${NC}"
cdk diff

# Confirm deployment
echo -e "\n${BLUE}=========================================="
echo "Ready to deploy infrastructure"
echo "==========================================${NC}"
echo ""
echo "This will create the following resources:"
echo "  - Lambda functions (recommendation handler, data ingestion)"
echo "  - API Gateway REST API"
echo "  - Amazon Bedrock Knowledge Base"
echo "  - OpenSearch Serverless collection"
echo "  - IAM roles and policies"
echo "  - CloudWatch log groups and alarms"
echo ""
read -p "Proceed with deployment? (y/n) " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Deployment cancelled${NC}"
    exit 0
fi

# Deploy the stack
echo -e "\n${YELLOW}Deploying stack (this may take 10-15 minutes)...${NC}"
cdk deploy --require-approval never

# Check deployment status
if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}=========================================="
    echo "Deployment successful!"
    echo "==========================================${NC}"
    
    # Get stack outputs
    echo -e "\n${YELLOW}Stack Outputs:${NC}"
    aws cloudformation describe-stacks \
        --stack-name PsalmRagStack \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
        --output table
    
    # Save outputs to file
    echo -e "\n${YELLOW}Saving outputs to deployment-outputs.json...${NC}"
    aws cloudformation describe-stacks \
        --stack-name PsalmRagStack \
        --region "$REGION" \
        --query 'Stacks[0].Outputs' \
        --output json > deployment-outputs.json
    echo -e "${GREEN}  ✓ Outputs saved${NC}"
    
    echo -e "\n${YELLOW}Next steps:${NC}"
    echo "  1. Wait 2-3 minutes for OpenSearch collection to become ACTIVE"
    echo "  2. Run ./scripts/ingest_psalms.sh to load initial psalm data"
    echo "  3. Test the API endpoint shown in the outputs above"
    
else
    echo -e "\n${RED}=========================================="
    echo "Deployment failed!"
    echo "==========================================${NC}"
    echo ""
    echo "Check the error messages above for details."
    echo "Common issues:"
    echo "  - Insufficient IAM permissions"
    echo "  - Service quotas exceeded"
    echo "  - Bedrock not enabled in region"
    exit 1
fi
