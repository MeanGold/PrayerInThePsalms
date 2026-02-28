"""
Lambda handler for processing psalm recommendation requests.

This handler accepts user emotional input and returns personalized psalm recommendations
using the RAG pipeline with Amazon Bedrock.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 7.1, 7.2, 7.3, 7.4, 8.4, 9.1, 9.2, 9.3, 9.4, 10.2**
"""

import json
import time
import uuid
import re
from typing import Any, Dict, Optional, List

from src.shared.config import config
from src.shared.embedding_service import EmbeddingService, EmbeddingModelUnavailableError, EmbeddingServiceError
from src.shared.vector_store import BedrockKnowledgeBaseVectorStore, VectorStoreUnavailableError, VectorStoreError
from src.shared.llm_service import LLMService, LLMGenerationFailedError, LLMServiceError
from src.shared.logging_config import get_logger, log_request_start, log_request_end, log_error, log_metric
from src.shared.metrics import emit_request_metric


logger = get_logger("handler")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for psalm recommendation requests.
    
    This handler orchestrates the RAG pipeline:
    1. Validates and extracts user emotional input
    2. Generates embedding for the input
    3. Searches for semantically similar psalms
    4. Generates personalized recommendations using LLM
    5. Returns formatted JSON response
    
    **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 7.1, 7.2, 7.3, 7.4, 8.4, 9.1, 9.2, 9.3, 9.4, 10.2**
    
    Args:
        event: API Gateway event containing user emotional input.
        context: Lambda context object.
        
    Returns:
        API Gateway response with psalm recommendations or error message.
    """
    # Generate unique request ID for tracking (Requirement 10.2)
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    # Log request start (Requirement 8.4)
    log_request_start(request_id, event)
    
    try:
        # Validate configuration
        config.validate()
        
        # Extract and validate emotional input (Requirements 1.1, 1.2, 1.3)
        emotional_input = extract_emotional_input(event, request_id)
        
        # Initialize services
        embedding_service = EmbeddingService()
        vector_store = BedrockKnowledgeBaseVectorStore()
        llm_service = LLMService()
        
        # Step 1: Generate embedding for user input (Requirement 2.1)
        logger.info("Generating embedding for user input", extra={"request_id": request_id})
        embedding = embedding_service.generate_embedding(emotional_input, request_id)
        
        # Step 2: Search for semantically similar psalms (Requirement 3.1)
        logger.info("Searching for similar psalms", extra={"request_id": request_id})
        search_results = vector_store.search(
            query_embedding=embedding,
            request_id=request_id
        )
        
        # Convert search results to format expected by LLM
        retrieved_psalms = format_psalms_for_llm(search_results)
        
        # Step 3: Generate personalized recommendations (Requirement 4.1)
        logger.info("Generating LLM recommendation", extra={"request_id": request_id})
        try:
            recommendation = llm_service.generate_recommendation(
                emotional_input=emotional_input,
                retrieved_psalms=retrieved_psalms,
                request_id=request_id
            )
            
            # Format successful response (Requirement 7.2)
            response_body = {
                "request_id": request_id,
                "recommendations": recommendation.to_dict()
            }
            
        except (LLMGenerationFailedError, LLMServiceError) as e:
            # Fallback: return psalm references without personalized text (Requirement 8.3)
            logger.warning(
                "LLM generation failed, using fallback response",
                extra={"request_id": request_id, "error": str(e)}
            )
            fallback_response = llm_service.generate_fallback_response(retrieved_psalms)
            response_body = {
                "request_id": request_id,
                "recommendations": fallback_response
            }
        
        # Calculate processing duration (Requirement 10.2)
        duration_ms = (time.time() - start_time) * 1000
        
        # Log successful completion
        log_request_end(request_id, duration_ms, success=True)
        
        # Track request metrics (Requirement 10.1)
        log_metric(
            metric_name="request_success",
            value=1,
            unit="count",
            metadata={
                "request_id": request_id,
                "duration_ms": duration_ms
            }
        )
        
        # Emit CloudWatch metrics for request count, latency (Requirements 10.1, 10.2)
        emit_request_metric(
            success=True,
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        # Return successful response (Requirement 7.2)
        return create_response(
            status_code=200,
            body=response_body,
            request_id=request_id
        )
        
    except ValidationError as e:
        # Handle input validation errors (Requirement 7.3)
        duration_ms = (time.time() - start_time) * 1000
        log_request_end(request_id, duration_ms, success=False)
        
        # Emit error metrics
        emit_request_metric(
            success=False,
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        return create_error_response(
            status_code=400,
            error_message=str(e),
            request_id=request_id
        )
        
    except EmbeddingModelUnavailableError as e:
        # Handle embedding service unavailability (Requirement 8.1)
        duration_ms = (time.time() - start_time) * 1000
        log_error(request_id, e, {"service": "embedding"})
        log_request_end(request_id, duration_ms, success=False)
        
        # Emit error metrics
        emit_request_metric(
            success=False,
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        return create_error_response(
            status_code=503,
            error_message="The embedding service is currently unavailable. Please try again later.",
            request_id=request_id
        )
        
    except (EmbeddingServiceError, VectorStoreError) as e:
        # Handle other service errors (Requirement 7.3)
        duration_ms = (time.time() - start_time) * 1000
        log_error(request_id, e, {"service": "rag_pipeline"})
        log_request_end(request_id, duration_ms, success=False)
        
        # Emit error metrics
        emit_request_metric(
            success=False,
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        return create_error_response(
            status_code=500,
            error_message="An error occurred while processing your request. Please try again.",
            request_id=request_id
        )
        
    except Exception as e:
        # Handle unexpected errors (Requirement 8.4)
        duration_ms = (time.time() - start_time) * 1000
        log_error(request_id, e, {"service": "handler", "unexpected": True})
        log_request_end(request_id, duration_ms, success=False)
        
        # Track error metrics (Requirement 10.1)
        log_metric(
            metric_name="request_error",
            value=1,
            unit="count",
            metadata={
                "request_id": request_id,
                "error_type": type(e).__name__
            }
        )
        
        # Emit CloudWatch error metrics
        emit_request_metric(
            success=False,
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        return create_error_response(
            status_code=500,
            error_message="An unexpected error occurred. Please try again.",
            request_id=request_id
        )


class ValidationError(Exception):
    """Exception raised for input validation errors."""
    pass


def extract_emotional_input(event: Dict[str, Any], request_id: str) -> str:
    """
    Extract and validate emotional input from API Gateway event.
    
    **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
    
    Args:
        event: API Gateway event.
        request_id: Request ID for logging.
        
    Returns:
        Validated emotional input (1-2 sentences).
        
    Raises:
        ValidationError: If input is invalid.
    """
    # Extract body from event (Requirement 1.4)
    body = event.get("body")
    
    if not body:
        raise ValidationError("Request body is required")
    
    # Parse JSON body if it's a string
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            raise ValidationError("Invalid JSON in request body")
    
    # Extract emotional input field
    emotional_input = body.get("emotional_input", "").strip()
    
    # Validate non-empty (Requirement 1.2)
    if not emotional_input:
        raise ValidationError("Emotional input is required. Please describe how you're feeling in 1-2 sentences.")
    
    # Process and limit to 2 sentences (Requirement 1.3)
    emotional_input = limit_to_sentences(emotional_input, max_sentences=config.MAX_INPUT_SENTENCES)
    
    logger.info(
        "Emotional input validated",
        extra={
            "request_id": request_id,
            "input_length": len(emotional_input),
            "sentence_count": count_sentences(emotional_input)
        }
    )
    
    return emotional_input


def limit_to_sentences(text: str, max_sentences: int = 2) -> str:
    """
    Limit text to a maximum number of sentences.
    
    **Validates: Requirement 1.3**
    
    Args:
        text: Input text.
        max_sentences: Maximum number of sentences to keep.
        
    Returns:
        Text limited to max_sentences.
    """
    # Split by sentence-ending punctuation
    sentences = re.split(r'[.!?]+', text)
    
    # Filter out empty strings and take first max_sentences
    sentences = [s.strip() for s in sentences if s.strip()]
    limited_sentences = sentences[:max_sentences]
    
    # Rejoin with periods
    return ". ".join(limited_sentences) + "." if limited_sentences else text


def count_sentences(text: str) -> int:
    """
    Count the number of sentences in text.
    
    Args:
        text: Input text.
        
    Returns:
        Number of sentences.
    """
    sentences = re.split(r'[.!?]+', text)
    return len([s for s in sentences if s.strip()])


def format_psalms_for_llm(search_results: List[Any]) -> List[Dict[str, Any]]:
    """
    Format search results into the structure expected by LLM service.
    
    Args:
        search_results: List of SearchResult objects from vector store.
        
    Returns:
        List of psalm dictionaries with metadata.
    """
    formatted_psalms = []
    
    for result in search_results:
        # Extract psalm number from psalm_id (e.g., "Psalm 23" -> 23)
        psalm_number = extract_psalm_number(result.psalm_id)
        
        psalm_dict = {
            "psalm_number": psalm_number,
            "content": result.content,
            "themes": result.metadata.get("themes", []),
            "emotional_context": result.metadata.get("emotional_context", ""),
            "key_verses": result.metadata.get("key_verses", []),
            "similarity_score": result.similarity_score
        }
        formatted_psalms.append(psalm_dict)
    
    return formatted_psalms


def extract_psalm_number(psalm_id: str) -> int:
    """
    Extract psalm number from psalm ID string.
    
    Args:
        psalm_id: Psalm identifier (e.g., "Psalm 23", "psalm_23", "23").
        
    Returns:
        Psalm number as integer, or 0 if not found.
    """
    # Try to find a number in the string
    match = re.search(r'\d+', psalm_id)
    if match:
        return int(match.group())
    return 0


def create_response(
    status_code: int,
    body: Dict[str, Any],
    request_id: str
) -> Dict[str, Any]:
    """
    Create an API Gateway response with proper headers.
    
    **Validates: Requirements 7.2, 9.3**
    
    Args:
        status_code: HTTP status code.
        body: Response body dictionary.
        request_id: Request ID for tracking.
        
    Returns:
        API Gateway response dictionary.
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "X-Request-ID": request_id,
            # CORS headers (if needed)
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "POST,OPTIONS"
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
    
    **Validates: Requirement 7.3**
    
    Args:
        status_code: HTTP status code.
        error_message: User-friendly error message.
        request_id: Request ID for tracking.
        
    Returns:
        API Gateway error response dictionary.
    """
    error_body = {
        "error": error_message,
        "request_id": request_id
    }
    
    return create_response(status_code, error_body, request_id)
