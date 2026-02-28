"""
Embedding service wrapper for Amazon Bedrock.

This module provides a wrapper for generating vector embeddings using Amazon Bedrock's
embedding models. It includes error handling, retry logic with exponential backoff,
and metrics tracking for monitoring.

**Validates: Requirements 2.1, 2.2, 2.3, 8.1, 10.3**
"""

import json
import time
from typing import List, Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError, BotoCoreError

from .config import config
from .logging_config import get_logger, log_metric, log_error
from .metrics import emit_embedding_metric


logger = get_logger("embedding_service")


class EmbeddingServiceError(Exception):
    """Base exception for embedding service errors."""
    pass


class EmbeddingModelUnavailableError(EmbeddingServiceError):
    """
    Exception raised when the embedding model is unavailable.
    
    **Validates: Requirement 2.2**
    """
    pass


class EmbeddingService:
    """
    Service for generating vector embeddings using Amazon Bedrock.
    
    This class provides methods to generate embeddings for text input with
    automatic retry logic, error handling, and metrics tracking.
    
    **Validates: Requirements 2.1, 2.2, 2.3, 8.1, 10.3**
    """
    
    def __init__(
        self,
        bedrock_client: Optional[Any] = None,
        model_id: Optional[str] = None,
        max_retries: Optional[int] = None,
        backoff_base: Optional[float] = None
    ):
        """
        Initialize the embedding service.
        
        Args:
            bedrock_client: Optional boto3 Bedrock Runtime client. If not provided,
                          a new client will be created.
            model_id: Optional embedding model ID. Defaults to config value.
            max_retries: Optional maximum retry attempts. Defaults to config value.
            backoff_base: Optional exponential backoff base. Defaults to config value.
        """
        self.bedrock_client = bedrock_client or self._create_bedrock_client()
        self.model_id = model_id or config.EMBEDDING_MODEL_ID
        self.max_retries = max_retries if max_retries is not None else config.MAX_RETRIES
        self.backoff_base = backoff_base if backoff_base is not None else config.RETRY_BACKOFF_BASE
        
        logger.info(
            "EmbeddingService initialized",
            extra={
                "model_id": self.model_id,
                "max_retries": self.max_retries
            }
        )
    
    def _create_bedrock_client(self) -> Any:
        """
        Create a boto3 Bedrock Runtime client with configured settings.
        
        Returns:
            Configured boto3 Bedrock Runtime client.
        """
        return boto3.client(
            "bedrock-runtime",
            region_name=config.BEDROCK_REGION
        )

    def generate_embedding(
        self,
        text: str,
        request_id: Optional[str] = None
    ) -> List[float]:
        """
        Generate a vector embedding for the given text.
        
        This method invokes the Bedrock embedding model with automatic retry logic
        for transient failures. It tracks metrics for successful and failed generations.
        
        **Validates: Requirements 2.1, 2.2, 8.1, 10.3**
        
        Args:
            text: The input text to generate an embedding for.
            request_id: Optional request ID for tracking and logging.
            
        Returns:
            A list of floats representing the embedding vector.
            
        Raises:
            EmbeddingModelUnavailableError: When the model is unavailable after retries.
            EmbeddingServiceError: For other embedding generation errors.
        """
        if not text or not text.strip():
            raise ValueError("Input text cannot be empty")
        
        start_time = time.time()
        attempt = 0
        last_error = None
        
        while attempt < self.max_retries:
            try:
                # Prepare the request body based on the model
                request_body = self._prepare_request_body(text)
                
                # Invoke the Bedrock model
                response = self.bedrock_client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(request_body),
                    contentType="application/json",
                    accept="application/json"
                )
                
                # Parse the response
                response_body = json.loads(response["body"].read())
                embedding = self._extract_embedding(response_body)
                
                # Track success metrics (Requirement 10.3)
                duration_ms = (time.time() - start_time) * 1000
                log_metric(
                    metric_name="embedding_generation_success",
                    value=1,
                    unit="count",
                    metadata={
                        "request_id": request_id,
                        "duration_ms": duration_ms,
                        "attempt": attempt + 1
                    }
                )
                
                # Emit CloudWatch metrics (Requirement 10.3)
                emit_embedding_metric(
                    success=True,
                    duration_ms=duration_ms,
                    request_id=request_id
                )
                
                logger.info(
                    "Embedding generated successfully",
                    extra={
                        "request_id": request_id,
                        "duration_ms": duration_ms,
                        "embedding_dimension": len(embedding),
                        "attempt": attempt + 1
                    }
                )
                
                return embedding
                
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                last_error = e
                
                # Check if this is a retryable error
                if self._is_retryable_error(error_code):
                    attempt += 1
                    if attempt < self.max_retries:
                        # Calculate exponential backoff delay
                        delay = self.backoff_base ** attempt
                        logger.warning(
                            f"Retryable error occurred, retrying in {delay}s",
                            extra={
                                "request_id": request_id,
                                "error_code": error_code,
                                "attempt": attempt,
                                "delay_seconds": delay
                            }
                        )
                        time.sleep(delay)
                        continue
                
                # Non-retryable error or max retries reached
                break
                
            except (BotoCoreError, json.JSONDecodeError, KeyError) as e:
                last_error = e
                attempt += 1
                if attempt < self.max_retries:
                    delay = self.backoff_base ** attempt
                    logger.warning(
                        f"Transient error occurred, retrying in {delay}s",
                        extra={
                            "request_id": request_id,
                            "error_type": type(e).__name__,
                            "attempt": attempt,
                            "delay_seconds": delay
                        }
                    )
                    time.sleep(delay)
                    continue
                break
        
        # All retries exhausted or non-retryable error
        self._handle_failure(last_error, request_id, start_time)

    def _prepare_request_body(self, text: str) -> Dict[str, Any]:
        """
        Prepare the request body for the embedding model.
        
        Different Bedrock embedding models may have different input formats.
        This method handles the format for Amazon Titan embeddings.
        
        Args:
            text: The input text to embed.
            
        Returns:
            Dictionary containing the request body.
        """
        # Amazon Titan Embeddings format
        if "titan-embed" in self.model_id:
            return {
                "inputText": text
            }
        
        # Cohere embeddings format
        elif "cohere.embed" in self.model_id:
            return {
                "texts": [text],
                "input_type": "search_query"
            }
        
        # Default format (Titan)
        return {
            "inputText": text
        }
    
    def _extract_embedding(self, response_body: Dict[str, Any]) -> List[float]:
        """
        Extract the embedding vector from the model response.
        
        Args:
            response_body: The parsed JSON response from the model.
            
        Returns:
            The embedding vector as a list of floats.
            
        Raises:
            KeyError: If the expected embedding field is not found.
        """
        # Amazon Titan Embeddings format
        if "embedding" in response_body:
            return response_body["embedding"]
        
        # Cohere embeddings format
        elif "embeddings" in response_body:
            return response_body["embeddings"][0]
        
        # Fallback
        raise KeyError(f"Could not find embedding in response: {response_body.keys()}")
    
    def _is_retryable_error(self, error_code: str) -> bool:
        """
        Determine if an error code indicates a retryable failure.
        
        Args:
            error_code: The AWS error code from the exception.
            
        Returns:
            True if the error is retryable, False otherwise.
        """
        retryable_codes = {
            "ThrottlingException",
            "ServiceUnavailableException",
            "InternalServerException",
            "TooManyRequestsException",
            "ModelTimeoutException"
        }
        return error_code in retryable_codes
    
    def _handle_failure(
        self,
        error: Exception,
        request_id: Optional[str],
        start_time: float
    ) -> None:
        """
        Handle embedding generation failure by logging and raising appropriate exception.
        
        **Validates: Requirements 2.2, 8.1, 10.3**
        
        Args:
            error: The exception that caused the failure.
            request_id: Optional request ID for tracking.
            start_time: The time when the request started.
            
        Raises:
            EmbeddingModelUnavailableError: When the model is unavailable.
            EmbeddingServiceError: For other errors.
        """
        duration_ms = (time.time() - start_time) * 1000
        
        # Track failure metrics (Requirement 10.3)
        log_metric(
            metric_name="embedding_generation_failed",
            value=1,
            unit="count",
            metadata={
                "request_id": request_id,
                "duration_ms": duration_ms,
                "error_type": type(error).__name__
            }
        )
        
        # Emit CloudWatch metrics (Requirement 10.3)
        emit_embedding_metric(
            success=False,
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        # Log error with context (Requirement 8.1)
        log_error(
            request_id=request_id or "unknown",
            error=error,
            context={
                "service": "embedding_service",
                "model_id": self.model_id,
                "duration_ms": duration_ms
            }
        )
        
        # Determine the appropriate exception to raise
        if isinstance(error, ClientError):
            error_code = error.response.get("Error", {}).get("Code", "Unknown")
            error_message = error.response.get("Error", {}).get("Message", str(error))
            
            # Model unavailable errors (Requirement 2.2)
            if error_code in {
                "ResourceNotFoundException",
                "ModelNotReadyException",
                "ServiceUnavailableException"
            }:
                raise EmbeddingModelUnavailableError(
                    f"Embedding model is unavailable: {error_message}"
                ) from error
            
            # Other client errors
            raise EmbeddingServiceError(
                f"Failed to generate embedding: {error_message}"
            ) from error
        
        # Generic errors
        raise EmbeddingServiceError(
            f"Failed to generate embedding: {str(error)}"
        ) from error
    
    def generate_embeddings_batch(
        self,
        texts: List[str],
        request_id: Optional[str] = None
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        This method generates embeddings for a batch of texts. Note that it
        processes texts sequentially to avoid rate limiting. For production use,
        consider implementing parallel processing with rate limiting.
        
        Args:
            texts: List of input texts to generate embeddings for.
            request_id: Optional request ID for tracking and logging.
            
        Returns:
            List of embedding vectors, one for each input text.
            
        Raises:
            EmbeddingModelUnavailableError: When the model is unavailable.
            EmbeddingServiceError: For other embedding generation errors.
        """
        if not texts:
            return []
        
        embeddings = []
        for i, text in enumerate(texts):
            logger.debug(
                f"Generating embedding {i+1}/{len(texts)}",
                extra={"request_id": request_id, "batch_index": i}
            )
            embedding = self.generate_embedding(text, request_id)
            embeddings.append(embedding)
        
        return embeddings
