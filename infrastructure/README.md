# Infrastructure - Psalm Recommendation RAG System

This directory contains AWS CDK infrastructure code for the Psalm Recommendation RAG system.

## Architecture Overview

The infrastructure consists of:

### Core Components

1. **Lambda Functions**
   - **Recommendation Handler** (`psalm-recommendation-handler`)
     - Runtime: Python 3.11
     - Timeout: 10 seconds (Requirement 2.3)
     - Memory: 512 MB
     - Handles psalm recommendation requests via RAG pipeline
   
   - **Data Ingestion** (`psalm-data-ingestion`)
     - Runtime: Python 3.11
     - Timeout: 60 seconds
     - Memory: 1024 MB
     - Ingests psalm data and generates embeddings

2. **Amazon Bedrock Knowledge Base**
   - Vector-based knowledge base for semantic search
   - Embedding Model: `amazon.titan-embed-text-v1`
   - Stores psalm embeddings and metadata
   - Integrated with OpenSearch Serverless

3. **OpenSearch Serverless Collection**
   - Collection Name: `psalm-vector-store`
   - Type: VECTORSEARCH
   - Index: `psalm-embeddings`
   - Provides durable vector storage (Requirement 6.1)

4. **API Gateway REST API**
   - Endpoint: `/recommend` (POST)
   - CORS enabled
   - Throttling: 100 requests/sec (configurable)
   - CloudWatch logging enabled

5. **IAM Roles and Policies**
   - Lambda execution roles with least privilege
   - Bedrock model invocation permissions
   - Knowledge Base retrieval permissions
   - CloudWatch Logs and Metrics permissions
   - OpenSearch Serverless data access

6. **CloudWatch Monitoring**
   - Log Groups:
     - `/aws/lambda/psalm-recommendation-handler`
     - `/aws/lambda/psalm-data-ingestion`
   - Alarms:
     - Lambda error rate
     - Lambda duration
     - API Gateway 5XX errors
   - Custom Metrics: Namespace `PsalmRecommendationRAG`

## Files

- `psalm_rag_stack.py`: Main CDK stack definition
- `__init__.py`: Package initialization

## Configuration

### Environment Variables

All Lambda environment variables are defined in the stack and can be customized:

**Bedrock Configuration:**
- `BEDROCK_REGION`: AWS region for Bedrock services
- `EMBEDDING_MODEL_ID`: Bedrock embedding model ID
- `LLM_MODEL_ID`: Bedrock LLM model ID

**Knowledge Base Configuration:**
- `KNOWLEDGE_BASE_ID`: Auto-generated Bedrock Knowledge Base ID
- `VECTOR_STORE_TYPE`: Vector store type (opensearch)
- `OPENSEARCH_ENDPOINT`: OpenSearch collection endpoint (ingestion only)
- `OPENSEARCH_INDEX`: OpenSearch index name (ingestion only)

**Retrieval Configuration:**
- `MAX_RESULTS`: Maximum retrieval results (default: 5)
- `MIN_RESULTS`: Minimum retrieval results (default: 3)
- `SIMILARITY_THRESHOLD`: Similarity threshold (default: 0.7)

**Lambda Configuration:**
- `LAMBDA_TIMEOUT_SECONDS`: Lambda timeout (default: 10)
- `REQUEST_TIMEOUT_SECONDS`: Request timeout (default: 5)

**Retry Configuration (Requirement 8.2):**
- `MAX_RETRIES`: Maximum retry attempts (default: 3)
- `RETRY_BACKOFF_BASE`: Exponential backoff base (default: 2.0)

**Input Validation:**
- `MAX_INPUT_SENTENCES`: Maximum input sentences (default: 2)

**Logging Configuration:**
- `LOG_LEVEL`: Logging level (default: INFO)
- `SERVICE_NAME`: Service name for logs
- `ENABLE_PII_LOGGING`: Enable PII logging (default: false, Requirement 9.2)

### Context Configuration

The `cdk.context.json` file contains environment-specific settings:

```json
{
  "account": "YOUR_AWS_ACCOUNT_ID",
  "region": "us-east-1",
  "environment": {
    "dev": { ... },
    "prod": { ... }
  }
}
```

## IAM Permissions

### Recommendation Handler Lambda Role

- **AWS Managed Policies:**
  - `AWSLambdaBasicExecutionRole` (CloudWatch Logs)

- **Custom Policies:**
  - Bedrock model invocation (InvokeModel)
  - Bedrock Knowledge Base retrieval (Retrieve, RetrieveAndGenerate)
  - CloudWatch metrics (PutMetricData)
  - OpenSearch Serverless data access (APIAccessAll)

### Data Ingestion Lambda Role

- **AWS Managed Policies:**
  - `AWSLambdaBasicExecutionRole` (CloudWatch Logs)

- **Custom Policies:**
  - Bedrock model invocation (InvokeModel)
  - CloudWatch metrics (PutMetricData)
  - OpenSearch Serverless data access (APIAccessAll)

### Bedrock Knowledge Base Role

- **Custom Policies:**
  - Bedrock model invocation (InvokeModel)
  - OpenSearch Serverless data access (APIAccessAll)

## Security

### Encryption

- **At Rest:**
  - OpenSearch Serverless: AWS-owned keys
  - Lambda environment variables: AWS-managed keys
  - CloudWatch Logs: AWS-managed keys

- **In Transit:**
  - API Gateway: HTTPS only
  - Bedrock API: TLS 1.2+
  - OpenSearch Serverless: TLS 1.2+

### Network Security

- **OpenSearch Serverless:**
  - Network policy allows public access (can be restricted)
  - Data access policy restricts to specific IAM roles

- **Lambda Functions:**
  - No VPC configuration by default (can be added)
  - IAM-based access control

### Data Privacy (Requirement 9)

- User input not persisted beyond request duration
- PII logging disabled by default
- Encrypted connections for all API communications

## Monitoring and Alarms

### CloudWatch Alarms

1. **Recommendation Handler Error Alarm**
   - Metric: Lambda Errors
   - Threshold: 5 errors in 5 minutes
   - Action: Alert

2. **Recommendation Handler Duration Alarm**
   - Metric: Lambda Duration
   - Threshold: 8000ms (80% of timeout)
   - Evaluation: 2 periods
   - Action: Alert

3. **API Gateway 5XX Error Alarm**
   - Metric: 5XX Errors
   - Threshold: 10 errors in 5 minutes
   - Action: Alert

### Custom Metrics

The application emits custom metrics to CloudWatch:
- Request count
- Latency
- Error rates
- Embedding generation success/failure
- LLM invocation success/failure

Namespace: `PsalmRecommendationRAG`

## Outputs

After deployment, the stack exports:

- `PsalmRagApiEndpoint`: API Gateway URL
- `PsalmRagKnowledgeBaseId`: Bedrock Knowledge Base ID
- `PsalmRagVectorStoreEndpoint`: OpenSearch Serverless endpoint
- `PsalmRagRecommendationLambdaArn`: Recommendation Lambda ARN
- `PsalmRagIngestionLambdaArn`: Ingestion Lambda ARN

## Deployment

See [DEPLOYMENT.md](../DEPLOYMENT.md) for detailed deployment instructions.

## Requirements Validation

This infrastructure validates the following requirements:

- **Requirement 2.3**: Lambda timeout configuration (10 seconds)
- **Requirement 6.1**: Vector Store persistence (OpenSearch Serverless)
- **Requirement 6.2**: Vector Store query performance (<2 seconds)
- **Requirement 7.1**: HTTP API endpoint (API Gateway)
- **Requirement 7.4**: Response time (<5 seconds)
- **Requirement 8.2**: Retry with exponential backoff
- **Requirement 9.2**: No PII in logs
- **Requirement 10.2**: System monitoring (CloudWatch)

## Customization

### Using Aurora for Vector Store

To use Aurora instead of OpenSearch Serverless:

1. Modify `storage_configuration` in the Knowledge Base definition
2. Add Aurora cluster and VPC configuration
3. Update Lambda VPC configuration
4. Update IAM permissions for RDS access

### Adding VPC Configuration

To deploy Lambda functions in a VPC:

1. Create VPC, subnets, and security groups in the stack
2. Add `vpc` parameter to Lambda function definitions
3. Update security group rules for Bedrock and OpenSearch access
4. Add VPC endpoints for AWS services

### Custom Domain

To add a custom domain to API Gateway:

1. Create ACM certificate
2. Add `domain_name` configuration to API Gateway
3. Create Route53 record

## Cost Optimization

- **Lambda**: Use appropriate memory settings (512 MB for recommendation, 1024 MB for ingestion)
- **OpenSearch Serverless**: Scales automatically based on usage
- **API Gateway**: Consider caching for frequently requested recommendations
- **CloudWatch Logs**: Set appropriate retention periods (7 days for dev, 30 days for prod)

## Troubleshooting

See [DEPLOYMENT.md](../DEPLOYMENT.md) for troubleshooting guidance.
