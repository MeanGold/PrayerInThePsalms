# Quick Start - Infrastructure Deployment

## Prerequisites Checklist

- [ ] AWS Account with admin access
- [ ] AWS CLI installed and configured (`aws configure`)
- [ ] Python 3.11+ installed
- [ ] Node.js installed (for CDK CLI)
- [ ] AWS CDK CLI installed (`npm install -g aws-cdk`)

## 5-Minute Deployment

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Account

Edit `cdk.context.json`:
```json
{
  "account": "YOUR_AWS_ACCOUNT_ID",
  "region": "us-east-1"
}
```

Get your account ID:
```bash
aws sts get-caller-identity --query Account --output text
```

### 3. Bootstrap CDK (First Time Only)

```bash
cdk bootstrap
```

### 4. Deploy

```bash
cdk deploy
```

Review and confirm the changes. Deployment takes ~10-15 minutes.

### 5. Save Outputs

After deployment, save these values:
- **ApiEndpoint**: Your API URL
- **KnowledgeBaseId**: For Lambda configuration
- **VectorStoreEndpoint**: OpenSearch endpoint

## Test the Deployment

### 1. Ingest Sample Data

Create `sample_psalm.json`:
```json
{
  "psalms": [
    {
      "number": 23,
      "text": "The Lord is my shepherd...",
      "themes": ["comfort", "trust", "guidance"],
      "emotional_context": "anxiety, fear, uncertainty"
    }
  ]
}
```

Invoke ingestion:
```bash
aws lambda invoke \
  --function-name psalm-data-ingestion \
  --payload file://sample_psalm.json \
  response.json
```

### 2. Test Recommendation API

```bash
curl -X POST https://YOUR_API_ENDPOINT/prod/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "emotional_input": "I am feeling anxious and worried."
  }'
```

## Common Commands

```bash
# View CloudFormation template
cdk synth

# Check for differences
cdk diff

# Deploy with auto-approval
cdk deploy --require-approval never

# View stack outputs
aws cloudformation describe-stacks \
  --stack-name PsalmRagStack \
  --query 'Stacks[0].Outputs'

# Destroy all resources
cdk destroy
```

## Monitoring

View logs:
```bash
# Recommendation handler logs
aws logs tail /aws/lambda/psalm-recommendation-handler --follow

# Ingestion handler logs
aws logs tail /aws/lambda/psalm-data-ingestion --follow
```

View metrics:
```bash
# Lambda invocations
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=psalm-recommendation-handler \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

## Troubleshooting

**Issue**: CDK bootstrap fails
- **Solution**: Ensure AWS credentials are configured correctly

**Issue**: Lambda timeout errors
- **Solution**: Check CloudWatch logs for specific errors

**Issue**: Knowledge Base not found
- **Solution**: Verify deployment completed successfully and check outputs

**Issue**: OpenSearch connection errors
- **Solution**: Wait a few minutes for collection to become ACTIVE

## Next Steps

1. Review [DEPLOYMENT.md](../DEPLOYMENT.md) for detailed documentation
2. Review [infrastructure/README.md](README.md) for architecture details
3. Configure monitoring and alarms
4. Set up CI/CD pipeline
5. Add API authentication for production

## Cost Estimate

Approximate monthly costs (us-east-1, light usage):
- Lambda: $5-10
- API Gateway: $3-5
- OpenSearch Serverless: $50-100
- Bedrock: Pay per use (~$0.0001 per 1K tokens)
- CloudWatch: $5-10

**Total**: ~$65-130/month for development workload

Use [AWS Pricing Calculator](https://calculator.aws/) for accurate estimates.
