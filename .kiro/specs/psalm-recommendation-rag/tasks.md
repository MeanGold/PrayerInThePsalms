# Implementation Plan: Psalm Recommendation RAG

## Overview

This implementation plan breaks down the psalm recommendation system into discrete coding tasks. The system uses AWS Lambda functions, Amazon Bedrock for embeddings and LLM inference, API Gateway for the HTTP interface, and a vector store (OpenSearch Serverless or Aurora) for semantic search. All implementation will be in Python using boto3 for AWS service integration.

## Tasks

- [x] 1. Set up project structure and core configuration
  - Create directory structure for Lambda functions (recommendation handler and data ingestion)
  - Define Python requirements.txt with boto3, AWS SDK dependencies
  - Create configuration module for AWS service endpoints, model IDs, and environment variables
  - Set up logging configuration with structured logging
  - _Requirements: 7.1, 8.4, 10.2_

- [x] 2. Implement embedding generation module
  - [x] 2.1 Create embedding service wrapper for Amazon Bedrock
    - Write Python class to invoke Bedrock embedding model (e.g., amazon.titan-embed-text-v1)
    - Implement error handling for model unavailability with appropriate exceptions
    - Add retry logic with exponential backoff for transient failures
    - _Requirements: 2.1, 2.2, 2.3, 8.1, 10.3_
  
  - [ ]* 2.2 Write unit tests for embedding service
    - Test successful embedding generation
    - Test error handling when Bedrock is unavailable
    - Test retry logic with mocked failures
    - _Requirements: 2.1, 2.2, 8.1_

- [x] 3. Implement vector store interface
  - [x] 3.1 Create vector store abstraction layer
    - Write Python interface/abstract class for vector operations (search, insert, update)
    - Implement concrete class for Amazon Bedrock Knowledge Base integration
    - Add methods for similarity search with configurable result count (3-5 results)
    - Implement ranking by similarity score in descending order
    - _Requirements: 3.1, 3.2, 3.3, 6.1, 6.3_
  
  - [x] 3.2 Add error handling and fallback logic
    - Implement retry logic for vector store unavailability (3 retries with exponential backoff)
    - Add fallback to return default comforting psalms when no matches meet threshold
    - _Requirements: 3.4, 8.2_
  
  - [ ]* 3.3 Write unit tests for vector store operations
    - Test successful similarity search
    - Test result ranking by score
    - Test retry logic and fallback behavior
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 8.2_

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement LLM recommendation generation
  - [x] 5.1 Create LLM service wrapper for Amazon Bedrock
    - Write Python class to invoke Bedrock LLM (e.g., anthropic.claude-v2)
    - Implement prompt template that includes user emotional input and retrieved psalm context
    - Configure LLM parameters for empathetic and supportive tone
    - Parse LLM response to extract psalm numbers, verses, and guidance
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  
  - [x] 5.2 Add error handling for LLM failures
    - Implement fallback to return psalm references without personalized text when LLM fails
    - Add logging for LLM invocation failures
    - _Requirements: 8.3, 8.4, 10.4_
  
  - [ ]* 5.3 Write unit tests for LLM service
    - Test successful recommendation generation
    - Test prompt construction with user input and context
    - Test fallback behavior when LLM fails
    - _Requirements: 4.1, 4.2, 4.3, 8.3_

- [x] 6. Implement request handler Lambda function
  - [x] 6.1 Create main Lambda handler for recommendation requests
    - Write Lambda handler function that accepts API Gateway events
    - Implement input validation for emotional input (1-2 sentences, non-empty)
    - Orchestrate the RAG pipeline: embedding generation → vector search → LLM generation
    - Format response as JSON with psalm recommendations
    - Add request ID tracking and timing metrics
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 7.1, 7.2, 10.2_
  
  - [x] 6.2 Add error handling and response formatting
    - Implement error responses with appropriate HTTP status codes
    - Ensure response time stays within 5 seconds under normal load
    - Add structured logging for debugging
    - _Requirements: 7.3, 7.4, 8.4_
  
  - [x] 6.3 Implement privacy and security measures
    - Ensure emotional input is not persisted beyond request duration
    - Remove PII from logs
    - Validate that all API communications use HTTPS
    - _Requirements: 9.1, 9.2, 9.3, 9.4_
  
  - [ ]* 6.4 Write unit tests for request handler
    - Test input validation (empty, valid, too long)
    - Test successful end-to-end flow
    - Test error handling for each component failure
    - Test response formatting
    - _Requirements: 1.1, 1.2, 1.3, 7.2, 7.3_

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement data ingestion Lambda function
  - [x] 8.1 Create Lambda handler for psalm data ingestion
    - Write Lambda handler that accepts psalm data in batch format
    - Extract psalm metadata (themes, emotional context, historical usage, key verses)
    - Generate embeddings for each psalm using embedding service
    - Store embeddings and metadata in vector store
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  
  - [x] 8.2 Add batch processing and error handling
    - Implement batch processing for multiple psalms
    - Add error handling for individual psalm failures without stopping batch
    - Support update operations to regenerate embeddings when psalm data changes
    - _Requirements: 5.4, 6.4_
  
  - [ ]* 8.3 Write unit tests for data ingestion
    - Test single psalm ingestion
    - Test batch ingestion
    - Test error handling for individual failures
    - Test update operations
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 6.4_

- [x] 9. Implement monitoring and metrics
  - [x] 9.1 Add CloudWatch metrics emission
    - Emit custom metrics for request count, latency, and error rates
    - Track successful and failed embedding generations
    - Track successful and failed LLM invocations
    - Add metrics for vector store query performance
    - _Requirements: 10.1, 10.2, 10.3, 10.4_
  
  - [ ]* 9.2 Write unit tests for metrics emission
    - Test metrics are emitted correctly
    - Test metric values are accurate
    - _Requirements: 10.1, 10.3, 10.4_

- [x] 10. Create Infrastructure as Code (IaC)
  - [x] 10.1 Define AWS resources using CloudFormation or CDK
    - Define Lambda functions with appropriate IAM roles
    - Define API Gateway REST API with endpoint configuration
    - Define Amazon Bedrock Knowledge Base with vector store (OpenSearch Serverless or Aurora)
    - Configure IAM permissions for Bedrock model access
    - Set up CloudWatch log groups and metric alarms
    - _Requirements: 6.1, 6.2, 7.1, 7.4_
  
  - [x] 10.2 Add environment configuration
    - Define environment variables for model IDs, Knowledge Base ID, and endpoints
    - Configure Lambda timeout (10 seconds) and memory settings
    - Set up VPC configuration if using Aurora for vector store
    - _Requirements: 2.3, 6.2, 7.4_

- [x] 11. Create deployment scripts and documentation
  - [x] 11.1 Write deployment automation
    - Create script to package Lambda functions with dependencies
    - Create script to deploy infrastructure stack
    - Create script to run data ingestion for initial psalm dataset
    - _Requirements: 5.4, 6.1_
  
  - [x] 11.2 Write API documentation
    - Document API endpoint, request format, and response format
    - Provide example requests and responses
    - Document error codes and messages
    - _Requirements: 7.1, 7.2, 7.3_

- [ ] 12. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- All Lambda functions will be implemented in Python using boto3
- The system uses Amazon Bedrock Knowledge Bases for managed vector search
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation throughout implementation
- Privacy requirements (9.x) are integrated into the request handler implementation
- Monitoring requirements (10.x) are implemented as a separate module for reusability
