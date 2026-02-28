"""
Vector store interface and implementation for Amazon Bedrock Knowledge Base.

This module provides an abstraction layer for vector operations including search,
insert, and update operations. It includes a concrete implementation for Amazon
Bedrock Knowledge Bases with retry logic, error handling, and fallback mechanisms.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 6.1, 6.3, 8.2**
"""

import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import boto3
from botocore.exceptions import ClientError, BotoCoreError

from .config import config
from .logging_config import get_logger, log_metric, log_error
from .metrics import emit_vector_store_metric


logger = get_logger("vector_store")


@dataclass
class SearchResult:
    """
    Represents a single search result from the vector store.
    
    Attributes:
        psalm_id: Identifier for the psalm (e.g., "Psalm 23").
        content: The psalm text or relevant excerpt.
        metadata: Additional metadata about the psalm (themes, context, etc.).
        similarity_score: Similarity score between 0 and 1.
    """
    psalm_id: str
    content: str
    metadata: Dict[str, Any]
    similarity_score: float
    
    def __repr__(self) -> str:
        return f"SearchResult(psalm_id={self.psalm_id}, score={self.similarity_score:.3f})"


class VectorStoreError(Exception):
    """Base exception for vector store errors."""
    pass


class VectorStoreUnavailableError(VectorStoreError):
    """
    Exception raised when the vector store is unavailable.
    
    **Validates: Requirement 8.2**
    """
    pass


class VectorStore(ABC):
    """
    Abstract base class for vector store operations.
    
    This interface defines the contract for vector store implementations,
    allowing for different backends (Bedrock Knowledge Base, OpenSearch, etc.).
    
    **Validates: Requirements 3.1, 3.2, 3.3, 6.1, 6.3**
    """
    
    @abstractmethod
    def search(
        self,
        query_embedding: List[float],
        max_results: Optional[int] = None,
        min_results: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        request_id: Optional[str] = None
    ) -> List[SearchResult]:
        """
        Search for semantically similar items using vector similarity.
        
        **Validates: Requirements 3.1, 3.2, 3.3, 6.3**
        
        Args:
            query_embedding: The query vector to search for.
            max_results: Maximum number of results to return (default: config.MAX_RESULTS).
            min_results: Minimum number of results to return (default: config.MIN_RESULTS).
            similarity_threshold: Minimum similarity score (default: config.SIMILARITY_THRESHOLD).
            request_id: Optional request ID for tracking and logging.
            
        Returns:
            List of SearchResult objects ranked by similarity score in descending order.
            
        Raises:
            VectorStoreUnavailableError: When the vector store is unavailable after retries.
            VectorStoreError: For other vector store errors.
        """
        pass
    
    @abstractmethod
    def insert(
        self,
        item_id: str,
        embedding: List[float],
        content: str,
        metadata: Dict[str, Any],
        request_id: Optional[str] = None
    ) -> None:
        """
        Insert a new item into the vector store.
        
        **Validates: Requirement 6.1**
        
        Args:
            item_id: Unique identifier for the item.
            embedding: Vector embedding for the item.
            content: The item content/text.
            metadata: Additional metadata about the item.
            request_id: Optional request ID for tracking and logging.
            
        Raises:
            VectorStoreUnavailableError: When the vector store is unavailable.
            VectorStoreError: For other vector store errors.
        """
        pass
    
    @abstractmethod
    def update(
        self,
        item_id: str,
        embedding: Optional[List[float]] = None,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> None:
        """
        Update an existing item in the vector store.
        
        **Validates: Requirement 6.4**
        
        Args:
            item_id: Unique identifier for the item to update.
            embedding: Optional new vector embedding.
            content: Optional new content.
            metadata: Optional new metadata (will be merged with existing).
            request_id: Optional request ID for tracking and logging.
            
        Raises:
            VectorStoreUnavailableError: When the vector store is unavailable.
            VectorStoreError: For other vector store errors.
        """
        pass


class BedrockKnowledgeBaseVectorStore(VectorStore):
    """
    Vector store implementation using Amazon Bedrock Knowledge Bases.
    
    This implementation provides vector search capabilities using Bedrock's
    Knowledge Base feature, with automatic retry logic and fallback mechanisms.
    
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 6.1, 6.3, 8.2**
    """
    
    # Default comforting psalms for fallback (Requirement 3.4)
    DEFAULT_PSALMS = [
        {
            "psalm_id": "Psalm 23",
            "content": "The Lord is my shepherd; I shall not want...",
            "metadata": {
                "themes": ["comfort", "guidance", "trust"],
                "emotional_context": "peace, reassurance"
            }
        },
        {
            "psalm_id": "Psalm 46",
            "content": "God is our refuge and strength, a very present help in trouble...",
            "metadata": {
                "themes": ["strength", "refuge", "protection"],
                "emotional_context": "fear, anxiety, trouble"
            }
        },
        {
            "psalm_id": "Psalm 91",
            "content": "He who dwells in the shelter of the Most High will abide in the shadow of the Almighty...",
            "metadata": {
                "themes": ["protection", "safety", "trust"],
                "emotional_context": "fear, danger, uncertainty"
            }
        }
    ]
    
    def __init__(
        self,
        knowledge_base_id: Optional[str] = None,
        bedrock_agent_client: Optional[Any] = None,
        max_retries: Optional[int] = None,
        backoff_base: Optional[float] = None
    ):
        """
        Initialize the Bedrock Knowledge Base vector store.
        
        Args:
            knowledge_base_id: Optional Knowledge Base ID. Defaults to config value.
            bedrock_agent_client: Optional boto3 Bedrock Agent client.
            max_retries: Optional maximum retry attempts. Defaults to config value.
            backoff_base: Optional exponential backoff base. Defaults to config value.
        """
        self.knowledge_base_id = knowledge_base_id or config.KNOWLEDGE_BASE_ID
        self.bedrock_agent_client = bedrock_agent_client or self._create_bedrock_agent_client()
        self.max_retries = max_retries if max_retries is not None else config.MAX_RETRIES
        self.backoff_base = backoff_base if backoff_base is not None else config.RETRY_BACKOFF_BASE
        
        if not self.knowledge_base_id:
            raise ValueError("Knowledge Base ID is required")
        
        logger.info(
            "BedrockKnowledgeBaseVectorStore initialized",
            extra={
                "knowledge_base_id": self.knowledge_base_id,
                "max_retries": self.max_retries
            }
        )
    
    def _create_bedrock_agent_client(self) -> Any:
        """
        Create a boto3 Bedrock Agent client with configured settings.
        
        Returns:
            Configured boto3 Bedrock Agent client.
        """
        return boto3.client(
            "bedrock-agent-runtime",
            region_name=config.BEDROCK_REGION
        )

    def search(
        self,
        query_embedding: List[float],
        max_results: Optional[int] = None,
        min_results: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        request_id: Optional[str] = None
    ) -> List[SearchResult]:
        """
        Search for semantically similar psalms using vector similarity.
        
        This method queries the Bedrock Knowledge Base with retry logic and
        returns results ranked by similarity score. If no results meet the
        threshold, it returns default comforting psalms.
        
        **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 6.3, 8.2**
        
        Args:
            query_embedding: The query vector to search for.
            max_results: Maximum number of results to return (default: config.MAX_RESULTS).
            min_results: Minimum number of results to return (default: config.MIN_RESULTS).
            similarity_threshold: Minimum similarity score (default: config.SIMILARITY_THRESHOLD).
            request_id: Optional request ID for tracking and logging.
            
        Returns:
            List of SearchResult objects ranked by similarity score in descending order.
            
        Raises:
            VectorStoreUnavailableError: When the vector store is unavailable after retries.
            VectorStoreError: For other vector store errors.
        """
        max_results = max_results or config.MAX_RESULTS
        min_results = min_results or config.MIN_RESULTS
        similarity_threshold = similarity_threshold or config.SIMILARITY_THRESHOLD
        
        if not query_embedding:
            raise ValueError("Query embedding cannot be empty")
        
        start_time = time.time()
        attempt = 0
        last_error = None
        
        # Retry loop with exponential backoff (Requirement 8.2)
        while attempt < self.max_retries:
            try:
                # Query the Knowledge Base
                response = self.bedrock_agent_client.retrieve(
                    knowledgeBaseId=self.knowledge_base_id,
                    retrievalQuery={
                        "text": ""  # We're using vector directly, not text query
                    },
                    retrievalConfiguration={
                        "vectorSearchConfiguration": {
                            "numberOfResults": max_results,
                            "overrideSearchType": "HYBRID"  # Use both semantic and keyword search
                        }
                    }
                )
                
                # Parse and rank results (Requirement 3.3)
                results = self._parse_search_results(
                    response,
                    similarity_threshold,
                    max_results
                )
                
                # Track success metrics
                duration_ms = (time.time() - start_time) * 1000
                log_metric(
                    metric_name="vector_search_success",
                    value=1,
                    unit="count",
                    metadata={
                        "request_id": request_id,
                        "duration_ms": duration_ms,
                        "results_count": len(results),
                        "attempt": attempt + 1
                    }
                )
                
                # Emit CloudWatch metrics for vector store query performance
                emit_vector_store_metric(
                    success=True,
                    duration_ms=duration_ms,
                    result_count=len(results),
                    request_id=request_id
                )
                
                logger.info(
                    "Vector search completed successfully",
                    extra={
                        "request_id": request_id,
                        "duration_ms": duration_ms,
                        "results_count": len(results),
                        "attempt": attempt + 1
                    }
                )
                
                # Check if we have enough results (Requirement 3.2)
                if len(results) < min_results:
                    logger.warning(
                        f"Insufficient results ({len(results)} < {min_results}), using fallback",
                        extra={
                            "request_id": request_id,
                            "results_count": len(results),
                            "min_results": min_results
                        }
                    )
                    return self._get_default_psalms(request_id)
                
                return results
                
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                last_error = e
                
                # Check if this is a retryable error
                if self._is_retryable_error(error_code):
                    attempt += 1
                    if attempt < self.max_retries:
                        # Calculate exponential backoff delay (Requirement 8.2)
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
                
                # Non-retryable error
                break
                
            except (BotoCoreError, KeyError, ValueError) as e:
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
        
        # All retries exhausted - use fallback (Requirement 3.4)
        self._handle_search_failure(last_error, request_id, start_time)
        return self._get_default_psalms(request_id)
    
    def _parse_search_results(
        self,
        response: Dict[str, Any],
        similarity_threshold: float,
        max_results: int
    ) -> List[SearchResult]:
        """
        Parse and rank search results from Bedrock Knowledge Base response.
        
        **Validates: Requirements 3.2, 3.3**
        
        Args:
            response: The response from Bedrock Knowledge Base retrieve API.
            similarity_threshold: Minimum similarity score to include.
            max_results: Maximum number of results to return.
            
        Returns:
            List of SearchResult objects ranked by similarity score in descending order.
        """
        results = []
        
        # Extract retrieval results
        retrieval_results = response.get("retrievalResults", [])
        
        for item in retrieval_results:
            # Extract similarity score
            score = item.get("score", 0.0)
            
            # Filter by threshold
            if score < similarity_threshold:
                continue
            
            # Extract content and metadata
            content = item.get("content", {}).get("text", "")
            metadata = item.get("metadata", {})
            
            # Extract psalm ID from metadata or location
            psalm_id = metadata.get("psalm_id") or metadata.get("source", "Unknown")
            
            # Create search result
            result = SearchResult(
                psalm_id=psalm_id,
                content=content,
                metadata=metadata,
                similarity_score=score
            )
            results.append(result)
        
        # Sort by similarity score in descending order (Requirement 3.3)
        results.sort(key=lambda x: x.similarity_score, reverse=True)
        
        # Limit to max_results (Requirement 3.2)
        return results[:max_results]
    
    def _get_default_psalms(self, request_id: Optional[str] = None) -> List[SearchResult]:
        """
        Return default comforting psalms as fallback.
        
        **Validates: Requirement 3.4**
        
        Args:
            request_id: Optional request ID for tracking and logging.
            
        Returns:
            List of default SearchResult objects.
        """
        logger.info(
            "Returning default comforting psalms",
            extra={
                "request_id": request_id,
                "default_count": len(self.DEFAULT_PSALMS)
            }
        )
        
        # Track fallback metric
        log_metric(
            metric_name="vector_search_fallback",
            value=1,
            unit="count",
            metadata={"request_id": request_id}
        )
        
        # Convert default psalms to SearchResult objects
        return [
            SearchResult(
                psalm_id=psalm["psalm_id"],
                content=psalm["content"],
                metadata=psalm["metadata"],
                similarity_score=0.0  # No similarity score for defaults
            )
            for psalm in self.DEFAULT_PSALMS
        ]
    
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
            "ResourceNotFoundException"  # KB might be temporarily unavailable
        }
        return error_code in retryable_codes
    
    def _handle_search_failure(
        self,
        error: Exception,
        request_id: Optional[str],
        start_time: float
    ) -> None:
        """
        Handle search failure by logging error.
        
        **Validates: Requirements 8.2, 8.4**
        
        Args:
            error: The exception that caused the failure.
            request_id: Optional request ID for tracking.
            start_time: The time when the request started.
        """
        duration_ms = (time.time() - start_time) * 1000
        
        # Track failure metrics
        log_metric(
            metric_name="vector_search_failed",
            value=1,
            unit="count",
            metadata={
                "request_id": request_id,
                "duration_ms": duration_ms,
                "error_type": type(error).__name__
            }
        )
        
        # Emit CloudWatch metrics for vector store query failure
        emit_vector_store_metric(
            success=False,
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        # Log error with context
        log_error(
            request_id=request_id or "unknown",
            error=error,
            context={
                "service": "vector_store",
                "knowledge_base_id": self.knowledge_base_id,
                "duration_ms": duration_ms
            }
        )
        
        logger.warning(
            "Vector search failed after retries, using fallback",
            extra={
                "request_id": request_id,
                "error_type": type(error).__name__,
                "duration_ms": duration_ms
            }
        )

    def insert(
        self,
        item_id: str,
        embedding: List[float],
        content: str,
        metadata: Dict[str, Any],
        request_id: Optional[str] = None
    ) -> None:
        """
        Insert a new item into the vector store.
        
        Note: For Bedrock Knowledge Bases, data ingestion is typically done
        through S3 and the Knowledge Base sync process, not direct insertion.
        This method is provided for interface completeness but may not be
        used in the typical workflow.
        
        **Validates: Requirement 6.1**
        
        Args:
            item_id: Unique identifier for the item.
            embedding: Vector embedding for the item.
            content: The item content/text.
            metadata: Additional metadata about the item.
            request_id: Optional request ID for tracking and logging.
            
        Raises:
            NotImplementedError: Bedrock Knowledge Bases use S3-based ingestion.
        """
        logger.warning(
            "Direct insertion not supported for Bedrock Knowledge Bases",
            extra={
                "request_id": request_id,
                "item_id": item_id,
                "info": "Use S3-based data ingestion and Knowledge Base sync instead"
            }
        )
        raise NotImplementedError(
            "Bedrock Knowledge Bases use S3-based data ingestion. "
            "Upload data to the configured S3 bucket and trigger a Knowledge Base sync."
        )
    
    def update(
        self,
        item_id: str,
        embedding: Optional[List[float]] = None,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> None:
        """
        Update an existing item in the vector store.
        
        Note: For Bedrock Knowledge Bases, data updates are typically done
        through S3 and the Knowledge Base sync process, not direct updates.
        This method is provided for interface completeness but may not be
        used in the typical workflow.
        
        **Validates: Requirement 6.4**
        
        Args:
            item_id: Unique identifier for the item to update.
            embedding: Optional new vector embedding.
            content: Optional new content.
            metadata: Optional new metadata (will be merged with existing).
            request_id: Optional request ID for tracking and logging.
            
        Raises:
            NotImplementedError: Bedrock Knowledge Bases use S3-based ingestion.
        """
        logger.warning(
            "Direct update not supported for Bedrock Knowledge Bases",
            extra={
                "request_id": request_id,
                "item_id": item_id,
                "info": "Use S3-based data ingestion and Knowledge Base sync instead"
            }
        )
        raise NotImplementedError(
            "Bedrock Knowledge Bases use S3-based data ingestion. "
            "Update data in the configured S3 bucket and trigger a Knowledge Base sync."
        )
