"""
Unit tests for vector store interface and Bedrock Knowledge Base implementation.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 6.1, 6.3, 8.2**
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from botocore.exceptions import ClientError

from .vector_store import (
    VectorStore,
    BedrockKnowledgeBaseVectorStore,
    SearchResult,
    VectorStoreError,
    VectorStoreUnavailableError
)


class TestSearchResult(unittest.TestCase):
    """Test cases for SearchResult dataclass."""
    
    def test_search_result_creation(self):
        """Test creating a SearchResult instance."""
        result = SearchResult(
            psalm_id="Psalm 23",
            content="The Lord is my shepherd",
            metadata={"themes": ["comfort"]},
            similarity_score=0.95
        )
        
        self.assertEqual(result.psalm_id, "Psalm 23")
        self.assertEqual(result.content, "The Lord is my shepherd")
        self.assertEqual(result.metadata, {"themes": ["comfort"]})
        self.assertEqual(result.similarity_score, 0.95)
    
    def test_search_result_repr(self):
        """Test SearchResult string representation."""
        result = SearchResult(
            psalm_id="Psalm 23",
            content="Test",
            metadata={},
            similarity_score=0.856
        )
        
        repr_str = repr(result)
        self.assertIn("Psalm 23", repr_str)
        self.assertIn("0.856", repr_str)


class TestBedrockKnowledgeBaseVectorStore(unittest.TestCase):
    """Test cases for BedrockKnowledgeBaseVectorStore implementation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = MagicMock()
        self.knowledge_base_id = "test-kb-123"
        self.vector_store = BedrockKnowledgeBaseVectorStore(
            knowledge_base_id=self.knowledge_base_id,
            bedrock_agent_client=self.mock_client,
            max_retries=3,
            backoff_base=2.0
        )
    
    def test_initialization(self):
        """Test vector store initialization."""
        self.assertEqual(self.vector_store.knowledge_base_id, self.knowledge_base_id)
        self.assertEqual(self.vector_store.max_retries, 3)
        self.assertEqual(self.vector_store.backoff_base, 2.0)
    
    def test_initialization_without_kb_id(self):
        """Test initialization fails without Knowledge Base ID."""
        with self.assertRaises(ValueError):
            BedrockKnowledgeBaseVectorStore(
                knowledge_base_id="",
                bedrock_agent_client=self.mock_client
            )
    
    def test_search_success(self):
        """
        Test successful vector search with results.
        
        **Validates: Requirements 3.1, 3.2, 3.3, 6.3**
        """
        # Mock successful response
        self.mock_client.retrieve.return_value = {
            "retrievalResults": [
                {
                    "score": 0.95,
                    "content": {"text": "The Lord is my shepherd"},
                    "metadata": {
                        "psalm_id": "Psalm 23",
                        "themes": ["comfort", "guidance"]
                    }
                },
                {
                    "score": 0.88,
                    "content": {"text": "God is our refuge"},
                    "metadata": {
                        "psalm_id": "Psalm 46",
                        "themes": ["strength", "refuge"]
                    }
                },
                {
                    "score": 0.82,
                    "content": {"text": "He who dwells in the shelter"},
                    "metadata": {
                        "psalm_id": "Psalm 91",
                        "themes": ["protection"]
                    }
                }
            ]
        }
        
        query_embedding = [0.1] * 1536
        results = self.vector_store.search(
            query_embedding=query_embedding,
            max_results=5,
            min_results=3,
            similarity_threshold=0.7,
            request_id="test-123"
        )
        
        # Verify results
        self.assertEqual(len(results), 3)
        
        # Verify ranking by similarity score (descending)
        self.assertEqual(results[0].psalm_id, "Psalm 23")
        self.assertEqual(results[0].similarity_score, 0.95)
        self.assertEqual(results[1].psalm_id, "Psalm 46")
        self.assertEqual(results[1].similarity_score, 0.88)
        self.assertEqual(results[2].psalm_id, "Psalm 91")
        self.assertEqual(results[2].similarity_score, 0.82)
        
        # Verify client was called correctly
        self.mock_client.retrieve.assert_called_once()
        call_args = self.mock_client.retrieve.call_args
        self.assertEqual(call_args[1]["knowledgeBaseId"], self.knowledge_base_id)
    
    def test_search_filters_by_threshold(self):
        """
        Test that search filters results below similarity threshold.
        
        **Validates: Requirement 3.3**
        """
        # Mock response with mixed scores
        self.mock_client.retrieve.return_value = {
            "retrievalResults": [
                {
                    "score": 0.95,
                    "content": {"text": "High score"},
                    "metadata": {"psalm_id": "Psalm 1"}
                },
                {
                    "score": 0.65,  # Below threshold
                    "content": {"text": "Low score"},
                    "metadata": {"psalm_id": "Psalm 2"}
                },
                {
                    "score": 0.85,
                    "content": {"text": "Medium score"},
                    "metadata": {"psalm_id": "Psalm 3"}
                },
                {
                    "score": 0.80,
                    "content": {"text": "Another medium score"},
                    "metadata": {"psalm_id": "Psalm 4"}
                }
            ]
        }
        
        query_embedding = [0.1] * 1536
        results = self.vector_store.search(
            query_embedding=query_embedding,
            similarity_threshold=0.7,
            min_results=3  # Ensure we get enough results
        )
        
        # Should only include results >= 0.7
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].similarity_score, 0.95)
        self.assertEqual(results[1].similarity_score, 0.85)
        self.assertEqual(results[2].similarity_score, 0.80)
    
    def test_search_limits_max_results(self):
        """
        Test that search respects max_results limit.
        
        **Validates: Requirement 3.2**
        """
        # Mock response with many results
        self.mock_client.retrieve.return_value = {
            "retrievalResults": [
                {
                    "score": 0.9 - (i * 0.05),
                    "content": {"text": f"Psalm {i}"},
                    "metadata": {"psalm_id": f"Psalm {i}"}
                }
                for i in range(10)
            ]
        }
        
        query_embedding = [0.1] * 1536
        results = self.vector_store.search(
            query_embedding=query_embedding,
            max_results=3,
            similarity_threshold=0.0
        )
        
        # Should only return 3 results
        self.assertEqual(len(results), 3)
    
    def test_search_fallback_insufficient_results(self):
        """
        Test fallback to default psalms when insufficient results.
        
        **Validates: Requirement 3.4**
        """
        # Mock response with only 1 result
        self.mock_client.retrieve.return_value = {
            "retrievalResults": [
                {
                    "score": 0.85,
                    "content": {"text": "Single result"},
                    "metadata": {"psalm_id": "Psalm 1"}
                }
            ]
        }
        
        query_embedding = [0.1] * 1536
        results = self.vector_store.search(
            query_embedding=query_embedding,
            min_results=3
        )
        
        # Should return default psalms
        self.assertEqual(len(results), 3)
        self.assertIn("Psalm 23", [r.psalm_id for r in results])
        self.assertIn("Psalm 46", [r.psalm_id for r in results])
        self.assertIn("Psalm 91", [r.psalm_id for r in results])
    
    @patch('src.shared.vector_store.time.sleep')
    def test_search_retry_on_throttling(self, mock_sleep):
        """
        Test retry logic with exponential backoff on throttling.
        
        **Validates: Requirement 8.2**
        """
        # Mock throttling error then success
        self.mock_client.retrieve.side_effect = [
            ClientError(
                {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
                "retrieve"
            ),
            {
                "retrievalResults": [
                    {
                        "score": 0.9,
                        "content": {"text": "Success after retry 1"},
                        "metadata": {"psalm_id": "Psalm 23"}
                    },
                    {
                        "score": 0.85,
                        "content": {"text": "Success after retry 2"},
                        "metadata": {"psalm_id": "Psalm 46"}
                    },
                    {
                        "score": 0.80,
                        "content": {"text": "Success after retry 3"},
                        "metadata": {"psalm_id": "Psalm 91"}
                    }
                ]
            }
        ]
        
        query_embedding = [0.1] * 1536
        results = self.vector_store.search(query_embedding=query_embedding)
        
        # Should succeed after retry
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].psalm_id, "Psalm 23")
        
        # Verify retry was attempted
        self.assertEqual(self.mock_client.retrieve.call_count, 2)
        
        # Verify exponential backoff (2^1 = 2 seconds)
        mock_sleep.assert_called_once_with(2.0)
    
    @patch('src.shared.vector_store.time.sleep')
    def test_search_fallback_after_max_retries(self, mock_sleep):
        """
        Test fallback to default psalms after max retries exhausted.
        
        **Validates: Requirements 3.4, 8.2**
        """
        # Mock persistent failure
        self.mock_client.retrieve.side_effect = ClientError(
            {"Error": {"Code": "ServiceUnavailableException", "Message": "Service down"}},
            "retrieve"
        )
        
        query_embedding = [0.1] * 1536
        results = self.vector_store.search(query_embedding=query_embedding)
        
        # Should return default psalms after retries
        self.assertEqual(len(results), 3)
        self.assertIn("Psalm 23", [r.psalm_id for r in results])
        
        # Verify all retries were attempted
        self.assertEqual(self.mock_client.retrieve.call_count, 3)
    
    def test_search_empty_embedding_raises_error(self):
        """Test that empty query embedding raises ValueError."""
        with self.assertRaises(ValueError):
            self.vector_store.search(query_embedding=[])
    
    def test_insert_not_implemented(self):
        """
        Test that direct insert raises NotImplementedError.
        
        **Validates: Requirement 6.1**
        """
        with self.assertRaises(NotImplementedError):
            self.vector_store.insert(
                item_id="psalm-1",
                embedding=[0.1] * 1536,
                content="Test content",
                metadata={}
            )
    
    def test_update_not_implemented(self):
        """
        Test that direct update raises NotImplementedError.
        
        **Validates: Requirement 6.4**
        """
        with self.assertRaises(NotImplementedError):
            self.vector_store.update(
                item_id="psalm-1",
                content="Updated content"
            )
    
    def test_default_psalms_structure(self):
        """Test that default psalms have required structure."""
        default_psalms = BedrockKnowledgeBaseVectorStore.DEFAULT_PSALMS
        
        self.assertEqual(len(default_psalms), 3)
        
        for psalm in default_psalms:
            self.assertIn("psalm_id", psalm)
            self.assertIn("content", psalm)
            self.assertIn("metadata", psalm)
            self.assertIn("themes", psalm["metadata"])
            self.assertIn("emotional_context", psalm["metadata"])


class TestVectorStoreInterface(unittest.TestCase):
    """Test cases for VectorStore abstract interface."""
    
    def test_cannot_instantiate_abstract_class(self):
        """Test that VectorStore abstract class cannot be instantiated."""
        with self.assertRaises(TypeError):
            VectorStore()
    
    def test_subclass_must_implement_search(self):
        """Test that subclass must implement search method."""
        class IncompleteVectorStore(VectorStore):
            def insert(self, *args, **kwargs):
                pass
            def update(self, *args, **kwargs):
                pass
        
        with self.assertRaises(TypeError):
            IncompleteVectorStore()


if __name__ == "__main__":
    unittest.main()
