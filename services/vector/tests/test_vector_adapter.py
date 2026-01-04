#!/usr/bin/env python3
"""
test_vector_adapter.py - Comprehensive Vector Adapter Tests

Mission: Ensure vector search methods always return a list, even if the underlying query fails or returns null.
Test cases cover:
- Empty but valid response
- Weaviate error (simulate exception)
- Schema mismatch (e.g., missing fields)
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, Mock, patch

# Add the pods/vector directory to the path so we can import vector_adapter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from vector_adapter import VectorAdapter
except ImportError:
    # Try importing from parent directory
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from vector_adapter import VectorAdapter


class TestVectorAdapterReliability(unittest.TestCase):
    """Test that VectorAdapter methods NEVER return None"""

    def setUp(self):
        """Set up test fixtures"""
        self.adapter = VectorAdapter()

    def test_search_empty_query_returns_list(self):
        """Test that search() returns empty list for empty query, not None"""
        result = self.adapter.search("")
        self.assertIsInstance(
            result, list, "search() should return list for empty query"
        )
        self.assertEqual(
            result, [], "search() should return empty list for empty query"
        )

    def test_search_none_query_returns_list(self):
        """Test that search() returns empty list for None query, not None"""
        result = self.adapter.search(None)
        self.assertIsInstance(
            result, list, "search() should return list for None query"
        )
        self.assertEqual(result, [], "search() should return empty list for None query")

    def test_query_related_memories_empty_query(self):
        """Test that query_related_memories() returns empty list for empty query"""
        result = self.adapter.query_related_memories("")
        self.assertIsInstance(
            result, list, "query_related_memories() should return list"
        )
        self.assertEqual(
            result,
            [],
            "query_related_memories() should return empty list for empty query",
        )

    def test_get_vector_matches_empty_query(self):
        """Test that get_vector_matches() returns empty list for empty query"""
        result = self.adapter.get_vector_matches("")
        self.assertIsInstance(result, list, "get_vector_matches() should return list")
        self.assertEqual(
            result, [], "get_vector_matches() should return empty list for empty query"
        )

    def test_search_memory_vectors_empty_query(self):
        """Test that search_memory_vectors() returns empty list for empty query"""
        result = self.adapter.search_memory_vectors("")
        self.assertIsInstance(
            result, list, "search_memory_vectors() should return list"
        )
        self.assertEqual(
            result,
            [],
            "search_memory_vectors() should return empty list for empty query",
        )

    @patch("requests.post")
    def test_search_weaviate_returns_none_response(self, mock_post):
        """Test search() when Weaviate returns None response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = None
        mock_post.return_value = mock_response

        result = self.adapter.search("test query")
        self.assertIsInstance(
            result, list, "search() should return list when Weaviate returns None"
        )
        self.assertEqual(
            result, [], "search() should return empty list when Weaviate returns None"
        )

    @patch("requests.post")
    def test_search_weaviate_http_error(self, mock_post):
        """Test search() when Weaviate returns HTTP error"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        result = self.adapter.search("test query")
        self.assertIsInstance(result, list, "search() should return list on HTTP error")
        self.assertEqual(result, [], "search() should return empty list on HTTP error")

    @patch("requests.post")
    def test_search_weaviate_malformed_response(self, mock_post):
        """Test search() when Weaviate returns malformed response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"invalid": "structure"}
        mock_post.return_value = mock_response

        result = self.adapter.search("test query")
        self.assertIsInstance(
            result, list, "search() should return list with malformed response"
        )
        self.assertEqual(
            result, [], "search() should return empty list with malformed response"
        )

    @patch("requests.post")
    def test_search_weaviate_memory_class_none(self, mock_post):
        """Test search() when Memory class returns None instead of list"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"Get": {"Memory": None}}  # This should trigger our None handling
        }
        mock_post.return_value = mock_response

        result = self.adapter.search("test query")
        self.assertIsInstance(
            result, list, "search() should return list when Memory class returns None"
        )
        self.assertEqual(
            result,
            [],
            "search() should return empty list when Memory class returns None",
        )

    @patch("requests.post")
    def test_search_requests_exception(self, mock_post):
        """Test search() when requests.post raises exception"""
        mock_post.side_effect = Exception("Connection timeout")

        result = self.adapter.search("test query")
        self.assertIsInstance(
            result, list, "search() should return list when requests raises exception"
        )
        self.assertEqual(
            result,
            [],
            "search() should return empty list when requests raises exception",
        )

    @patch("requests.post")
    def test_search_schema_mismatch_missing_fields(self, mock_post):
        """Test search() with schema mismatch - missing required fields"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "Get": {
                    "Memory": [
                        {"missing_text_field": "value"},  # Missing 'text' field
                        {"text": "valid memory"},  # This one should work
                    ]
                }
            }
        }
        mock_post.return_value = mock_response

        result = self.adapter.search("test query")
        self.assertIsInstance(
            result, list, "search() should return list with schema mismatch"
        )
        # Should filter out invalid entries but keep valid ones
        # Note: The actual filtering behavior depends on implementation

    @patch("requests.post")
    def test_search_missing_data_field(self, mock_post):
        """Test search() when response is missing 'data' field"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "wrong_field": "wrong_value",
            "unexpected": ["structure"],
        }
        mock_post.return_value = mock_response

        result = self.adapter.search("test query")
        self.assertIsInstance(
            result, list, "search() should return list with missing data field"
        )
        self.assertEqual(
            result, [], "search() should return empty list with missing data field"
        )

    @patch("requests.post")
    def test_search_data_field_not_dict(self, mock_post):
        """Test search() when 'data' field is not a dictionary"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": "not_a_dict"  # Should be dict but isn't
        }
        mock_post.return_value = mock_response

        result = self.adapter.search("test query")
        self.assertIsInstance(
            result, list, "search() should return list when data field is not dict"
        )
        self.assertEqual(
            result, [], "search() should return empty list when data field is not dict"
        )


class TestVectorAdapterAsyncReliability(unittest.IsolatedAsyncioTestCase):
    """Test that async VectorAdapter methods NEVER return None"""

    def setUp(self):
        """Set up test fixtures"""
        self.adapter = VectorAdapter()

    async def test_recall_relevant_memories_empty_query(self):
        """Test that recall_relevant_memories() returns empty list for empty query"""
        result = await self.adapter.recall_relevant_memories("")
        self.assertIsInstance(
            result,
            list,
            "recall_relevant_memories() should return list for empty query",
        )
        self.assertEqual(
            result,
            [],
            "recall_relevant_memories() should return empty list for empty query",
        )

    async def test_recall_relevant_memories_none_query(self):
        """Test that recall_relevant_memories() returns empty list for None query"""
        result = await self.adapter.recall_relevant_memories(None)
        self.assertIsInstance(
            result, list, "recall_relevant_memories() should return list for None query"
        )
        self.assertEqual(
            result,
            [],
            "recall_relevant_memories() should return empty list for None query",
        )

    @patch("aiohttp.ClientSession")
    async def test_recall_aiohttp_none_response(self, mock_session):
        """Test recall_relevant_memories() when aiohttp returns None response"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=None)

        mock_session_instance = AsyncMock()
        mock_session_instance.post.return_value.__aenter__.return_value = mock_response
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        result = await self.adapter.recall_relevant_memories("test query")
        self.assertIsInstance(
            result,
            list,
            "recall_relevant_memories() should return list when aiohttp returns None",
        )
        self.assertEqual(
            result,
            [],
            "recall_relevant_memories() should return empty list when aiohttp returns None",
        )

    @patch("aiohttp.ClientSession")
    async def test_recall_aiohttp_http_error(self, mock_session):
        """Test recall_relevant_memories() when aiohttp returns HTTP error"""
        mock_response = AsyncMock()
        mock_response.status = 500

        mock_session_instance = AsyncMock()
        mock_session_instance.post.return_value.__aenter__.return_value = mock_response
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        result = await self.adapter.recall_relevant_memories("test query")
        self.assertIsInstance(
            result, list, "recall_relevant_memories() should return list on HTTP error"
        )
        self.assertEqual(
            result,
            [],
            "recall_relevant_memories() should return empty list on HTTP error",
        )

    @patch("aiohttp.ClientSession")
    async def test_recall_aiohttp_exception(self, mock_session):
        """Test recall_relevant_memories() when aiohttp raises exception"""
        mock_session.side_effect = Exception("Connection timeout")

        result = await self.adapter.recall_relevant_memories("test query")
        self.assertIsInstance(
            result,
            list,
            "recall_relevant_memories() should return list when aiohttp raises exception",
        )
        self.assertEqual(
            result,
            [],
            "recall_relevant_memories() should return empty list when aiohttp raises exception",
        )

    @patch("aiohttp.ClientSession")
    async def test_recall_malformed_response(self, mock_session):
        """Test recall_relevant_memories() with malformed response structure"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "data": {"Get": {"Memory": None}}  # Should trigger None handling
            }
        )

        mock_session_instance = AsyncMock()
        mock_session_instance.post.return_value.__aenter__.return_value = mock_response
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        result = await self.adapter.recall_relevant_memories("test query")
        self.assertIsInstance(
            result,
            list,
            "recall_relevant_memories() should return list with malformed response",
        )
        self.assertEqual(
            result,
            [],
            "recall_relevant_memories() should return empty list with malformed response",
        )

    @patch("aiohttp.ClientSession")
    async def test_recall_invalid_hits_type(self, mock_session):
        """Test recall_relevant_memories() when hits is not a list"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "data": {"Get": {"Memory": "not_a_list"}}  # Should be list but isn't
            }
        )

        mock_session_instance = AsyncMock()
        mock_session_instance.post.return_value.__aenter__.return_value = mock_response
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        result = await self.adapter.recall_relevant_memories("test query")
        self.assertIsInstance(
            result,
            list,
            "recall_relevant_memories() should return list when hits is not list",
        )
        self.assertEqual(
            result,
            [],
            "recall_relevant_memories() should return empty list when hits is not list",
        )


class TestVectorAdapterWrapperMethods(unittest.TestCase):
    """Test wrapper methods that should never return None"""

    def setUp(self):
        """Set up test fixtures"""
        self.adapter = VectorAdapter()

    @patch.object(VectorAdapter, "search")
    def test_query_related_memories_wrapper(self, mock_search):
        """Test that query_related_memories wrapper handles None from search()"""
        # Test case where search() somehow returns None (shouldn't happen but test anyway)
        mock_search.return_value = None

        result = self.adapter.query_related_memories("test")
        self.assertIsInstance(
            result,
            list,
            "query_related_memories() should return list even if search() returns None",
        )
        self.assertEqual(
            result,
            [],
            "query_related_memories() should return empty list when search() returns None",
        )

    @patch.object(VectorAdapter, "search")
    def test_get_vector_matches_wrapper(self, mock_search):
        """Test that get_vector_matches wrapper handles None from search()"""
        # Test case where search() somehow returns None (shouldn't happen but test anyway)
        mock_search.return_value = None

        result = self.adapter.get_vector_matches("test")
        self.assertIsInstance(
            result,
            list,
            "get_vector_matches() should return list even if search() returns None",
        )
        self.assertEqual(
            result,
            [],
            "get_vector_matches() should return empty list when search() returns None",
        )

    @patch.object(VectorAdapter, "search")
    def test_search_memory_vectors_wrapper(self, mock_search):
        """Test that search_memory_vectors wrapper handles None from search()"""
        # Test case where search() somehow returns None (shouldn't happen but test anyway)
        mock_search.return_value = None

        result = self.adapter.search_memory_vectors("test")
        self.assertIsInstance(
            result,
            list,
            "search_memory_vectors() should return list even if search() returns None",
        )
        self.assertEqual(
            result,
            [],
            "search_memory_vectors() should return empty list when search() returns None",
        )

    @patch.object(VectorAdapter, "search")
    def test_wrapper_methods_exception_handling(self, mock_search):
        """Test that wrapper methods handle exceptions from search()"""
        mock_search.side_effect = Exception("Search failed")

        # Test each wrapper method
        result1 = self.adapter.query_related_memories("test")
        self.assertIsInstance(
            result1, list, "query_related_memories() should return list on exception"
        )
        self.assertEqual(
            result1,
            [],
            "query_related_memories() should return empty list on exception",
        )

        result2 = self.adapter.get_vector_matches("test")
        self.assertIsInstance(
            result2, list, "get_vector_matches() should return list on exception"
        )
        self.assertEqual(
            result2, [], "get_vector_matches() should return empty list on exception"
        )

        result3 = self.adapter.search_memory_vectors("test")
        self.assertIsInstance(
            result3, list, "search_memory_vectors() should return list on exception"
        )
        self.assertEqual(
            result3, [], "search_memory_vectors() should return empty list on exception"
        )


def run_tests():
    """Run all tests and return success status"""
    print("🧪 Running Vector Adapter Reliability Tests...")
    print("=" * 60)

    # Create test suite
    suite = unittest.TestSuite()

    # Add sync tests
    suite.addTest(unittest.makeSuite(TestVectorAdapterReliability))
    suite.addTest(unittest.makeSuite(TestVectorAdapterWrapperMethods))

    # Add async tests
    suite.addTest(unittest.makeSuite(TestVectorAdapterAsyncReliability))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("=" * 60)
    if result.wasSuccessful():
        print("✅ ALL VECTOR ADAPTER TESTS PASSED!")
        print(f"🎯 Ran {result.testsRun} tests successfully")
        return True
    else:
        print("❌ SOME VECTOR ADAPTER TESTS FAILED!")
        print(
            f"🎯 Ran {result.testsRun} tests: {len(result.failures)} failures, {len(result.errors)} errors"
        )
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
