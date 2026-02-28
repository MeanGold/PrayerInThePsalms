# Deployment Guide - Psalm Recommendation RAG System

This guide explains how to deploy the Psalm Recommendation RAG system using AWS CDK.

## Prerequisites

1. **AWS Account**: You need an AWS account with appropriate permissions
2. **AWS CLI**: Install and configure AWS CLI with your credentials
   ```bash
   aws configure
   ```
3. **Python 3.11+**: Required for Lambda runtime and CDK
4. **Node.js**: Required for AWS CDK CLI
5. **AWS CDK CLI**: Install globally
   ```bash
   npm install -g aws-cdk
   ```

## Setup

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure AWS Account and Region

Edit `cdk.context.json` and update:
- `account`: Your AWS account ID
- `region`: Your preferred AWS region (default: us-east-1)

You can find your account ID with:
```bash
aws sts get-caller-identity --query Account --output text
```

### 3. Bootstrap CDK (First Time Only)

If this is your first time using CDK in this account/region:

```bash
cdk bootstrap aws://ACCOUNT-ID/REGION
```

Example:
```bash
cdk bootstrap aws://123456789012/us-east-1
```

## Deployment

### 1. Synthesize CloudFormation Template

Generate the CloudFormation template to review:

```bash
cdk synth
```

This creates a CloudFormation template in `cdk.out/PsalmRagStack.template.json`

### 2. Deploy the Stack

Deploy all resources to AWS:

```bash
cdk deploy
```

Review the changes and confirm when prompted. The deployment will:
- Create OpenSearch Serverless collection for vector storage
- Create Bedrock Knowledge Base
- Deploy Lambda functions for recommendation and data ingestion
- Create API Gateway REST API
- Set up IAM roles and permissions
- Configure CloudWatch log groups and alarms

### 3. Note the Outputs

After deployment, CDK will output important values:
- **ApiEndpoint**: The API Gateway URL for making requests
- **KnowledgeBaseId**: The Bedrock Knowledge Base ID
- **VectorStoreEndpoint**: OpenSearch Serverless endpoint
- **RecommendationLambdaArn**: Lambda function ARN
- **IngestionLambdaArn**: Data ingestion Lambda ARN

Save these values for configuration and testing.

## Environment Variables

The Lambda functions are configured with the following environment variables:

### Recommendation Handler Lambda

| Variable | Default | Description |
|----------|---------|-------------|
| `BEDROCK_REGION` | Stack region | AWS region for Bedrock services |
| `EMBEDDING_MODEL_ID` | `amazon.titan-embed-text-v1` | Bedrock embedding model |
| `LLM_MODEL_ID` | `anthropic.claude-3-sonnet-20240229-v1:0` | Bedrock LLM model |
| `KNOWLEDGE_BASE_ID` | Auto-generated | Bedrock Knowledge Base ID |
| `VECTOR_STORE_TYPE` | `opensearch` | Vector store type |
| `MAX_RESULTS` | `5` | Maximum retrieval results |
| `MIN_RESULTS` | `3` | Minimum retrieval results |
| `SIMILARITY_THRESHOLD` | `0.7` | Similarity threshold for matches |
| `LAMBDA_TIMEOUT_SECONDS` | `10` | Lambda timeout (Requirement 2.3) |
| `REQUEST_TIMEOUT_SECONDS` | `5` | Request timeout (Requirement 7.4) |
| `MAX_RETRIES` | `3` | Max retry attempts (Requirement 8.2) |
| `RETRY_BACKOFF_BASE` | `2.0` | Exponential backoff base |
| `MAX_INPUT_SENTENCES` | `2` | Max input sentences (Requirement 1.1) |
| `LOG_LEVEL` | `INFO` | Logging level |
| `SERVICE_NAME` | `psalm-recommendation-rag` | Service name for logs |
| `ENABLE_PII_LOGGING` | `false` | PII logging (Requirement 9.2) |

### Data Ingestion Lambda

| Variable | Default | Description |
|----------|---------|-------------|
| `BEDROCK_REGION` | Stack region | AWS region for Bedrock services |
| `EMBEDDING_MODEL_ID` | `amazon.titan-embed-text-v1` | Bedrock embedding model |
| `KNOWLEDGE_BASE_ID` | Auto-generated | Bedrock Knowledge Base ID |
| `VECTOR_STORE_TYPE` | `opensearch` | Vector store type |
| `OPENSEARCH_ENDPOINT` | Auto-generated | OpenSearch collection endpoint |
| `OPENSEARCH_INDEX` | `psalm-embeddings` | OpenSearch index name |
| `LOG_LEVEL` | `INFO` | Logging level |
| `SERVICE_NAME` | `psalm-recommendation-rag` | Service name for logs |

## Post-Deployment Steps

### 1. Ingest Psalm Data

Before the system can make recommendations, you need to ingest psalm data:

```bash
aws lambda invoke \
  --function-name psalm-data-ingestion \
  --payload file://sample_psalms.json \
  response.json
```

Create `sample_psalms.json` with psalm data in the format expected by the ingestion handler.

### 2. Test the API

Test the recommendation endpoint:

```bash
curl -X POST https://YOUR_API_ENDPOINT/prod/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "emotional_input": "I am feeling anxious and worried about the future."
  }'
```

Replace `YOUR_API_ENDPOINT` with the `ApiEndpoint` output from deployment.

### 3. Monitor the System

- **CloudWatch Logs**: View logs in CloudWatch under log groups:
  - `/aws/lambda/psalm-recommendation-handler`
  - `/aws/lambda/psalm-data-ingestion`
  
- **CloudWatch Alarms**: Monitor alarms for:
  - High error rates
  - High latency
  - API Gateway 5XX errors

- **CloudWatch Metrics**: Custom metrics under namespace `PsalmRecommendationRAG`

## Configuration Updates

To update environment variables after deployment:

1. Modify the environment variables in `infrastructure/psalm_rag_stack.py`
2. Redeploy:
   ```bash
   cdk deploy
   ```

## VPC Configuration (Optional)

If you need to deploy Lambda functions in a VPC (e.g., for Aurora vector store):

1. Uncomment VPC configuration in `psalm_rag_stack.py`
2. Update security group and subnet configurations
3. Redeploy the stack

## Cleanup

To remove all resources:

```bash
cdk destroy
```

**Warning**: This will delete all resources including the vector store data. Make sure to backup any important data first.

## Troubleshooting

### Lambda Timeout Errors

If you see timeout errors:
1. Check CloudWatch logs for the specific error
2. Increase `LAMBDA_TIMEOUT_SECONDS` if needed
3. Verify Bedrock service availability in your region

### Knowledge Base Not Found

If the Knowledge Base ID is not found:
1. Verify the Knowledge Base was created successfully in AWS Console
2. Check that the `KNOWLEDGE_BASE_ID` environment variable is set correctly
3. Ensure IAM permissions allow access to the Knowledge Base

### OpenSearch Connection Errors

If you see OpenSearch connection errors:
1. Verify the data access policy includes the Lambda execution roles
2. Check that the collection is in ACTIVE state
3. Ensure the index `psalm-embeddings` exists

## Cost Considerations

The deployed infrastructure incurs costs for:
- **Lambda**: Pay per invocation and compute time
- **API Gateway**: Pay per request
- **OpenSearch Serverless**: Pay per OCU (OpenSearch Compute Unit)
- **Bedrock**: Pay per model invocation and token usage
- **CloudWatch**: Pay for log storage and metrics

Estimate costs using the [AWS Pricing Calculator](https://calculator.aws/).

## Security Best Practices

1. **API Authentication**: Add API Gateway authorizers for production
2. **Encryption**: All data is encrypted at rest and in transit
3. **IAM Least Privilege**: Roles have minimal required permissions
4. **VPC**: Consider deploying in VPC for additional network isolation
5. **Secrets Management**: Use AWS Secrets Manager for sensitive configuration

## Support

For issues or questions:
1. Check CloudWatch logs for error details
2. Review AWS service health dashboard
3. Consult AWS Bedrock documentation
4. Review the requirements and design documents in `.kiro/specs/psalm-recommendation-rag/`
