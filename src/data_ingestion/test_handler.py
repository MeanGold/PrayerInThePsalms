"""
Unit tests for the data ingestion Lambda handler.

Tests the psalm data ingestion pipeline including validation, metadata extraction,
and embedding generation.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.data_ingestion.handler import (
    lambda_handler,
    extract_operation_type,
    extract_psalm_data,
    validate_psalm_structure,
    extract_psalm_metadata,
    prepare_embedding_text,
    process_psalm,
    ValidationError
)


class TestLambdaHandler:
    """Tests for the main Lambda handler function."""
    
    @patch("src.data_ingestion.handler.EmbeddingService")
    @patch("src.data_ingestion.handler.config")
    def test_successful_ingestion(self, mock_config, mock_embedding_service_class):
        """Test successful ingestion of psalm data."""
        # Setup
        mock_config.validate.return_value = None
        mock_embedding_service = Mock()
        mock_embedding_service.generate_embedding.return_value = [0.1] * 1536
        mock_embedding_service_class.return_value = mock_embedding_service
        
        event = {
            "psalms": [
                {
                    "psalm_id": "Psalm 23",
                    "content": "The Lord is my shepherd; I shall not want.",
                    "themes": ["comfort", "guidance"],
                    "emotional_context": "peace, reassurance",
                    "historical_usage": "Funerals, comfort",
                    "key_verses": ["verse 1", "verse 4"]
                }
            ]
        }
        
        # Execute
        response = lambda_handler(event, None)
        
        # Verify
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "success"
        assert body["processed_count"] == 1
        assert body["failed_count"] == 0
        assert body["operation_type"] == "insert"
        assert "request_id" in body
    
    @patch("src.data_ingestion.handler.EmbeddingService")
    @patch("src.data_ingestion.handler.config")
    def test_successful_update_operation(self, mock_config, mock_embedding_service_class):
        """Test successful update operation for psalm data."""
        # Setup
        mock_config.validate.return_value = None
        mock_embedding_service = Mock()
        mock_embedding_service.generate_embedding.return_value = [0.1] * 1536
        mock_embedding_service_class.return_value = mock_embedding_service
        
        event = {
            "operation_type": "update",
            "psalms": [
                {
                    "psalm_id": "Psalm 23",
                    "content": "The Lord is my shepherd; I shall not want.",
                    "themes": ["comfort", "guidance", "trust"],
                    "emotional_context": "peace, reassurance, safety"
                }
            ]
        }
        
        # Execute
        response = lambda_handler(event, None)
        
        # Verify
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "success"
        assert body["operation_type"] == "update"
        assert body["processed_count"] == 1
        assert body["failed_count"] == 0
    
    @patch("src.data_ingestion.handler.EmbeddingService")
    @patch("src.data_ingestion.handler.config")
    def test_batch_processing_with_partial_failures(self, mock_config, mock_embedding_service_class):
        """Test batch processing continues even when individual psalms fail."""
        # Setup
        mock_config.validate.return_value = None
        mock_embedding_service = Mock()
        
        # First psalm succeeds, second fails, third succeeds
        mock_embedding_service.generate_embedding.side_effect = [
            [0.1] * 1536,  # Success
            Exception("Embedding generation failed"),  # Failure
            [0.2] * 1536   # Success
        ]
        mock_embedding_service_class.return_value = mock_embedding_service
        
        event = {
            "psalms": [
                {
                    "psalm_id": "Psalm 1",
                    "content": "Blessed is the one..."
                },
                {
                    "psalm_id": "Psalm 2",
                    "content": "Why do the nations conspire..."
                },
                {
                    "psalm_id": "Psalm 3",
                    "content": "Lord, how many are my foes..."
                }
            ]
        }
        
        # Execute
        response = lambda_handler(event, None)
        
        # Verify
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "success"
        assert body["processed_count"] == 2
        assert body["failed_count"] == 1
        assert len(body["failed_psalms"]) == 1
        assert body["failed_psalms"][0]["psalm_id"] == "Psalm 2"
    
    @patch("src.data_ingestion.handler.config")
    def test_empty_psalms_array(self, mock_config):
        """Test error handling for empty psalms array."""
        mock_config.validate.return_value = None
        
        event = {"psalms": []}
        
        response = lambda_handler(event, None)
        
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
        assert body["status"] == "error"
    
    @patch("src.data_ingestion.handler.config")
    def test_missing_psalms_field(self, mock_config):
        """Test error handling when psalms field is missing."""
        mock_config.validate.return_value = None
        
        event = {"body": json.dumps({})}
        
        response = lambda_handler(event, None)
        
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
    
    @patch("src.data_ingestion.handler.config")
    def test_invalid_operation_type(self, mock_config):
        """Test error handling for invalid operation type."""
        mock_config.validate.return_value = None
        
        event = {
            "operation_type": "delete",
            "psalms": [
                {
                    "psalm_id": "Psalm 1",
                    "content": "Blessed is the one..."
                }
            ]
        }
        
        response = lambda_handler(event, None)
        
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
        assert "Invalid operation_type" in body["error"]


class TestExtractOperationType:
    """Tests for operation type extraction."""
    
    def test_extract_insert_operation(self):
        """Test extracting insert operation type."""
        event = {"operation_type": "insert"}
        
        operation_type = extract_operation_type(event, "test-request-id")
        
        assert operation_type == "insert"
    
    def test_extract_update_operation(self):
        """Test extracting update operation type."""
        event = {"operation_type": "update"}
        
        operation_type = extract_operation_type(event, "test-request-id")
        
        assert operation_type == "update"
    
    def test_default_to_insert(self):
        """Test defaulting to insert when operation_type is not provided."""
        event = {"psalms": []}
        
        operation_type = extract_operation_type(event, "test-request-id")
        
        assert operation_type == "insert"
    
    def test_extract_from_api_gateway_body(self):
        """Test extracting operation type from API Gateway body."""
        event = {
            "body": json.dumps({
                "operation_type": "update",
                "psalms": []
            })
        }
        
        operation_type = extract_operation_type(event, "test-request-id")
        
        assert operation_type == "update"
    
    def test_invalid_operation_type(self):
        """Test error handling for invalid operation type."""
        event = {"operation_type": "delete"}
        
        with pytest.raises(ValidationError, match="Invalid operation_type"):
            extract_operation_type(event, "test-request-id")


class TestExtractPsalmData:
    """Tests for psalm data extraction and validation."""
    
    def test_extract_from_direct_event(self):
        """Test extracting psalms from direct Lambda invocation."""
        event = {
            "psalms": [
                {
                    "psalm_id": "Psalm 1",
                    "content": "Blessed is the one..."
                }
            ]
        }
        
        psalms = extract_psalm_data(event, "test-request-id")
        
        assert len(psalms) == 1
        assert psalms[0]["psalm_id"] == "Psalm 1"
    
    def test_extract_from_api_gateway_event(self):
        """Test extracting psalms from API Gateway event."""
        event = {
            "body": json.dumps({
                "psalms": [
                    {
                        "psalm_id": "Psalm 2",
                        "content": "Why do the nations conspire..."
                    }
                ]
            })
        }
        
        psalms = extract_psalm_data(event, "test-request-id")
        
        assert len(psalms) == 1
        assert psalms[0]["psalm_id"] == "Psalm 2"
    
    def test_invalid_json(self):
        """Test error handling for invalid JSON."""
        event = {"body": "invalid json"}
        
        with pytest.raises(ValidationError, match="Invalid JSON"):
            extract_psalm_data(event, "test-request-id")


class TestValidatePsalmStructure:
    """Tests for psalm structure validation."""
    
    def test_valid_psalm(self):
        """Test validation of a valid psalm."""
        psalm = {
            "psalm_id": "Psalm 23",
            "content": "The Lord is my shepherd"
        }
        
        # Should not raise
        validate_psalm_structure(psalm, 0)
    
    def test_missing_psalm_id(self):
        """Test validation fails when psalm_id is missing."""
        psalm = {"content": "Some content"}
        
        with pytest.raises(ValidationError, match="missing required field: psalm_id"):
            validate_psalm_structure(psalm, 0)
    
    def test_missing_content(self):
        """Test validation fails when content is missing."""
        psalm = {"psalm_id": "Psalm 1"}
        
        with pytest.raises(ValidationError, match="missing required field: content"):
            validate_psalm_structure(psalm, 0)
    
    def test_empty_content(self):
        """Test validation fails when content is empty."""
        psalm = {"psalm_id": "Psalm 1", "content": ""}
        
        with pytest.raises(ValidationError, match="missing required field: content"):
            validate_psalm_structure(psalm, 0)


class TestExtractPsalmMetadata:
    """Tests for psalm metadata extraction."""
    
    def test_extract_all_metadata(self):
        """Test extracting all metadata fields."""
        psalm = {
            "psalm_id": "Psalm 23",
            "content": "The Lord is my shepherd",
            "themes": ["comfort", "guidance"],
            "emotional_context": "peace",
            "historical_usage": "funerals",
            "key_verses": ["verse 1", "verse 4"]
        }
        
        metadata = extract_psalm_metadata(psalm)
        
        assert metadata["psalm_id"] == "Psalm 23"
        assert metadata["themes"] == ["comfort", "guidance"]
        assert metadata["emotional_context"] == "peace"
        assert metadata["historical_usage"] == "funerals"
        assert metadata["key_verses"] == ["verse 1", "verse 4"]
    
    def test_extract_with_missing_optional_fields(self):
        """Test extracting metadata when optional fields are missing."""
        psalm = {
            "psalm_id": "Psalm 1",
            "content": "Blessed is the one"
        }
        
        metadata = extract_psalm_metadata(psalm)
        
        assert metadata["psalm_id"] == "Psalm 1"
        assert metadata["themes"] == []
        assert metadata["emotional_context"] == ""
        assert metadata["historical_usage"] == ""
        assert metadata["key_verses"] == []
    
    def test_convert_string_themes_to_list(self):
        """Test converting comma-separated themes string to list."""
        psalm = {
            "psalm_id": "Psalm 1",
            "content": "Blessed",
            "themes": "comfort, guidance, trust"
        }
        
        metadata = extract_psalm_metadata(psalm)
        
        assert metadata["themes"] == ["comfort", "guidance", "trust"]


class TestPrepareEmbeddingText:
    """Tests for embedding text preparation."""
    
    def test_prepare_with_all_metadata(self):
        """Test preparing embedding text with all metadata."""
        psalm = {"content": "The Lord is my shepherd"}
        metadata = {
            "themes": ["comfort", "guidance"],
            "emotional_context": "peace, reassurance"
        }
        
        text = prepare_embedding_text(psalm, metadata)
        
        assert "The Lord is my shepherd" in text
        assert "Themes: comfort, guidance" in text
        assert "Emotional context: peace, reassurance" in text
    
    def test_prepare_with_minimal_metadata(self):
        """Test preparing embedding text with minimal metadata."""
        psalm = {"content": "Blessed is the one"}
        metadata = {
            "themes": [],
            "emotional_context": ""
        }
        
        text = prepare_embedding_text(psalm, metadata)
        
        assert text == "Blessed is the one"


class TestProcessPsalm:
    """Tests for individual psalm processing."""
    
    @patch("src.data_ingestion.handler.EmbeddingService")
    def test_process_psalm_success(self, mock_embedding_service_class):
        """Test successful processing of a psalm."""
        # Setup
        mock_embedding_service = Mock()
        mock_embedding_service.generate_embedding.return_value = [0.1] * 1536
        
        psalm = {
            "psalm_id": "Psalm 23",
            "content": "The Lord is my shepherd",
            "themes": ["comfort"],
            "emotional_context": "peace"
        }
        
        # Execute
        result = process_psalm(psalm, mock_embedding_service, "test-request-id")
        
        # Verify
        assert result["psalm_id"] == "Psalm 23"
        assert result["content"] == "The Lord is my shepherd"
        assert result["operation_type"] == "insert"
        assert "metadata" in result
        assert "embedding" in result
        assert result["embedding_dimension"] == 1536
        assert mock_embedding_service.generate_embedding.called
    
    @patch("src.data_ingestion.handler.EmbeddingService")
    def test_process_psalm_update_operation(self, mock_embedding_service_class):
        """Test processing a psalm with update operation."""
        # Setup
        mock_embedding_service = Mock()
        mock_embedding_service.generate_embedding.return_value = [0.2] * 1536
        
        psalm = {
            "psalm_id": "Psalm 23",
            "content": "The Lord is my shepherd; I shall not want.",
            "themes": ["comfort", "guidance", "trust"],
            "emotional_context": "peace, reassurance"
        }
        
        # Execute
        result = process_psalm(
            psalm,
            mock_embedding_service,
            "test-request-id",
            operation_type="update"
        )
        
        # Verify
        assert result["psalm_id"] == "Psalm 23"
        assert result["operation_type"] == "update"
        assert "embedding" in result
        assert result["embedding_dimension"] == 1536
        # Verify embedding was regenerated
        assert mock_embedding_service.generate_embedding.called
