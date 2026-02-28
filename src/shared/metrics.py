"""
CloudWatch metrics emission module for the Psalm Recommendation RAG system.

This module provides functionality to emit custom CloudWatch metrics for monitoring
request count, latency, error rates, and service-specific metrics.

**Validates: Requirements 10.1, 10.2, 10.3, 10.4**
"""

import time
from typing import Dict, Any, Optional, List
from enum import Enum
import boto3
from botocore.exceptions import ClientError

from .config import config
from .logging_config import get_logger


logger = get_logger("metrics")


class MetricUnit(Enum):
    """Standard CloudWatch metric units."""
    SECONDS = "Seconds"
    MICROSECONDS = "Microseconds"
    MILLISECONDS = "Milliseconds"
    BYTES = "Bytes"
    KILOBYTES = "Kilobytes"
    MEGABYTES = "Megabytes"
    GIGABYTES = "Gigabytes"
    TERABYTES = "Terabytes"
    BITS = "Bits"
    KILOBITS = "Kilobits"
    MEGABITS = "Megabits"
    GIGABITS = "Gigabits"
    TERABITS = "Terabits"
    PERCENT = "Percent"
    COUNT = "Count"
    BYTES_PER_SECOND = "Bytes/Second"
    KILOBYTES_PER_SECOND = "Kilobytes/Second"
    MEGABYTES_PER_SECOND = "Megabytes/Second"
    GIGABYTES_PER_SECOND = "Gigabytes/Second"
    TERABYTES_PER_SECOND = "Terabytes/Second"
    BITS_PER_SECOND = "Bits/Second"
    KILOBITS_PER_SECOND = "Kilobits/Second"
    MEGABITS_PER_SECOND = "Megabits/Second"
    GIGABITS_PER_SECOND = "Gigabits/Second"
    TERABITS_PER_SECOND = "Terabits/Second"
    COUNT_PER_SECOND = "Count/Second"
    NONE = "None"


class MetricsClient:
    """
    Client for emitting CloudWatch metrics.
    
    This class provides methods to emit custom metrics to CloudWatch for monitoring
    system performance, errors, and service-specific operations.
    
    **Validates: Requirements 10.1, 10.2, 10.3, 10.4**
    """
    
    def __init__(
        self,
        namespace: Optional[str] = None,
        cloudwatch_client: Optional[Any] = None
    ):
        """
        Initialize the metrics client.
        
        Args:
            namespace: CloudWatch namespace for metrics. Defaults to service name.
            cloudwatch_client: Optional boto3 CloudWatch client.
        """
        self.namespace = namespace or f"AWS/Lambda/{config.SERVICE_NAME}"
        self.cloudwatch_client = cloudwatch_client or self._create_cloudwatch_client()
        self._metric_buffer: List[Dict[str, Any]] = []
        self._buffer_size = 20  # CloudWatch PutMetricData limit
        
        logger.info(
            "MetricsClient initialized",
            extra={"namespace": self.namespace}
        )
    
    def _create_cloudwatch_client(self) -> Any:
        """
        Create a boto3 CloudWatch client.
        
        Returns:
            Configured boto3 CloudWatch client.
        """
        return boto3.client(
            "cloudwatch",
            region_name=config.BEDROCK_REGION
        )
    
    def emit_metric(
        self,
        metric_name: str,
        value: float,
        unit: MetricUnit = MetricUnit.COUNT,
        dimensions: Optional[Dict[str, str]] = None,
        timestamp: Optional[float] = None
    ) -> None:
        """
        Emit a single metric to CloudWatch.
        
        **Validates: Requirement 10.1**
        
        Args:
            metric_name: Name of the metric.
            value: Metric value.
            unit: Unit of measurement (default: COUNT).
            dimensions: Optional dimensions for the metric (e.g., {"Service": "EmbeddingService"}).
            timestamp: Optional timestamp (defaults to current time).
        """
        metric_data = {
            "MetricName": metric_name,
            "Value": value,
            "Unit": unit.value,
            "Timestamp": timestamp or time.time()
        }
        
        if dimensions:
            metric_data["Dimensions"] = [
                {"Name": k, "Value": v} for k, v in dimensions.items()
            ]
        
        self._metric_buffer.append(metric_data)
        
        # Flush buffer if it reaches the limit
        if len(self._metric_buffer) >= self._buffer_size:
            self.flush()
    
    def flush(self) -> None:
        """
        Flush buffered metrics to CloudWatch.
        
        This method sends all buffered metrics to CloudWatch in a single API call.
        """
        if not self._metric_buffer:
            return
        
        try:
            # Create a copy of the buffer to send
            metrics_to_send = list(self._metric_buffer)
            
            self.cloudwatch_client.put_metric_data(
                Namespace=self.namespace,
                MetricData=metrics_to_send
            )
            
            logger.debug(
                f"Flushed {len(metrics_to_send)} metrics to CloudWatch",
                extra={
                    "namespace": self.namespace,
                    "metric_count": len(metrics_to_send)
                }
            )
            
            self._metric_buffer.clear()
            
        except ClientError as e:
            logger.error(
                "Failed to emit metrics to CloudWatch",
                extra={
                    "error": str(e),
                    "namespace": self.namespace,
                    "metric_count": len(self._metric_buffer)
                }
            )
            # Clear buffer to prevent memory buildup
            self._metric_buffer.clear()
    
    def emit_request_metric(
        self,
        success: bool,
        duration_ms: float,
        request_id: Optional[str] = None
    ) -> None:
        """
        Emit request-level metrics for monitoring.
        
        **Validates: Requirements 10.1, 10.2**
        
        Args:
            success: Whether the request was successful.
            duration_ms: Request processing duration in milliseconds.
            request_id: Optional request ID for tracking.
        """
        dimensions = {"RequestStatus": "Success" if success else "Error"}
        
        # Emit request count (Requirement 10.1)
        self.emit_metric(
            metric_name="RequestCount",
            value=1,
            unit=MetricUnit.COUNT,
            dimensions=dimensions
        )
        
        # Emit latency (Requirement 10.1)
        self.emit_metric(
            metric_name="RequestLatency",
            value=duration_ms,
            unit=MetricUnit.MILLISECONDS,
            dimensions=dimensions
        )
        
        # Emit error rate if request failed (Requirement 10.1)
        if not success:
            self.emit_metric(
                metric_name="ErrorRate",
                value=1,
                unit=MetricUnit.COUNT
            )
    
    def emit_embedding_metric(
        self,
        success: bool,
        duration_ms: float,
        request_id: Optional[str] = None
    ) -> None:
        """
        Emit embedding generation metrics.
        
        **Validates: Requirement 10.3**
        
        Args:
            success: Whether embedding generation was successful.
            duration_ms: Embedding generation duration in milliseconds.
            request_id: Optional request ID for tracking.
        """
        dimensions = {
            "Service": "EmbeddingService",
            "Status": "Success" if success else "Failed"
        }
        
        # Track successful and failed embedding generations (Requirement 10.3)
        metric_name = "EmbeddingGenerationSuccess" if success else "EmbeddingGenerationFailed"
        
        self.emit_metric(
            metric_name=metric_name,
            value=1,
            unit=MetricUnit.COUNT,
            dimensions=dimensions
        )
        
        # Emit latency for successful generations
        if success:
            self.emit_metric(
                metric_name="EmbeddingGenerationLatency",
                value=duration_ms,
                unit=MetricUnit.MILLISECONDS,
                dimensions={"Service": "EmbeddingService"}
            )
    
    def emit_llm_metric(
        self,
        success: bool,
        duration_ms: float,
        request_id: Optional[str] = None
    ) -> None:
        """
        Emit LLM invocation metrics.
        
        **Validates: Requirement 10.4**
        
        Args:
            success: Whether LLM invocation was successful.
            duration_ms: LLM invocation duration in milliseconds.
            request_id: Optional request ID for tracking.
        """
        dimensions = {
            "Service": "LLMService",
            "Status": "Success" if success else "Failed"
        }
        
        # Track successful and failed LLM invocations (Requirement 10.4)
        metric_name = "LLMInvocationSuccess" if success else "LLMInvocationFailed"
        
        self.emit_metric(
            metric_name=metric_name,
            value=1,
            unit=MetricUnit.COUNT,
            dimensions=dimensions
        )
        
        # Emit latency for successful invocations
        if success:
            self.emit_metric(
                metric_name="LLMInvocationLatency",
                value=duration_ms,
                unit=MetricUnit.MILLISECONDS,
                dimensions={"Service": "LLMService"}
            )
    
    def emit_vector_store_metric(
        self,
        success: bool,
        duration_ms: float,
        result_count: Optional[int] = None,
        request_id: Optional[str] = None
    ) -> None:
        """
        Emit vector store query performance metrics.
        
        **Validates: Requirement 10.1**
        
        Args:
            success: Whether vector store query was successful.
            duration_ms: Query duration in milliseconds.
            result_count: Optional number of results returned.
            request_id: Optional request ID for tracking.
        """
        dimensions = {
            "Service": "VectorStore",
            "Status": "Success" if success else "Failed"
        }
        
        # Track query success/failure
        metric_name = "VectorStoreQuerySuccess" if success else "VectorStoreQueryFailed"
        
        self.emit_metric(
            metric_name=metric_name,
            value=1,
            unit=MetricUnit.COUNT,
            dimensions=dimensions
        )
        
        # Emit query latency (performance metric)
        self.emit_metric(
            metric_name="VectorStoreQueryLatency",
            value=duration_ms,
            unit=MetricUnit.MILLISECONDS,
            dimensions={"Service": "VectorStore"}
        )
        
        # Emit result count if provided
        if result_count is not None:
            self.emit_metric(
                metric_name="VectorStoreResultCount",
                value=result_count,
                unit=MetricUnit.COUNT,
                dimensions={"Service": "VectorStore"}
            )


# Singleton instance
_metrics_client: Optional[MetricsClient] = None


def get_metrics_client() -> MetricsClient:
    """
    Get the singleton metrics client instance.
    
    Returns:
        MetricsClient instance.
    """
    global _metrics_client
    if _metrics_client is None:
        _metrics_client = MetricsClient()
    return _metrics_client


def emit_request_metric(
    success: bool,
    duration_ms: float,
    request_id: Optional[str] = None
) -> None:
    """
    Convenience function to emit request metrics.
    
    **Validates: Requirements 10.1, 10.2**
    """
    client = get_metrics_client()
    client.emit_request_metric(success, duration_ms, request_id)
    client.flush()


def emit_embedding_metric(
    success: bool,
    duration_ms: float,
    request_id: Optional[str] = None
) -> None:
    """
    Convenience function to emit embedding metrics.
    
    **Validates: Requirement 10.3**
    """
    client = get_metrics_client()
    client.emit_embedding_metric(success, duration_ms, request_id)
    client.flush()


def emit_llm_metric(
    success: bool,
    duration_ms: float,
    request_id: Optional[str] = None
) -> None:
    """
    Convenience function to emit LLM metrics.
    
    **Validates: Requirement 10.4**
    """
    client = get_metrics_client()
    client.emit_llm_metric(success, duration_ms, request_id)
    client.flush()


def emit_vector_store_metric(
    success: bool,
    duration_ms: float,
    result_count: Optional[int] = None,
    request_id: Optional[str] = None
) -> None:
    """
    Convenience function to emit vector store metrics.
    
    **Validates: Requirement 10.1**
    """
    client = get_metrics_client()
    client.emit_vector_store_metric(success, duration_ms, result_count, request_id)
    client.flush()
