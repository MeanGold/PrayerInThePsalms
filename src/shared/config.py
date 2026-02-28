"""
Configuration module for AWS service endpoints, model IDs, and environment variables.

This module centralizes all configuration for the Psalm Recommendation RAG system,
including Amazon Bedrock model IDs, Knowledge Base configuration, and Lambda settings.

**Validates: Requirements 7.1, 8.4, 10.2**
"""

import os
from typing import Optional


class Config:
    """Central configuration for the Psalm Recommendation RAG system."""
    
    # Amazon Bedrock Configuration
    BEDROCK_REGION: str = os.getenv("BEDROCK_REGION", "us-east-1")
    
    # Embedding Model Configuration
    # Default: Amazon Titan Embeddings G1 - Text
    EMBEDDING_MODEL_ID: str = os.getenv(
        "EMBEDDING_MODEL_ID",
        "amazon.titan-embed-text-v1"
    )
    
    # LLM Configuration
    # Default: Claude 3 Sonnet for balanced performance and quality
    LLM_MODEL_ID: str = os.getenv(
        "LLM_MODEL_ID",
        "anthropic.claude-3-sonnet-20240229-v1:0"
    )
    
    # Knowledge Base Configuration
    KNOWLEDGE_BASE_ID: str = os.getenv("KNOWLEDGE_BASE_ID", "")
    
    # Vector Store Configuration
    VECTOR_STORE_TYPE: str = os.getenv("VECTOR_STORE_TYPE", "opensearch")
    
    # Retrieval Configuration
    MAX_RESULTS: int = int(os.getenv("MAX_RESULTS", "5"))
    MIN_RESULTS: int = int(os.getenv("MIN_RESULTS", "3"))
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))
    
    # Lambda Configuration
    LAMBDA_TIMEOUT_SECONDS: int = int(os.getenv("LAMBDA_TIMEOUT_SECONDS", "10"))
    REQUEST_TIMEOUT_SECONDS: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "5"))
    
    # Retry Configuration (Requirement 8.2)
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_BACKOFF_BASE: float = float(os.getenv("RETRY_BACKOFF_BASE", "2.0"))
    
    # Input Validation
    MAX_INPUT_SENTENCES: int = int(os.getenv("MAX_INPUT_SENTENCES", "2"))
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    SERVICE_NAME: str = os.getenv("SERVICE_NAME", "psalm-recommendation-rag")
    
    # Privacy Configuration (Requirement 9.2)
    ENABLE_PII_LOGGING: bool = os.getenv("ENABLE_PII_LOGGING", "false").lower() == "true"
    
    @classmethod
    def validate(cls) -> None:
        """
        Validate that required configuration values are set.
        
        Raises:
            ValueError: If required configuration is missing or invalid.
        """
        if not cls.KNOWLEDGE_BASE_ID:
            raise ValueError("KNOWLEDGE_BASE_ID environment variable is required")
        
        if cls.MAX_RESULTS < cls.MIN_RESULTS:
            raise ValueError(
                f"MAX_RESULTS ({cls.MAX_RESULTS}) must be >= MIN_RESULTS ({cls.MIN_RESULTS})"
            )
        
        if cls.SIMILARITY_THRESHOLD < 0 or cls.SIMILARITY_THRESHOLD > 1:
            raise ValueError(
                f"SIMILARITY_THRESHOLD must be between 0 and 1, got {cls.SIMILARITY_THRESHOLD}"
            )
    
    @classmethod
    def get_bedrock_client_config(cls) -> dict:
        """
        Get configuration for boto3 Bedrock client.
        
        Returns:
            Dictionary with client configuration parameters.
        """
        return {
            "region_name": cls.BEDROCK_REGION,
            "config": {
                "retries": {
                    "max_attempts": cls.MAX_RETRIES,
                    "mode": "adaptive"
                }
            }
        }
    
    @classmethod
    def get_embedding_model_config(cls) -> dict:
        """
        Get configuration for embedding model invocation.
        
        Returns:
            Dictionary with embedding model parameters.
        """
        return {
            "modelId": cls.EMBEDDING_MODEL_ID
        }
    
    @classmethod
    def get_llm_config(cls) -> dict:
        """
        Get configuration for LLM invocation.
        
        Returns:
            Dictionary with LLM parameters.
        """
        return {
            "modelId": cls.LLM_MODEL_ID,
            "temperature": 0.7,
            "maxTokens": 1000
        }


# Singleton instance
config = Config()
