"""
Lambda handler for ingesting and processing psalm data.

This handler accepts psalm data in batch format, extracts metadata, generates
embeddings using Amazon Bedrock, and stores them in the vector store for
semantic search.

**Validates: Requirements 5.1, 5.2, 5.3, 5.4**
"""

import json
import time
import uuid
from typing import Any, Dict, List, Optional

from src.shared.config import config
from src.shared.embedding_service import (
    EmbeddingService,
    EmbeddingModelUnavailableError,
    EmbeddingServiceError
)
from src.shared.logging_config import (
    get_logger,
    log_request_start,
    log_request_end,
    log_error,
    log_metric
)


logger = get_logger("data_ingestion")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for psalm data ingestion.
    
    This handler orchestrates the data ingestion pipeline:
    1. Validates and extracts psalm data from the event
    2. Processes each psalm to extract metadata
    3. Generates embeddings for each psalm
    4. Prepares data for storage in vector store (S3-based ingestion)
    5. Supports both insert and update operations
    
    **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 6.4**
    
    Args:
        event: Event containing psalm data in batch format.
               Expected format:
               {
                   "operation_type": "insert" | "update",  # Optional, defaults to "insert"
                   "psalms": [
                       {
                           "psalm_id": "Psalm 23",
                           "content": "The Lord is my shepherd...",
                           "themes": ["comfort", "guidance"],
                           "emotional_context": "peace, reassurance",
                           "historical_usage": "Funerals, comfort",
                           "key_verses": ["verse 1", "verse 4"]
                       },
                       ...
                   ]
               }
        context: Lambda context object.
        
    Returns:
        Response indicating ingestion status with details about processed psalms.
    """
    # Generate unique request ID for tracking
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    # Log request start
    log_request_start(request_id, event)
    
    try:
        # Validate configuration
        config.validate()
        
        # Extract operation type (Requirement 6.4)
        operation_type = extract_operation_type(event, request_id)
        
        # Extract psalm data from event (Requirement 5.1)
        psalms = extract_psalm_data(event, request_id)
        
        if not psalms:
            raise ValidationError("No psalm data provided for ingestion")
        
        logger.info(
            f"Starting {operation_type} operation for {len(psalms)} psalms",
            extra={
                "request_id": request_id,
                "psalm_count": len(psalms),
                "operation_type": operation_type
            }
        )
        
        # Initialize embedding service
        embedding_service = EmbeddingService()
        
        # Process each psalm (Requirements 5.1, 5.2, 5.3, 6.4)
        processed_psalms = []
        failed_psalms = []
        
        for psalm in psalms:
            try:
                processed_psalm = process_psalm(
                    psalm=psalm,
                    embedding_service=embedding_service,
                    request_id=request_id,
                    operation_type=operation_type
                )
                processed_psalms.append(processed_psalm)
                
            except Exception as e:
                # Log individual psalm failure but continue processing batch (Requirement 5.4)
                psalm_id = psalm.get("psalm_id", "unknown")
                logger.error(
                    f"Failed to process psalm {psalm_id}",
                    extra={
                        "request_id": request_id,
                        "psalm_id": psalm_id,
                        "operation_type": operation_type,
                        "error": str(e)
                    }
                )
                failed_psalms.append({
                    "psalm_id": psalm_id,
                    "error": str(e)
                })
        
        # Calculate processing duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log successful completion
        log_request_end(request_id, duration_ms, success=True)
        
        # Track ingestion metrics
        log_metric(
            metric_name=f"psalm_{operation_type}_success",
            value=len(processed_psalms),
            unit="count",
            metadata={
                "request_id": request_id,
                "duration_ms": duration_ms,
                "total_psalms": len(psalms),
                "failed_psalms": len(failed_psalms),
                "operation_type": operation_type
            }
        )
        
        # Prepare response
        response_body = {
            "request_id": request_id,
            "status": "success",
            "operation_type": operation_type,
            "processed_count": len(processed_psalms),
            "failed_count": len(failed_psalms),
            "duration_ms": duration_ms
        }
        
        if failed_psalms:
            response_body["failed_psalms"] = failed_psalms
        
        logger.info(
            f"{operation_type.capitalize()} operation completed",
            extra={
                "request_id": request_id,
                "operation_type": operation_type,
                "processed_count": len(processed_psalms),
                "failed_count": len(failed_psalms)
            }
        )
        
        return create_response(
            status_code=200,
            body=response_body,
            request_id=request_id
        )
        
    except ValidationError as e:
        # Handle validation errors
        duration_ms = (time.time() - start_time) * 1000
        log_request_end(request_id, duration_ms, success=False)
        
        return create_error_response(
            status_code=400,
            error_message=str(e),
            request_id=request_id
        )
        
    except EmbeddingModelUnavailableError as e:
        # Handle embedding service unavailability
        duration_ms = (time.time() - start_time) * 1000
        log_error(request_id, e, {"service": "embedding"})
        log_request_end(request_id, duration_ms, success=False)
        
        return create_error_response(
            status_code=503,
            error_message="The embedding service is currently unavailable. Please try again later.",
            request_id=request_id
        )
        
    except Exception as e:
        # Handle unexpected errors
        duration_ms = (time.time() - start_time) * 1000
        log_error(request_id, e, {"service": "data_ingestion", "unexpected": True})
        log_request_end(request_id, duration_ms, success=False)
        
        # Track error metrics
        log_metric(
            metric_name="psalm_ingestion_error",
            value=1,
            unit="count",
            metadata={
                "request_id": request_id,
                "error_type": type(e).__name__,
                "operation_type": event.get("operation_type", "insert")
            }
        )
        
        return create_error_response(
            status_code=500,
            error_message="An unexpected error occurred during ingestion. Please try again.",
            request_id=request_id
        )


class ValidationError(Exception):
    """Exception raised for input validation errors."""
    pass


def extract_operation_type(event: Dict[str, Any], request_id: str) -> str:
    """
    Extract and validate operation type from the event.
    
    **Validates: Requirement 6.4**
    
    Args:
        event: Lambda event containing operation type.
        request_id: Request ID for logging.
        
    Returns:
        Operation type: "insert" or "update" (defaults to "insert").
        
    Raises:
        ValidationError: If operation type is invalid.
    """
    # Extract body from event
    body = event.get("body")
    
    if body is None:
        # Check if operation_type is directly in the event
        operation_type = event.get("operation_type", "insert")
    else:
        # Parse JSON body if it's a string
        if isinstance(body, str):
            try:
                body = json.loads(body)
                operation_type = body.get("operation_type", "insert")
            except json.JSONDecodeError:
                # If JSON parsing fails, default to insert
                operation_type = "insert"
        else:
            operation_type = body.get("operation_type", "insert")
    
    # Validate operation type
    valid_operations = ["insert", "update"]
    if operation_type not in valid_operations:
        raise ValidationError(
            f"Invalid operation_type: {operation_type}. Must be one of: {', '.join(valid_operations)}"
        )
    
    logger.debug(
        f"Operation type: {operation_type}",
        extra={"request_id": request_id, "operation_type": operation_type}
    )
    
    return operation_type


def extract_psalm_data(event: Dict[str, Any], request_id: str) -> List[Dict[str, Any]]:
    """
    Extract and validate psalm data from the event.
    
    **Validates: Requirements 5.1, 5.4**
    
    Args:
        event: Lambda event containing psalm data.
        request_id: Request ID for logging.
        
    Returns:
        List of psalm dictionaries.
        
    Raises:
        ValidationError: If psalm data is invalid or missing.
    """
    # Extract body from event
    body = event.get("body")
    
    if body is None:
        # Check if psalms are directly in the event (for direct Lambda invocation)
        if "psalms" in event:
            body = event
        else:
            raise ValidationError("Request body is required")
    
    # Parse JSON body if it's a string
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            raise ValidationError("Invalid JSON in request body")
    
    # Extract psalms array
    psalms = body.get("psalms", [])
    
    if not isinstance(psalms, list):
        raise ValidationError("'psalms' must be an array")
    
    if not psalms:
        raise ValidationError("At least one psalm is required for ingestion")
    
    # Validate each psalm has required fields
    for i, psalm in enumerate(psalms):
        validate_psalm_structure(psalm, i)
    
    logger.info(
        f"Extracted {len(psalms)} psalms for ingestion",
        extra={"request_id": request_id, "psalm_count": len(psalms)}
    )
    
    return psalms


def validate_psalm_structure(psalm: Dict[str, Any], index: int) -> None:
    """
    Validate that a psalm has the required structure.
    
    **Validates: Requirement 5.1**
    
    Args:
        psalm: Psalm dictionary to validate.
        index: Index of the psalm in the batch (for error messages).
        
    Raises:
        ValidationError: If psalm structure is invalid.
    """
    if not isinstance(psalm, dict):
        raise ValidationError(f"Psalm at index {index} must be an object")
    
    # Required fields
    required_fields = ["psalm_id", "content"]
    for field in required_fields:
        if field not in psalm or not psalm[field]:
            raise ValidationError(
                f"Psalm at index {index} is missing required field: {field}"
            )
    
    # Validate psalm_id format
    psalm_id = psalm["psalm_id"]
    if not isinstance(psalm_id, str):
        raise ValidationError(
            f"Psalm at index {index}: psalm_id must be a string"
        )
    
    # Validate content
    content = psalm["content"]
    if not isinstance(content, str) or not content.strip():
        raise ValidationError(
            f"Psalm at index {index}: content must be a non-empty string"
        )


def process_psalm(
    psalm: Dict[str, Any],
    embedding_service: EmbeddingService,
    request_id: str,
    operation_type: str = "insert"
) -> Dict[str, Any]:
    """
    Process a single psalm: extract metadata and generate embedding.
    
    **Validates: Requirements 5.1, 5.2, 5.3, 6.4**
    
    Args:
        psalm: Psalm data dictionary.
        embedding_service: Embedding service instance.
        request_id: Request ID for logging.
        operation_type: Type of operation ("insert" or "update").
        
    Returns:
        Processed psalm with embedding and extracted metadata.
        
    Raises:
        EmbeddingServiceError: If embedding generation fails.
    """
    psalm_id = psalm["psalm_id"]
    
    logger.info(
        f"Processing psalm {psalm_id} for {operation_type}",
        extra={
            "request_id": request_id,
            "psalm_id": psalm_id,
            "operation_type": operation_type
        }
    )
    
    # Extract psalm metadata (Requirement 5.1)
    metadata = extract_psalm_metadata(psalm)
    
    # Prepare text for embedding generation
    # Combine content with metadata for richer semantic representation
    embedding_text = prepare_embedding_text(psalm, metadata)
    
    # Generate embedding (Requirements 5.2, 6.4)
    # For update operations, regenerate embeddings to reflect updated data
    logger.debug(
        f"Generating embedding for {psalm_id} ({operation_type})",
        extra={
            "request_id": request_id,
            "psalm_id": psalm_id,
            "operation_type": operation_type
        }
    )
    
    embedding = embedding_service.generate_embedding(
        text=embedding_text,
        request_id=request_id
    )
    
    # Prepare processed psalm data (Requirement 5.3)
    processed_psalm = {
        "psalm_id": psalm_id,
        "content": psalm["content"],
        "metadata": metadata,
        "embedding": embedding,
        "embedding_dimension": len(embedding),
        "operation_type": operation_type
    }
    
    logger.info(
        f"Successfully processed {psalm_id} for {operation_type}",
        extra={
            "request_id": request_id,
            "psalm_id": psalm_id,
            "operation_type": operation_type,
            "embedding_dimension": len(embedding)
        }
    )
    
    return processed_psalm


def extract_psalm_metadata(psalm: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and structure psalm metadata.
    
    **Validates: Requirement 5.1**
    
    Args:
        psalm: Raw psalm data.
        
    Returns:
        Structured metadata dictionary.
    """
    metadata = {
        "psalm_id": psalm["psalm_id"],
        "themes": psalm.get("themes", []),
        "emotional_context": psalm.get("emotional_context", ""),
        "historical_usage": psalm.get("historical_usage", ""),
        "key_verses": psalm.get("key_verses", [])
    }
    
    # Ensure themes is a list
    if isinstance(metadata["themes"], str):
        metadata["themes"] = [t.strip() for t in metadata["themes"].split(",")]
    
    # Ensure key_verses is a list
    if isinstance(metadata["key_verses"], str):
        metadata["key_verses"] = [v.strip() for v in metadata["key_verses"].split(",")]
    
    return metadata


def prepare_embedding_text(psalm: Dict[str, Any], metadata: Dict[str, Any]) -> str:
    """
    Prepare text for embedding generation by combining content with metadata.
    
    This creates a richer semantic representation by including themes and
    emotional context alongside the psalm content.
    
    Args:
        psalm: Psalm data.
        metadata: Extracted metadata.
        
    Returns:
        Combined text for embedding generation.
    """
    parts = [psalm["content"]]
    
    # Add themes if available
    if metadata["themes"]:
        themes_text = "Themes: " + ", ".join(metadata["themes"])
        parts.append(themes_text)
    
    # Add emotional context if available
    if metadata["emotional_context"]:
        context_text = "Emotional context: " + metadata["emotional_context"]
        parts.append(context_text)
    
    # Combine all parts
    return "\n\n".join(parts)


def create_response(
    status_code: int,
    body: Dict[str, Any],
    request_id: str
) -> Dict[str, Any]:
    """
    Create a Lambda response with proper headers.
    
    Args:
        status_code: HTTP status code.
        body: Response body dictionary.
        request_id: Request ID for tracking.
        
    Returns:
        Lambda response dictionary.
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "X-Request-ID": request_id
        },
        "body": json.dumps(body)
    }


def create_error_response(
    status_code: int,
    error_message: str,
    request_id: str
) -> Dict[str, Any]:
    """
    Create an error response with appropriate HTTP status code.
    
    Args:
        status_code: HTTP status code.
        error_message: User-friendly error message.
        request_id: Request ID for tracking.
        
    Returns:
        Lambda error response dictionary.
    """
    error_body = {
        "error": error_message,
        "request_id": request_id,
        "status": "error"
    }
    
    return create_response(status_code, error_body, request_id)
