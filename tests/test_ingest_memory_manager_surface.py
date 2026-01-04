#!/usr/bin/env python3
"""
Test for MemoryManager surface required by ingest_world_map.py

This test ensures that the MemoryManager symbol resolves and provides
the minimal surface expected by the ingester without requiring vector deps.
"""

import os
import sys

# Add workspace root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")


def test_memory_manager_surface_no_vector():
    """Test MemoryManager minimal surface without vector dependencies"""
    from pods.memory import MemoryManager

    # Initialize with vector_sync=False (default)
    mm = MemoryManager(vector_sync=False)

    # Test store method
    rec = mm.store({"kind": "test", "text": "hello"})
    assert isinstance(rec, dict)
    assert "id" in rec

    # Test store_memory alias
    rec2 = mm.store_memory({"kind": "test2", "text": "world"})
    assert isinstance(rec2, dict)
    assert "id" in rec2

    # Test long_term_memory attribute
    assert hasattr(mm, "long_term_memory")
    assert hasattr(mm.long_term_memory, "__len__")  # List-like
    assert len(mm.long_term_memory) >= 2  # Should have our test entries

    # Test close method (should not fail)
    mm.close()


def test_memory_manager_surface_vector_sync_missing_deps():
    """Test MemoryManager with vector_sync=True when deps are missing"""
    from pods.memory import MemoryManager

    # Initialize with vector_sync=True (should gracefully fallback)
    mm = MemoryManager(vector_sync=True)

    # Should still work, just without vector backend
    rec = mm.store({"kind": "test_vector", "text": "fallback test"})
    assert isinstance(rec, dict)
    assert "id" in rec

    # Should still have functional long_term_memory
    assert len(mm.long_term_memory) >= 1

    mm.close()


def test_memory_manager_coercion():
    """Test that MemoryManager can handle different input types"""
    from pods.memory import MemoryManager

    mm = MemoryManager()

    # Test dict input
    rec1 = mm.store({"content": "test dict"})
    assert "content" in rec1

    # Test string input
    rec2 = mm.store("test string")
    assert "text" in rec2
    assert rec2["text"] == "test string"

    # Test None input
    rec3 = mm.store(None)
    assert isinstance(rec3, dict)

    # Test kwargs
    rec4 = mm.store(content="test kwargs", importance=0.8)
    assert rec4["content"] == "test kwargs"
    assert rec4["importance"] == 0.8

    mm.close()


def test_memory_manager_import_resolution():
    """Test that the MemoryManager can be imported from the expected path"""
    # This should not raise ImportError
    from pods.memory import MemoryManager

    # Should be a class
    assert isinstance(MemoryManager, type)

    # Should be instantiable
    mm = MemoryManager()
    assert mm is not None
    mm.close()


if __name__ == "__main__":
    print("Running MemoryManager surface tests...")

    try:
        test_memory_manager_surface_no_vector()
        print("✅ test_memory_manager_surface_no_vector PASSED")
    except Exception as e:
        print(f"❌ test_memory_manager_surface_no_vector FAILED: {e}")
        raise

    try:
        test_memory_manager_surface_vector_sync_missing_deps()
        print("✅ test_memory_manager_surface_vector_sync_missing_deps PASSED")
    except Exception as e:
        print(f"❌ test_memory_manager_surface_vector_sync_missing_deps FAILED: {e}")
        raise

    try:
        test_memory_manager_coercion()
        print("✅ test_memory_manager_coercion PASSED")
    except Exception as e:
        print(f"❌ test_memory_manager_coercion FAILED: {e}")
        raise

    try:
        test_memory_manager_import_resolution()
        print("✅ test_memory_manager_import_resolution PASSED")
    except Exception as e:
        print(f"❌ test_memory_manager_import_resolution FAILED: {e}")
        raise

    print("🎉 All tests passed!")
