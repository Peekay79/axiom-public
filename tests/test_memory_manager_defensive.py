#!/usr/bin/env python3
"""
Test suite for defensive handling of missing metadata in Memory class
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

# Add the parent directory to sys.path to import memory_manager
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory_types import MemoryTypeInferrer

from pods.memory.memory_manager import Memory


class TestMemoryDefensiveHandling(unittest.TestCase):
    """Test cases for defensive handling of missing metadata fields"""

    def setUp(self):
        """Set up test environment"""
        # Create a temporary file for memory storage
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        self.temp_file.close()

        # Patch the MEMORY_FILE constant to use our temp file
        self.memory_file_patcher = patch(
            "memory_manager.MEMORY_FILE", self.temp_file.name
        )
        self.memory_file_patcher.start()

        self.memory = Memory()
        self.type_inferrer = MemoryTypeInferrer()

    def tearDown(self):
        """Clean up test environment"""
        self.memory_file_patcher.stop()
        # Clean up temp file
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    def test_add_to_long_term_missing_type(self):
        """Test that add_to_long_term handles missing 'type' field gracefully"""
        entry = {
            "id": "test_001",
            "content": "This is a test memory without type field",
            "source": "test_system",
        }

        # This should not raise an exception
        try:
            memory_id = self.memory.add_to_long_term(entry)
            self.assertIsNotNone(memory_id)
        except AttributeError as e:
            if "'NoneType' object has no attribute 'lower'" in str(e):
                self.fail("Memory.add_to_long_term crashed with None.lower() error")
            else:
                raise

    def test_add_to_long_term_missing_source(self):
        """Test that add_to_long_term handles missing 'source' field gracefully"""
        entry = {
            "id": "test_002",
            "content": "This is a test memory without source field",
            "type": "belief",
        }

        # This should not raise an exception
        try:
            memory_id = self.memory.add_to_long_term(entry)
            self.assertIsNotNone(memory_id)
        except AttributeError as e:
            if "'NoneType' object has no attribute 'lower'" in str(e):
                self.fail("Memory.add_to_long_term crashed with None.lower() error")
            else:
                raise

    def test_add_to_long_term_none_type(self):
        """Test that add_to_long_term handles explicit None 'type' field gracefully"""
        entry = {
            "id": "test_003",
            "content": "This is a test memory with None type field",
            "type": None,
            "source": "test_system",
        }

        # This should not raise an exception
        try:
            memory_id = self.memory.add_to_long_term(entry)
            self.assertIsNotNone(memory_id)
        except AttributeError as e:
            if "'NoneType' object has no attribute 'lower'" in str(e):
                self.fail("Memory.add_to_long_term crashed with None.lower() error")
            else:
                raise

    def test_add_to_long_term_none_source(self):
        """Test that add_to_long_term handles explicit None 'source' field gracefully"""
        entry = {
            "id": "test_004",
            "content": "This is a test memory with None source field",
            "type": "belief",
            "source": None,
        }

        # This should not raise an exception
        try:
            memory_id = self.memory.add_to_long_term(entry)
            self.assertIsNotNone(memory_id)
        except AttributeError as e:
            if "'NoneType' object has no attribute 'lower'" in str(e):
                self.fail("Memory.add_to_long_term crashed with None.lower() error")
            else:
                raise

    def test_memory_type_inferrer_defensive_source(self):
        """Test that MemoryTypeInferrer handles None source gracefully"""
        try:
            memory_type = self.type_inferrer.infer_memory_type(
                content="Test content", source=None
            )
            self.assertIsNotNone(memory_type)
        except AttributeError as e:
            if "'NoneType' object has no attribute 'lower'" in str(e):
                self.fail(
                    "MemoryTypeInferrer.infer_memory_type crashed with None.lower() error"
                )
            else:
                raise

    def test_memory_type_inferrer_defensive_context_type(self):
        """Test that MemoryTypeInferrer handles None context['type'] gracefully"""
        context = {"type": None, "speaker": "user"}

        try:
            memory_type = self.type_inferrer.infer_memory_type(
                content="Test content", context=context
            )
            self.assertIsNotNone(memory_type)
        except AttributeError as e:
            if "'NoneType' object has no attribute 'lower'" in str(e):
                self.fail(
                    "MemoryTypeInferrer.infer_memory_type crashed with None.lower() error"
                )
            else:
                raise

    def test_memory_storage_and_retrieval_with_missing_metadata(self):
        """Integration test: store memory with missing metadata and retrieve it"""
        entry = {
            "id": "test_integration",
            "content": "Integration test memory without metadata",
            # Missing type, source, and other metadata
        }

        # Store the memory
        memory_id = self.memory.add_to_long_term(entry)
        self.assertIsNotNone(memory_id)

        # Retrieve the memory
        retrieved = self.memory.get(memory_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["content"], entry["content"])


if __name__ == "__main__":
    unittest.main()
