# Psalm Recommendation RAG System

An AI-powered psalm recommendation system that helps users discover relevant psalms based on their emotional state using Amazon Bedrock and RAG (Retrieval-Augmented Generation).

## Project Structure

```
.
├── src/
│   ├── recommendation_handler/    # Lambda function for handling recommendation requests
│   │   ├── __init__.py
│   │   └── handler.py
│   ├── data_ingestion/           # Lambda function for ingesting psalm data
│   │   ├── __init__.py
│   │   └── handler.py
│   └── shared/                   # Shared utilities and configuration
│       ├── __init__.py
│       ├── config.py             # Central configuration module
│       ├── logging_config.py     # Structured logging setup
│       ├── embedding_service.py  # Bedrock embedding service
│       ├── llm_service.py        # Bedrock LLM service
│       ├── vector_store.py       # Vector store operations
│       └── metrics.py            # CloudWatch metrics
├── infrastructure/               # AWS CDK infrastructure code
│   ├── __init__.py
│   ├── psalm_rag_stack.py       # Main CDK stack definition
│   ├── README.md                # Infrastructure documentation
│   └── QUICK_START.md           # Quick deployment guide
├── app.py                       # CDK app entry point
├── cdk.json                     # CDK configuration
├── requirements.txt             # Python dependencies
├── DEPLOYMENT.md                # Detailed deployment guide
└── README.md                    # This file
```

## Configuration

The system is configured through environment variables. See `src/shared/config.py` for all available configuration options.

### Required Environment Variables

- `KNOWLEDGE_BASE_ID`: Amazon Bedrock Knowledge Base ID

### Optional Environment Variables

- `BEDROCK_REGION`: AWS region for Bedrock (default: us-east-1)
- `EMBEDDING_MODEL_ID`: Bedrock embedding model (default: amazon.titan-embed-text-v1)
- `LLM_MODEL_ID`: Bedrock LLM model (default: anthropic.claude-3-sonnet-20240229-v1:0)
- `MAX_RESULTS`: Maximum psalms to retrieve (default: 5)
- `MIN_RESULTS`: Minimum psalms to retrieve (default: 3)
- `LAMBDA_TIMEOUT_SECONDS`: Lambda timeout (default: 10)
- `LOG_LEVEL`: Logging level (default: INFO)

## Dependencies

- `boto3`: AWS SDK for Python
- `aws-lambda-powertools`: Structured logging and utilities for Lambda
- `aws-cdk-lib`: AWS CDK library for infrastructure as code
- `constructs`: CDK constructs library

Install dependencies:
```bash
pip install -r requirements.txt
```

## Deployment

This project uses AWS CDK for infrastructure deployment. See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions.

### Quick Start

1. Install dependencies: `pip install -r requirements.txt`
2. Configure AWS account in `cdk.context.json`
3. Bootstrap CDK: `cdk bootstrap`
4. Deploy: `cdk deploy`

See [infrastructure/QUICK_START.md](infrastructure/QUICK_START.md) for a 5-minute deployment guide.

## Lambda Functions

### Recommendation Handler
Processes user emotional input and returns personalized psalm recommendations.

**Handler**: `src.recommendation_handler.handler.lambda_handler`

### Data Ingestion
Ingests psalm data and generates embeddings for the vector store.

**Handler**: `src.data_ingestion.handler.lambda_handler`

## Logging

The system uses AWS Lambda Powertools for structured logging with:
- Automatic request ID correlation
- PII sanitization (configurable)
- Performance metrics tracking
- Error context for debugging

## Development

This project follows the requirements and design specified in `.kiro/specs/psalm-recommendation-rag/`.

### Architecture

The system uses:
- **Amazon Bedrock** for embeddings and LLM inference
- **Amazon Bedrock Knowledge Base** for semantic search
- **OpenSearch Serverless** for vector storage
- **AWS Lambda** for serverless compute
- **API Gateway** for REST API
- **CloudWatch** for logging and monitoring

### Testing

Run tests:
```bash
pytest
```

Run tests with coverage:
```bash
pytest --cov=src --cov-report=html
```

### Infrastructure

The infrastructure is defined using AWS CDK in Python. Key resources:
- Lambda functions with IAM roles
- API Gateway REST API
- Bedrock Knowledge Base
- OpenSearch Serverless collection
- CloudWatch log groups and alarms

See [infrastructure/README.md](infrastructure/README.md) for architecture details.
