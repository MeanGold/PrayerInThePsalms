"""
Unit tests for the LLM service wrapper.

**Validates: Requirements 4.1, 4.2, 4.3, 4.4, 8.3, 8.4, 10.4**
"""

import json
import pytest
from unittest.mock import Mock, MagicMock, patch
from botocore.exceptions import ClientError

from .llm_service import (
    LLMService,
    LLMServiceError,
    LLMGenerationFailedError,
    PsalmRecommendation
)


@pytest.fixture
def mock_bedrock_client():
    """Create a mock Bedrock client."""
    return Mock()


@pytest.fixture
def llm_service(mock_bedrock_client):
    """Create an LLM service instance with mocked client."""
    return LLMService(
        bedrock_client=mock_bedrock_client,
        model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        max_retries=3,
        backoff_base=2.0,
        temperature=0.7,
        max_tokens=1000
    )


@pytest.fixture
def sample_emotional_input():
    """Sample user emotional input."""
    return "I'm feeling anxious and overwhelmed with all the challenges I'm facing."


@pytest.fixture
def sample_retrieved_psalms():
    """Sample retrieved psalms with metadata."""
    return [
        {
            "psalm_number": 23,
            "themes": ["comfort", "guidance", "trust"],
            "emotional_context": "Fear, anxiety, need for comfort",
            "key_verses": ["Psalm 23:1", "Psalm 23:4"]
        },
        {
            "psalm_number": 46,
            "themes": ["refuge", "strength", "protection"],
            "emotional_context": "Trouble, fear, need for security",
            "key_verses": ["Psalm 46:1", "Psalm 46:10"]
        },
        {
            "psalm_number": 91,
            "themes": ["protection", "safety", "trust"],
            "emotional_context": "Danger, fear, need for protection",
            "key_verses": ["Psalm 91:1-2", "Psalm 91:11"]
        }
    ]


@pytest.fixture
def sample_llm_response():
    """Sample LLM response text."""
    return """PSALMS: 23, 46
VERSES: Psalm 23:4 - "Even though I walk through the darkest valley, I will fear no evil, for you are with me"
Psalm 46:1 - "God is our refuge and strength, an ever-present help in trouble"
GUIDANCE: I hear that you're feeling anxious and overwhelmed. These feelings are completely valid, and you're not alone in experiencing them. Psalm 23 offers beautiful imagery of God as a shepherd who guides and comforts us through difficult times. Psalm 46 reminds us that even in the midst of trouble, we can find refuge and strength. Take a moment to breathe deeply and remember that you don't have to face these challenges alone."""


class TestLLMServiceInitialization:
    """Test LLM service initialization."""
    
    def test_initialization_with_defaults(self):
        """Test that service initializes with default configuration."""
        service = LLMService()
        assert service.model_id is not None
        assert service.max_retries == 3
        assert service.temperature == 0.7
        assert service.max_tokens == 1000
    
    def test_initialization_with_custom_params(self, mock_bedrock_client):
        """Test that service initializes with custom parameters."""
        service = LLMService(
            bedrock_client=mock_bedrock_client,
            model_id="custom-model",
            max_retries=5,
            temperature=0.5,
            max_tokens=500
        )
        assert service.model_id == "custom-model"
        assert service.max_retries == 5
        assert service.temperature == 0.5
        assert service.max_tokens == 500


class TestGenerateRecommendation:
    """Test LLM recommendation generation."""
    
    def test_successful_generation(
        self,
        llm_service,
        mock_bedrock_client,
        sample_emotional_input,
        sample_retrieved_psalms,
        sample_llm_response
    ):
        """
        Test successful LLM recommendation generation.
        
        **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
        """
        # Mock successful Bedrock response
        mock_response = {
            "body": MagicMock()
        }
        mock_response["body"].read.return_value = json.dumps({
            "content": [{"text": sample_llm_response}]
        }).encode()
        mock_bedrock_client.invoke_model.return_value = mock_response
        
        # Generate recommendation
        recommendation = llm_service.generate_recommendation(
            emotional_input=sample_emotional_input,
            retrieved_psalms=sample_retrieved_psalms,
            request_id="test-123"
        )
        
        # Verify the recommendation structure
        assert isinstance(recommendation, PsalmRecommendation)
        assert len(recommendation.psalm_numbers) > 0
        assert 23 in recommendation.psalm_numbers
        assert 46 in recommendation.psalm_numbers
        assert len(recommendation.verses) > 0
        assert recommendation.guidance
        assert "anxious" in recommendation.guidance.lower() or "overwhelmed" in recommendation.guidance.lower()
        
        # Verify Bedrock was called
        mock_bedrock_client.invoke_model.assert_called_once()
        call_args = mock_bedrock_client.invoke_model.call_args
        assert call_args[1]["modelId"] == llm_service.model_id
        
        # Verify prompt includes emotional input (Requirement 4.4)
        request_body = json.loads(call_args[1]["body"])
        # Extract the actual prompt content from the messages
        if "messages" in request_body:
            prompt_text = request_body["messages"][0]["content"]
        else:
            prompt_text = request_body.get("prompt", "")
        assert sample_emotional_input in prompt_text
    
    def test_empty_emotional_input_raises_error(
        self,
        llm_service,
        sample_retrieved_psalms
    ):
        """Test that empty emotional input raises ValueError."""
        with pytest.raises(ValueError, match="Emotional input cannot be empty"):
            llm_service.generate_recommendation(
                emotional_input="",
                retrieved_psalms=sample_retrieved_psalms
            )
    
    def test_empty_retrieved_psalms_raises_error(
        self,
        llm_service,
        sample_emotional_input
    ):
        """Test that empty retrieved psalms raises ValueError."""
        with pytest.raises(ValueError, match="Retrieved psalms list cannot be empty"):
            llm_service.generate_recommendation(
                emotional_input=sample_emotional_input,
                retrieved_psalms=[]
            )
    
    def test_retry_on_throttling(
        self,
        llm_service,
        mock_bedrock_client,
        sample_emotional_input,
        sample_retrieved_psalms,
        sample_llm_response
    ):
        """Test that service retries on throttling errors."""
        # Mock throttling error followed by success
        throttling_error = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "invoke_model"
        )
        
        mock_success_response = {
            "body": MagicMock()
        }
        mock_success_response["body"].read.return_value = json.dumps({
            "content": [{"text": sample_llm_response}]
        }).encode()
        
        mock_bedrock_client.invoke_model.side_effect = [
            throttling_error,
            mock_success_response
        ]
        
        # Should succeed after retry
        with patch("time.sleep"):  # Mock sleep to speed up test
            recommendation = llm_service.generate_recommendation(
                emotional_input=sample_emotional_input,
                retrieved_psalms=sample_retrieved_psalms
            )
        
        assert isinstance(recommendation, PsalmRecommendation)
        assert mock_bedrock_client.invoke_model.call_count == 2
    
    def test_max_retries_exhausted(
        self,
        llm_service,
        mock_bedrock_client,
        sample_emotional_input,
        sample_retrieved_psalms
    ):
        """
        Test that service raises error after max retries.
        
        **Validates: Requirement 8.3**
        """
        # Mock persistent throttling error
        throttling_error = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "invoke_model"
        )
        mock_bedrock_client.invoke_model.side_effect = throttling_error
        
        # Should raise LLMGenerationFailedError after retries
        with patch("time.sleep"):  # Mock sleep to speed up test
            with pytest.raises(LLMGenerationFailedError):
                llm_service.generate_recommendation(
                    emotional_input=sample_emotional_input,
                    retrieved_psalms=sample_retrieved_psalms
                )
        
        # Verify retries occurred
        assert mock_bedrock_client.invoke_model.call_count == llm_service.max_retries


class TestPromptBuilding:
    """Test prompt building functionality."""
    
    def test_prompt_includes_emotional_input(
        self,
        llm_service,
        sample_emotional_input,
        sample_retrieved_psalms
    ):
        """
        Test that prompt includes user's emotional input.
        
        **Validates: Requirement 4.4**
        """
        prompt = llm_service._build_prompt(sample_emotional_input, sample_retrieved_psalms)
        assert sample_emotional_input in prompt
    
    def test_prompt_includes_psalm_context(
        self,
        llm_service,
        sample_emotional_input,
        sample_retrieved_psalms
    ):
        """
        Test that prompt includes retrieved psalm context.
        
        **Validates: Requirement 4.1**
        """
        prompt = llm_service._build_prompt(sample_emotional_input, sample_retrieved_psalms)
        
        # Check that psalm numbers are included
        assert "23" in prompt
        assert "46" in prompt
        assert "91" in prompt
        
        # Check that themes are included
        assert "comfort" in prompt.lower() or "guidance" in prompt.lower()
    
    def test_prompt_requests_empathetic_tone(
        self,
        llm_service,
        sample_emotional_input,
        sample_retrieved_psalms
    ):
        """
        Test that prompt requests empathetic and supportive tone.
        
        **Validates: Requirement 4.3**
        """
        prompt = llm_service._build_prompt(sample_emotional_input, sample_retrieved_psalms)
        
        # Check for empathy-related keywords
        assert any(word in prompt.lower() for word in [
            "compassion", "empathetic", "warm", "supportive", "comfort"
        ])
    
    def test_prompt_requests_structured_output(
        self,
        llm_service,
        sample_emotional_input,
        sample_retrieved_psalms
    ):
        """
        Test that prompt requests structured output format.
        
        **Validates: Requirement 4.2**
        """
        prompt = llm_service._build_prompt(sample_emotional_input, sample_retrieved_psalms)
        
        # Check for output format instructions
        assert "PSALMS:" in prompt
        assert "VERSES:" in prompt
        assert "GUIDANCE:" in prompt


class TestResponseParsing:
    """Test LLM response parsing."""
    
    def test_parse_valid_response(self, llm_service, sample_llm_response):
        """
        Test parsing a valid LLM response.
        
        **Validates: Requirement 4.2**
        """
        recommendation = llm_service._parse_recommendation(sample_llm_response)
        
        assert isinstance(recommendation, PsalmRecommendation)
        assert 23 in recommendation.psalm_numbers
        assert 46 in recommendation.psalm_numbers
        assert len(recommendation.verses) > 0
        assert recommendation.guidance
        assert len(recommendation.guidance) > 0
    
    def test_parse_response_without_psalm_numbers(self, llm_service):
        """Test that parsing fails when psalm numbers are missing."""
        invalid_response = """VERSES: Some verse
GUIDANCE: Some guidance"""
        
        with pytest.raises(ValueError, match="Could not extract psalm numbers"):
            llm_service._parse_recommendation(invalid_response)
    
    def test_parse_response_without_guidance(self, llm_service):
        """Test that parsing fails when guidance is missing."""
        invalid_response = """PSALMS: 23, 46
VERSES: Some verse"""
        
        with pytest.raises(ValueError, match="Could not extract guidance"):
            llm_service._parse_recommendation(invalid_response)
    
    def test_extract_psalm_numbers(self, llm_service):
        """Test extraction of psalm numbers from text."""
        text = "23, 46, 91"
        numbers = llm_service._extract_psalm_numbers(text)
        assert numbers == [23, 46, 91]
    
    def test_extract_psalm_numbers_filters_invalid(self, llm_service):
        """Test that invalid psalm numbers are filtered out."""
        text = "0, 23, 151, 46, 200"
        numbers = llm_service._extract_psalm_numbers(text)
        assert numbers == [23, 46]  # Only valid psalm numbers (1-150)


class TestFallbackResponse:
    """Test fallback response generation."""
    
    def test_generate_fallback_response(
        self,
        llm_service,
        sample_retrieved_psalms
    ):
        """
        Test fallback response when LLM fails.
        
        **Validates: Requirement 8.3**
        """
        fallback = llm_service.generate_fallback_response(sample_retrieved_psalms)
        
        assert "psalms" in fallback
        assert "message" in fallback
        assert len(fallback["psalms"]) <= 3  # Should limit to top 3
        
        # Verify psalm information is included
        for psalm in fallback["psalms"]:
            assert "psalm_number" in psalm
            assert "themes" in psalm
            assert "key_verses" in psalm
    
    def test_fallback_limits_to_three_psalms(
        self,
        llm_service,
        sample_retrieved_psalms
    ):
        """Test that fallback response limits to 3 psalms."""
        # Add more psalms
        extended_psalms = sample_retrieved_psalms + [
            {"psalm_number": 121, "themes": ["help"], "key_verses": []},
            {"psalm_number": 139, "themes": ["presence"], "key_verses": []}
        ]
        
        fallback = llm_service.generate_fallback_response(extended_psalms)
        assert len(fallback["psalms"]) == 3


class TestErrorHandling:
    """Test error handling and logging."""
    
    @patch("src.shared.llm_service.log_metric")
    @patch("src.shared.llm_service.log_error")
    def test_failure_logging(
        self,
        mock_log_error,
        mock_log_metric,
        llm_service,
        mock_bedrock_client,
        sample_emotional_input,
        sample_retrieved_psalms
    ):
        """
        Test that failures are logged with context.
        
        **Validates: Requirements 8.4, 10.4**
        """
        # Mock a non-retryable error
        error = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Invalid input"}},
            "invoke_model"
        )
        mock_bedrock_client.invoke_model.side_effect = error
        
        # Should raise error and log
        with pytest.raises(LLMGenerationFailedError):
            llm_service.generate_recommendation(
                emotional_input=sample_emotional_input,
                retrieved_psalms=sample_retrieved_psalms,
                request_id="test-123"
            )
        
        # Verify error was logged
        mock_log_error.assert_called_once()
        call_args = mock_log_error.call_args
        assert call_args[1]["request_id"] == "test-123"
        assert "llm_service" in call_args[1]["context"]["service"]
        
        # Verify failure metric was logged
        mock_log_metric.assert_called()
        metric_calls = [call for call in mock_log_metric.call_args_list 
                       if call[1]["metric_name"] == "llm_invocation_failed"]
        assert len(metric_calls) > 0
    
    @patch("src.shared.llm_service.log_metric")
    def test_success_metrics(
        self,
        mock_log_metric,
        llm_service,
        mock_bedrock_client,
        sample_emotional_input,
        sample_retrieved_psalms,
        sample_llm_response
    ):
        """
        Test that success metrics are tracked.
        
        **Validates: Requirement 10.4**
        """
        # Mock successful response
        mock_response = {
            "body": MagicMock()
        }
        mock_response["body"].read.return_value = json.dumps({
            "content": [{"text": sample_llm_response}]
        }).encode()
        mock_bedrock_client.invoke_model.return_value = mock_response
        
        # Generate recommendation
        llm_service.generate_recommendation(
            emotional_input=sample_emotional_input,
            retrieved_psalms=sample_retrieved_psalms,
            request_id="test-123"
        )
        
        # Verify success metric was logged
        mock_log_metric.assert_called()
        metric_calls = [call for call in mock_log_metric.call_args_list 
                       if call[1]["metric_name"] == "llm_invocation_success"]
        assert len(metric_calls) > 0
        
        # Verify metric includes request_id
        success_call = metric_calls[0]
        assert success_call[1]["metadata"]["request_id"] == "test-123"


class TestPsalmRecommendation:
    """Test PsalmRecommendation data class."""
    
    def test_to_dict(self):
        """Test conversion to dictionary format."""
        recommendation = PsalmRecommendation(
            psalm_numbers=[23, 46],
            verses=["Psalm 23:1", "Psalm 46:1"],
            guidance="Test guidance",
            raw_response="Raw response"
        )
        
        result = recommendation.to_dict()
        assert result["psalm_numbers"] == [23, 46]
        assert result["verses"] == ["Psalm 23:1", "Psalm 46:1"]
        assert result["guidance"] == "Test guidance"
        assert "raw_response" not in result  # Should not include raw response
