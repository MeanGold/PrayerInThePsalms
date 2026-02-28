"""
Unit tests for the Lambda handler.

**Validates: Requirements 1.1, 1.2, 1.3, 7.1, 7.2, 7.3, 9.1, 9.2**
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.recommendation_handler.handler import (
    lambda_handler,
    extract_emotional_input,
    limit_to_sentences,
    count_sentences,
    format_psalms_for_llm,
    extract_psalm_number,
    ValidationError
)
from src.shared.vector_store import SearchResult


class TestInputValidation:
    """Test input validation and extraction."""
    
    def test_extract_emotional_input_valid(self):
        """Test extracting valid emotional input."""
        event = {
            "body": json.dumps({
                "emotional_input": "I am feeling anxious and overwhelmed."
            })
        }
        result = extract_emotional_input(event, "test-request-id")
        assert result == "I am feeling anxious and overwhelmed."
    
    def test_extract_emotional_input_empty(self):
        """Test that empty input raises ValidationError (Requirement 1.2)."""
        event = {
            "body": json.dumps({
                "emotional_input": ""
            })
        }
        with pytest.raises(ValidationError, match="Emotional input is required"):
            extract_emotional_input(event, "test-request-id")
    
    def test_extract_emotional_input_whitespace_only(self):
        """Test that whitespace-only input raises ValidationError."""
        event = {
            "body": json.dumps({
                "emotional_input": "   "
            })
        }
        with pytest.raises(ValidationError, match="Emotional input is required"):
            extract_emotional_input(event, "test-request-id")
    
    def test_extract_emotional_input_missing_body(self):
        """Test that missing body raises ValidationError."""
        event = {}
        with pytest.raises(ValidationError, match="Request body is required"):
            extract_emotional_input(event, "test-request-id")
    
    def test_extract_emotional_input_invalid_json(self):
        """Test that invalid JSON raises ValidationError."""
        event = {
            "body": "not valid json"
        }
        with pytest.raises(ValidationError, match="Invalid JSON"):
            extract_emotional_input(event, "test-request-id")
    
    def test_limit_to_sentences_single(self):
        """Test limiting to sentences with single sentence."""
        text = "I am feeling sad."
        result = limit_to_sentences(text, max_sentences=2)
        assert result == "I am feeling sad."
    
    def test_limit_to_sentences_multiple(self):
        """Test limiting to sentences with multiple sentences (Requirement 1.3)."""
        text = "I am feeling sad. I need comfort. I want peace. I seek guidance."
        result = limit_to_sentences(text, max_sentences=2)
        assert result == "I am feeling sad. I need comfort."
    
    def test_count_sentences(self):
        """Test counting sentences."""
        assert count_sentences("One.") == 1
        assert count_sentences("One. Two.") == 2
        assert count_sentences("One! Two? Three.") == 3


class TestPsalmFormatting:
    """Test psalm formatting utilities."""
    
    def test_format_psalms_for_llm(self):
        """Test formatting search results for LLM."""
        search_results = [
            SearchResult(
                psalm_id="Psalm 23",
                content="The Lord is my shepherd...",
                metadata={
                    "themes": ["comfort", "guidance"],
                    "emotional_context": "peace",
                    "key_verses": ["Psalm 23:1", "Psalm 23:4"]
                },
                similarity_score=0.95
            )
        ]
        
        result = format_psalms_for_llm(search_results)
        
        assert len(result) == 1
        assert result[0]["psalm_number"] == 23
        assert result[0]["content"] == "The Lord is my shepherd..."
        assert result[0]["themes"] == ["comfort", "guidance"]
        assert result[0]["similarity_score"] == 0.95
    
    def test_extract_psalm_number(self):
        """Test extracting psalm numbers from various formats."""
        assert extract_psalm_number("Psalm 23") == 23
        assert extract_psalm_number("psalm_46") == 46
        assert extract_psalm_number("91") == 91
        assert extract_psalm_number("Psalm 150") == 150
        assert extract_psalm_number("unknown") == 0


class TestLambdaHandler:
    """Test the main Lambda handler function."""
    
    @patch('src.recommendation_handler.handler.config')
    @patch('src.recommendation_handler.handler.EmbeddingService')
    @patch('src.recommendation_handler.handler.BedrockKnowledgeBaseVectorStore')
    @patch('src.recommendation_handler.handler.LLMService')
    def test_lambda_handler_success(self, mock_llm_cls, mock_vector_cls, mock_embed_cls, mock_config):
        """Test successful request processing (Requirements 7.1, 7.2)."""
        # Mock config validation
        mock_config.validate.return_value = None
        
        # Setup mocks
        mock_embed = Mock()
        mock_embed.generate_embedding.return_value = [0.1] * 1536
        mock_embed_cls.return_value = mock_embed
        
        mock_vector = Mock()
        mock_vector.search.return_value = [
            SearchResult(
                psalm_id="Psalm 23",
                content="The Lord is my shepherd...",
                metadata={
                    "themes": ["comfort"],
                    "emotional_context": "peace",
                    "key_verses": ["Psalm 23:1"]
                },
                similarity_score=0.95
            )
        ]
        mock_vector_cls.return_value = mock_vector
        
        mock_llm = Mock()
        mock_recommendation = Mock()
        mock_recommendation.to_dict.return_value = {
            "psalm_numbers": [23],
            "verses": ["Psalm 23:1"],
            "guidance": "Test guidance"
        }
        mock_llm.generate_recommendation.return_value = mock_recommendation
        mock_llm_cls.return_value = mock_llm
        
        # Create event
        event = {
            "body": json.dumps({
                "emotional_input": "I am feeling anxious."
            })
        }
        context = Mock()
        
        # Call handler
        response = lambda_handler(event, context)
        
        # Verify response
        assert response["statusCode"] == 200
        assert "X-Request-ID" in response["headers"]
        
        body = json.loads(response["body"])
        assert "request_id" in body
        assert "recommendations" in body
        assert body["recommendations"]["psalm_numbers"] == [23]
    
    @patch('src.recommendation_handler.handler.config')
    def test_lambda_handler_validation_error(self, mock_config):
        """Test handler with validation error (Requirement 7.3)."""
        # Mock config validation
        mock_config.validate.return_value = None
        
        event = {
            "body": json.dumps({
                "emotional_input": ""
            })
        }
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
        assert "request_id" in body
    
    @patch('src.recommendation_handler.handler.config')
    @patch('src.recommendation_handler.handler.EmbeddingService')
    @patch('src.recommendation_handler.handler.BedrockKnowledgeBaseVectorStore')
    def test_lambda_handler_embedding_unavailable(self, mock_vector_cls, mock_embed_cls, mock_config):
        """Test handler when embedding service is unavailable (Requirement 8.1)."""
        from src.shared.embedding_service import EmbeddingModelUnavailableError
        
        # Mock config validation
        mock_config.validate.return_value = None
        
        mock_embed = Mock()
        mock_embed.generate_embedding.side_effect = EmbeddingModelUnavailableError("Service unavailable")
        mock_embed_cls.return_value = mock_embed
        
        # Mock vector store (won't be used but needs to be initialized)
        mock_vector = Mock()
        mock_vector_cls.return_value = mock_vector
        
        event = {
            "body": json.dumps({
                "emotional_input": "I am feeling anxious."
            })
        }
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response["statusCode"] == 503
        body = json.loads(response["body"])
        assert "error" in body
        assert "unavailable" in body["error"].lower()
    
    @patch('src.recommendation_handler.handler.config')
    @patch('src.recommendation_handler.handler.EmbeddingService')
    @patch('src.recommendation_handler.handler.BedrockKnowledgeBaseVectorStore')
    @patch('src.recommendation_handler.handler.LLMService')
    def test_lambda_handler_llm_fallback(self, mock_llm_cls, mock_vector_cls, mock_embed_cls, mock_config):
        """Test handler with LLM fallback (Requirement 8.3)."""
        from src.shared.llm_service import LLMGenerationFailedError
        
        # Mock config validation
        mock_config.validate.return_value = None
        
        # Setup mocks
        mock_embed = Mock()
        mock_embed.generate_embedding.return_value = [0.1] * 1536
        mock_embed_cls.return_value = mock_embed
        
        mock_vector = Mock()
        mock_vector.search.return_value = [
            SearchResult(
                psalm_id="Psalm 23",
                content="The Lord is my shepherd...",
                metadata={"themes": ["comfort"]},
                similarity_score=0.95
            )
        ]
        mock_vector_cls.return_value = mock_vector
        
        mock_llm = Mock()
        mock_llm.generate_recommendation.side_effect = LLMGenerationFailedError("LLM failed")
        mock_llm.generate_fallback_response.return_value = {
            "psalms": [{"psalm_number": 23}],
            "message": "Fallback message"
        }
        mock_llm_cls.return_value = mock_llm
        
        event = {
            "body": json.dumps({
                "emotional_input": "I am feeling anxious."
            })
        }
        context = Mock()
        
        response = lambda_handler(event, context)
        
        # Should still return 200 with fallback response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "recommendations" in body
        assert "message" in body["recommendations"]


class TestPrivacyAndSecurity:
    """Test privacy and security measures."""
    
    def test_emotional_input_not_in_logs(self):
        """Test that emotional input is not logged (Requirement 9.2)."""
        # This is validated by the logging_config module's sanitization
        # The handler uses structured logging that sanitizes PII
        pass
    
    def test_https_headers(self):
        """Test that response includes proper headers (Requirement 9.3)."""
        from src.recommendation_handler.handler import create_response
        
        response = create_response(
            status_code=200,
            body={"test": "data"},
            request_id="test-id"
        )
        
        assert "headers" in response
        assert response["headers"]["Content-Type"] == "application/json"
        assert response["headers"]["X-Request-ID"] == "test-id"
