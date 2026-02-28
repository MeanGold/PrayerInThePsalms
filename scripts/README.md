# Deployment Scripts

This directory contains automation scripts for deploying and managing the Psalm Recommendation RAG system.

## Scripts Overview

### 1. package_lambdas.sh
Packages Lambda functions with their dependencies into deployment-ready ZIP files.

**Requirements**: 5.4, 6.1

**What it does:**
- Creates a `build/` directory
- Copies Lambda function code and shared modules
- Installs Python dependencies
- Removes unnecessary files to reduce package size
- Creates ZIP files for each Lambda function

**Usage:**
```bash
./scripts/package_lambdas.sh
```

**Output:**
- `build/recommendation-handler.zip` - Recommendation handler deployment package
- `build/data-ingestion.zip` - Data ingestion handler deployment package

**Note:** This script is optional when using CDK, as CDK automatically packages Lambda functions from the source directories.

---

### 2. deploy_stack.sh
Deploys the complete infrastructure stack using AWS CDK.

**Requirements**: 5.4, 6.1

**What it does:**
- Checks prerequisites (AWS CLI, CDK CLI, Python)
- Verifies AWS credentials
- Installs Python dependencies
- Bootstraps CDK (if needed)
- Synthesizes CloudFormation template
- Shows infrastructure changes (diff)
- Deploys the stack
- Saves stack outputs to `deployment-outputs.json`

**Usage:**
```bash
./scripts/deploy_stack.sh
```

**Prerequisites:**
- AWS CLI installed and configured
- AWS CDK CLI installed (`npm install -g aws-cdk`)
- Python 3.11+
- Valid AWS credentials

**Resources Created:**
- Lambda functions (recommendation handler, data ingestion)
- API Gateway REST API
- Amazon Bedrock Knowledge Base
- OpenSearch Serverless collection
- IAM roles and policies
- CloudWatch log groups and alarms

**Deployment Time:** 10-15 minutes

---

### 3. ingest_psalms.sh
Runs data ingestion to load psalm data into the vector store.

**Requirements**: 5.4, 6.1

**What it does:**
- Retrieves Lambda function name from stack outputs
- Creates sample psalm data if not provided
- Invokes the data ingestion Lambda function
- Displays ingestion results

**Usage:**
```bash
# Use default sample data
./scripts/ingest_psalms.sh

# Use custom psalm data file
./scripts/ingest_psalms.sh path/to/psalms.json
```

**Prerequisites:**
- Infrastructure must be deployed first
- AWS CLI installed and configured

**Psalm Data Format:**
```json
{
  "psalms": [
    {
      "number": 23,
      "text": "The Lord is my shepherd...",
      "themes": ["comfort", "trust", "guidance"],
      "emotional_context": "anxiety, fear, uncertainty",
      "historical_usage": "Used in times of distress",
      "key_verses": ["verse 1: The Lord is my shepherd"]
    }
  ]
}
```

**Sample Data:**
If no data file is provided, the script creates `data/psalms.json` with 5 sample psalms:
- Psalm 23 (The Lord is my shepherd)
- Psalm 46 (God is our refuge and strength)
- Psalm 139 (You have searched me, Lord)
- Psalm 91 (Whoever dwells in the shelter)
- Psalm 42 (As the deer pants for water)

---

## Complete Deployment Workflow

### First-Time Deployment

1. **Deploy Infrastructure**
   ```bash
   ./scripts/deploy_stack.sh
   ```
   
   This will:
   - Check prerequisites
   - Bootstrap CDK if needed
   - Deploy all AWS resources
   - Save outputs to `deployment-outputs.json`

2. **Wait for OpenSearch Collection**
   
   Wait 2-3 minutes for the OpenSearch Serverless collection to become ACTIVE.

3. **Ingest Psalm Data**
   ```bash
   ./scripts/ingest_psalms.sh
   ```
   
   This will:
   - Create sample psalm data (or use your custom data)
   - Invoke the data ingestion Lambda
   - Generate embeddings for all psalms
   - Store embeddings in the vector store

4. **Test the API**
   
   Get the API endpoint from `deployment-outputs.json`:
   ```bash
   API_ENDPOINT=$(jq -r '.[] | select(.OutputKey=="ApiEndpoint") | .OutputValue' deployment-outputs.json)
   
   curl -X POST "${API_ENDPOINT}recommend" \
     -H "Content-Type: application/json" \
     -d '{"emotional_input": "I am feeling anxious and worried about the future."}'
   ```

### Updating the Stack

To update infrastructure after code changes:

```bash
./scripts/deploy_stack.sh
```

CDK will show you the changes and ask for confirmation before deploying.

### Adding More Psalms

To add more psalms to the vector store:

1. Create a JSON file with new psalm data
2. Run the ingestion script:
   ```bash
   ./scripts/ingest_psalms.sh path/to/new_psalms.json
   ```

---

## Windows Users

These scripts are written for Bash (Linux/macOS). Windows users have several options:

### Option 1: Use Git Bash
Git Bash provides a Bash environment on Windows:
```bash
bash scripts/deploy_stack.sh
```

### Option 2: Use WSL (Windows Subsystem for Linux)
Install WSL and run the scripts in a Linux environment:
```bash
wsl
./scripts/deploy_stack.sh
```

### Option 3: Use CDK Directly
Run CDK commands directly without the scripts:

```powershell
# Install dependencies
pip install -r requirements.txt
pip install -r requirements-cdk.txt

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy
cdk deploy

# Get outputs
aws cloudformation describe-stacks --stack-name PsalmRagStack --query 'Stacks[0].Outputs'
```

For data ingestion:
```powershell
# Invoke Lambda directly
aws lambda invoke `
  --function-name psalm-data-ingestion `
  --payload file://data/psalms.json `
  --cli-binary-format raw-in-base64-out `
  response.json

# View response
Get-Content response.json | ConvertFrom-Json
```

---

## Troubleshooting

### Script Permission Denied

On Linux/macOS, make scripts executable:
```bash
chmod +x scripts/*.sh
```

### AWS Credentials Not Found

Configure AWS credentials:
```bash
aws configure
```

### CDK Not Bootstrapped

Bootstrap CDK in your account/region:
```bash
cdk bootstrap aws://ACCOUNT_ID/REGION
```

### Lambda Invocation Failed

Check Lambda logs:
```bash
aws logs tail /aws/lambda/psalm-data-ingestion --follow
```

### OpenSearch Connection Errors

Wait a few minutes for the OpenSearch collection to become ACTIVE:
```bash
aws opensearchserverless list-collections
```

---

## Environment Variables

The scripts use the following environment variables (optional):

- `AWS_REGION` - AWS region (default: from AWS CLI config)
- `AWS_PROFILE` - AWS CLI profile to use (default: default)

Example:
```bash
AWS_REGION=us-west-2 AWS_PROFILE=myprofile ./scripts/deploy_stack.sh
```

---

## Cost Considerations

Running these scripts will create AWS resources that incur costs:

- **Lambda**: Pay per invocation (~$0.20 per 1M requests)
- **API Gateway**: Pay per request (~$3.50 per 1M requests)
- **OpenSearch Serverless**: ~$50-100/month minimum
- **Bedrock**: Pay per token (~$0.0001 per 1K tokens)
- **CloudWatch**: ~$5-10/month for logs and metrics

**Estimated monthly cost for light usage**: $65-130

Use the [AWS Pricing Calculator](https://calculator.aws/) for accurate estimates.

---

## Cleanup

To remove all resources and stop incurring costs:

```bash
cdk destroy
```

**Warning**: This will delete all data including psalm embeddings. Backup any important data first.

---

## Additional Resources

- [DEPLOYMENT.md](../DEPLOYMENT.md) - Detailed deployment guide
- [infrastructure/README.md](../infrastructure/README.md) - Infrastructure documentation
- [infrastructure/QUICK_START.md](../infrastructure/QUICK_START.md) - Quick start guide
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [Amazon Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
