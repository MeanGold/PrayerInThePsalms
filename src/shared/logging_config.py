"""
Logging configuration with structured logging for the Psalm Recommendation RAG system.

This module provides structured logging using AWS Lambda Powertools, ensuring
consistent log formatting, correlation IDs, and proper context for debugging.

**Validates: Requirements 8.4, 10.2**
"""

import logging
from typing import Any, Dict, Optional
from aws_lambda_powertools import Logger
from aws_lambda_powertools.logging import correlation_paths

from .config import config


# Initialize the Lambda Powertools logger with structured logging
logger = Logger(
    service=config.SERVICE_NAME,
    level=config.LOG_LEVEL,
    log_uncaught_exceptions=True,
    json_default=str  # Handle non-serializable objects
)


def get_logger(name: Optional[str] = None) -> Logger:
    """
    Get a logger instance with optional name suffix.
    
    Args:
        name: Optional name to append to the service name for component-specific logging.
        
    Returns:
        Configured Logger instance.
    """
    if name:
        return Logger(
            service=f"{config.SERVICE_NAME}.{name}",
            level=config.LOG_LEVEL,
            child=True
        )
    return logger


def log_request_start(request_id: str, event: Dict[str, Any]) -> None:
    """
    Log the start of a request with sanitized event data.
    
    Args:
        request_id: Unique identifier for the request.
        event: Lambda event data (will be sanitized for PII).
    """
    # Sanitize event data to remove potential PII (Requirement 9.2)
    sanitized_event = _sanitize_event(event) if not config.ENABLE_PII_LOGGING else event
    
    logger.info(
        "Request started",
        extra={
            "request_id": request_id,
            "event_keys": list(sanitized_event.keys())
        }
    )


def log_request_end(request_id: str, duration_ms: float, success: bool) -> None:
    """
    Log the end of a request with performance metrics.
    
    Args:
        request_id: Unique identifier for the request.
        duration_ms: Request processing duration in milliseconds.
        success: Whether the request completed successfully.
    """
    logger.info(
        "Request completed",
        extra={
            "request_id": request_id,
            "duration_ms": duration_ms,
            "success": success
        }
    )


def log_error(
    request_id: str,
    error: Exception,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an error with sufficient context for debugging (Requirement 8.4).
    
    Args:
        request_id: Unique identifier for the request.
        error: The exception that occurred.
        context: Additional context about the error.
    """
    error_context = {
        "request_id": request_id,
        "error_type": type(error).__name__,
        "error_message": str(error)
    }
    
    if context:
        error_context.update(context)
    
    logger.error(
        "Error occurred",
        extra=error_context,
        exc_info=True
    )


def log_metric(
    metric_name: str,
    value: float,
    unit: str,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log a metric for monitoring (Requirement 10.1, 10.3, 10.4).
    
    Args:
        metric_name: Name of the metric (e.g., "embedding_generation_success").
        value: Metric value.
        unit: Unit of measurement (e.g., "count", "milliseconds").
        metadata: Additional metadata about the metric.
    """
    metric_data = {
        "metric_name": metric_name,
        "value": value,
        "unit": unit
    }
    
    if metadata:
        metric_data.update(metadata)
    
    logger.info(
        "Metric recorded",
        extra=metric_data
    )


def _sanitize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove potential PII from event data for logging.
    
    Args:
        event: Raw event data.
        
    Returns:
        Sanitized event data safe for logging.
    """
    # Create a shallow copy to avoid modifying the original
    sanitized = {}
    
    # List of keys that are safe to log
    safe_keys = {
        "httpMethod",
        "path",
        "requestContext",
        "headers",  # Will be further sanitized
        "queryStringParameters",
        "pathParameters"
    }
    
    for key, value in event.items():
        if key in safe_keys:
            if key == "headers":
                # Remove authorization and other sensitive headers
                sanitized[key] = {
                    k: v for k, v in value.items()
                    if k.lower() not in {"authorization", "cookie", "x-api-key"}
                }
            else:
                sanitized[key] = value
    
    return sanitized


def inject_lambda_context(func):
    """
    Decorator to inject Lambda context into logs.
    
    This is a wrapper around Lambda Powertools' inject_lambda_context
    that adds request ID correlation.
    """
    return logger.inject_lambda_context(
        correlation_id_path=correlation_paths.API_GATEWAY_REST,
        log_event=not config.ENABLE_PII_LOGGING  # Only log full event if PII logging is enabled
    )(func)
