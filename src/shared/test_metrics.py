"""
Unit tests for the CloudWatch metrics module.

**Validates: Requirements 10.1, 10.2, 10.3, 10.4**
"""

import pytest
from unittest.mock import Mock, patch, call
from botocore.exceptions import ClientError

from .metrics import (
    MetricsClient,
    MetricUnit,
    get_metrics_client,
    emit_request_metric,
    emit_embedding_metric,
    emit_llm_metric,
    emit_vector_store_metric
)


@pytest.fixture
def mock_cloudwatch_client():
    """Create a mock CloudWatch client."""
    return Mock()


@pytest.fixture
def metrics_client(mock_cloudwatch_client):
    """Create a MetricsClient with mocked CloudWatch client."""
    return MetricsClient(
        namespace="TestNamespace",
        cloudwatch_client=mock_cloudwatch_client
    )


class TestMetricsClient:
    """Test suite for MetricsClient class."""
    
    def test_initialization(self, metrics_client):
        """Test MetricsClient initialization."""
        assert metrics_client.namespace == "TestNamespace"
        assert metrics_client._buffer_size == 20
        assert len(metrics_client._metric_buffer) == 0
    
    def test_emit_metric_basic(self, metrics_client):
        """Test emitting a basic metric."""
        metrics_client.emit_metric(
            metric_name="TestMetric",
            value=1.0,
            unit=MetricUnit.COUNT
        )
        
        assert len(metrics_client._metric_buffer) == 1
        metric = metrics_client._metric_buffer[0]
        assert metric["MetricName"] == "TestMetric"
        assert metric["Value"] == 1.0
        assert metric["Unit"] == "Count"
        assert "Timestamp" in metric
    
    def test_emit_metric_with_dimensions(self, metrics_client):
        """Test emitting a metric with dimensions."""
        metrics_client.emit_metric(
            metric_name="TestMetric",
            value=100.0,
            unit=MetricUnit.MILLISECONDS,
            dimensions={"Service": "TestService", "Status": "Success"}
        )
        
        assert len(metrics_client._metric_buffer) == 1
        metric = metrics_client._metric_buffer[0]
        assert metric["MetricName"] == "TestMetric"
        assert metric["Value"] == 100.0
        assert metric["Unit"] == "Milliseconds"
        assert len(metric["Dimensions"]) == 2
        
        # Check dimensions
        dimension_dict = {d["Name"]: d["Value"] for d in metric["Dimensions"]}
        assert dimension_dict["Service"] == "TestService"
        assert dimension_dict["Status"] == "Success"
    
    def test_flush_metrics(self, metrics_client, mock_cloudwatch_client):
        """Test flushing metrics to CloudWatch."""
        # Add some metrics
        metrics_client.emit_metric("Metric1", 1.0, MetricUnit.COUNT)
        metrics_client.emit_metric("Metric2", 2.0, MetricUnit.COUNT)
        
        # Verify buffer has metrics before flush
        assert len(metrics_client._metric_buffer) == 2
        
        # Flush
        metrics_client.flush()
        
        # Verify CloudWatch API was called
        mock_cloudwatch_client.put_metric_data.assert_called_once()
        
        # Get the actual call arguments
        call_args = mock_cloudwatch_client.put_metric_data.call_args
        
        # Check if using positional or keyword arguments
        if call_args.kwargs:
            assert call_args.kwargs["Namespace"] == "TestNamespace"
            assert len(call_args.kwargs["MetricData"]) == 2
        else:
            # Fallback to positional args
            assert call_args[1]["Namespace"] == "TestNamespace"
            assert len(call_args[1]["MetricData"]) == 2
        
        # Buffer should be cleared
        assert len(metrics_client._metric_buffer) == 0
    
    def test_auto_flush_on_buffer_full(self, metrics_client, mock_cloudwatch_client):
        """Test automatic flush when buffer reaches limit."""
        # Add metrics up to buffer size
        for i in range(20):
            metrics_client.emit_metric(f"Metric{i}", float(i), MetricUnit.COUNT)
        
        # Should have auto-flushed
        mock_cloudwatch_client.put_metric_data.assert_called_once()
        assert len(metrics_client._metric_buffer) == 0
    
    def test_flush_handles_client_error(self, metrics_client, mock_cloudwatch_client):
        """Test that flush handles CloudWatch client errors gracefully."""
        # Configure mock to raise error
        mock_cloudwatch_client.put_metric_data.side_effect = ClientError(
            {"Error": {"Code": "ServiceUnavailable", "Message": "Service unavailable"}},
            "PutMetricData"
        )
        
        # Add a metric
        metrics_client.emit_metric("TestMetric", 1.0, MetricUnit.COUNT)
        
        # Flush should not raise exception
        metrics_client.flush()
        
        # Buffer should be cleared even on error
        assert len(metrics_client._metric_buffer) == 0
    
    def test_emit_request_metric_success(self, metrics_client):
        """Test emitting successful request metrics."""
        metrics_client.emit_request_metric(
            success=True,
            duration_ms=150.0,
            request_id="test-request-id"
        )
        
        # Should emit 2 metrics: RequestCount and RequestLatency
        assert len(metrics_client._metric_buffer) == 2
        
        # Check RequestCount metric
        request_count = next(m for m in metrics_client._metric_buffer if m["MetricName"] == "RequestCount")
        assert request_count["Value"] == 1
        assert request_count["Unit"] == "Count"
        
        # Check RequestLatency metric
        request_latency = next(m for m in metrics_client._metric_buffer if m["MetricName"] == "RequestLatency")
        assert request_latency["Value"] == 150.0
        assert request_latency["Unit"] == "Milliseconds"
    
    def test_emit_request_metric_failure(self, metrics_client):
        """Test emitting failed request metrics."""
        metrics_client.emit_request_metric(
            success=False,
            duration_ms=200.0,
            request_id="test-request-id"
        )
        
        # Should emit 3 metrics: RequestCount, RequestLatency, and ErrorRate
        assert len(metrics_client._metric_buffer) == 3
        
        # Check ErrorRate metric
        error_rate = next(m for m in metrics_client._metric_buffer if m["MetricName"] == "ErrorRate")
        assert error_rate["Value"] == 1
        assert error_rate["Unit"] == "Count"
    
    def test_emit_embedding_metric_success(self, metrics_client):
        """Test emitting successful embedding generation metrics."""
        metrics_client.emit_embedding_metric(
            success=True,
            duration_ms=50.0,
            request_id="test-request-id"
        )
        
        # Should emit 2 metrics: EmbeddingGenerationSuccess and EmbeddingGenerationLatency
        assert len(metrics_client._metric_buffer) == 2
        
        # Check success metric
        success_metric = next(m for m in metrics_client._metric_buffer if m["MetricName"] == "EmbeddingGenerationSuccess")
        assert success_metric["Value"] == 1
        assert success_metric["Unit"] == "Count"
        
        # Check latency metric
        latency_metric = next(m for m in metrics_client._metric_buffer if m["MetricName"] == "EmbeddingGenerationLatency")
        assert latency_metric["Value"] == 50.0
        assert latency_metric["Unit"] == "Milliseconds"
    
    def test_emit_embedding_metric_failure(self, metrics_client):
        """Test emitting failed embedding generation metrics."""
        metrics_client.emit_embedding_metric(
            success=False,
            duration_ms=100.0,
            request_id="test-request-id"
        )
        
        # Should emit 1 metric: EmbeddingGenerationFailed (no latency for failures)
        assert len(metrics_client._metric_buffer) == 1
        
        # Check failure metric
        failure_metric = metrics_client._metric_buffer[0]
        assert failure_metric["MetricName"] == "EmbeddingGenerationFailed"
        assert failure_metric["Value"] == 1
        assert failure_metric["Unit"] == "Count"
    
    def test_emit_llm_metric_success(self, metrics_client):
        """Test emitting successful LLM invocation metrics."""
        metrics_client.emit_llm_metric(
            success=True,
            duration_ms=500.0,
            request_id="test-request-id"
        )
        
        # Should emit 2 metrics: LLMInvocationSuccess and LLMInvocationLatency
        assert len(metrics_client._metric_buffer) == 2
        
        # Check success metric
        success_metric = next(m for m in metrics_client._metric_buffer if m["MetricName"] == "LLMInvocationSuccess")
        assert success_metric["Value"] == 1
        assert success_metric["Unit"] == "Count"
        
        # Check latency metric
        latency_metric = next(m for m in metrics_client._metric_buffer if m["MetricName"] == "LLMInvocationLatency")
        assert latency_metric["Value"] == 500.0
        assert latency_metric["Unit"] == "Milliseconds"
    
    def test_emit_llm_metric_failure(self, metrics_client):
        """Test emitting failed LLM invocation metrics."""
        metrics_client.emit_llm_metric(
            success=False,
            duration_ms=300.0,
            request_id="test-request-id"
        )
        
        # Should emit 1 metric: LLMInvocationFailed
        assert len(metrics_client._metric_buffer) == 1
        
        # Check failure metric
        failure_metric = metrics_client._metric_buffer[0]
        assert failure_metric["MetricName"] == "LLMInvocationFailed"
        assert failure_metric["Value"] == 1
        assert failure_metric["Unit"] == "Count"
    
    def test_emit_vector_store_metric_success(self, metrics_client):
        """Test emitting successful vector store query metrics."""
        metrics_client.emit_vector_store_metric(
            success=True,
            duration_ms=75.0,
            result_count=5,
            request_id="test-request-id"
        )
        
        # Should emit 3 metrics: VectorStoreQuerySuccess, VectorStoreQueryLatency, VectorStoreResultCount
        assert len(metrics_client._metric_buffer) == 3
        
        # Check success metric
        success_metric = next(m for m in metrics_client._metric_buffer if m["MetricName"] == "VectorStoreQuerySuccess")
        assert success_metric["Value"] == 1
        
        # Check latency metric
        latency_metric = next(m for m in metrics_client._metric_buffer if m["MetricName"] == "VectorStoreQueryLatency")
        assert latency_metric["Value"] == 75.0
        
        # Check result count metric
        result_count_metric = next(m for m in metrics_client._metric_buffer if m["MetricName"] == "VectorStoreResultCount")
        assert result_count_metric["Value"] == 5
    
    def test_emit_vector_store_metric_failure(self, metrics_client):
        """Test emitting failed vector store query metrics."""
        metrics_client.emit_vector_store_metric(
            success=False,
            duration_ms=100.0,
            request_id="test-request-id"
        )
        
        # Should emit 2 metrics: VectorStoreQueryFailed and VectorStoreQueryLatency
        assert len(metrics_client._metric_buffer) == 2
        
        # Check failure metric
        failure_metric = next(m for m in metrics_client._metric_buffer if m["MetricName"] == "VectorStoreQueryFailed")
        assert failure_metric["Value"] == 1


class TestConvenienceFunctions:
    """Test suite for convenience functions."""
    
    @patch('src.shared.metrics.get_metrics_client')
    def test_emit_request_metric_function(self, mock_get_client):
        """Test emit_request_metric convenience function."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        emit_request_metric(success=True, duration_ms=100.0, request_id="test-id")
        
        mock_client.emit_request_metric.assert_called_once_with(True, 100.0, "test-id")
        mock_client.flush.assert_called_once()
    
    @patch('src.shared.metrics.get_metrics_client')
    def test_emit_embedding_metric_function(self, mock_get_client):
        """Test emit_embedding_metric convenience function."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        emit_embedding_metric(success=True, duration_ms=50.0, request_id="test-id")
        
        mock_client.emit_embedding_metric.assert_called_once_with(True, 50.0, "test-id")
        mock_client.flush.assert_called_once()
    
    @patch('src.shared.metrics.get_metrics_client')
    def test_emit_llm_metric_function(self, mock_get_client):
        """Test emit_llm_metric convenience function."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        emit_llm_metric(success=False, duration_ms=200.0, request_id="test-id")
        
        mock_client.emit_llm_metric.assert_called_once_with(False, 200.0, "test-id")
        mock_client.flush.assert_called_once()
    
    @patch('src.shared.metrics.get_metrics_client')
    def test_emit_vector_store_metric_function(self, mock_get_client):
        """Test emit_vector_store_metric convenience function."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        emit_vector_store_metric(success=True, duration_ms=75.0, result_count=3, request_id="test-id")
        
        mock_client.emit_vector_store_metric.assert_called_once_with(True, 75.0, 3, "test-id")
        mock_client.flush.assert_called_once()


class TestMetricUnit:
    """Test suite for MetricUnit enum."""
    
    def test_metric_unit_values(self):
        """Test that MetricUnit enum has correct values."""
        assert MetricUnit.COUNT.value == "Count"
        assert MetricUnit.MILLISECONDS.value == "Milliseconds"
        assert MetricUnit.SECONDS.value == "Seconds"
        assert MetricUnit.PERCENT.value == "Percent"
        assert MetricUnit.BYTES.value == "Bytes"
