# Memory module init with fallback MemoryManager
try:
    from .memory_manager import MemoryManager
except ImportError:
    # If the main memory manager can't import due to dependencies,
    # provide the minimal implementation
    from .memory_manager_minimal import MemoryManager

__all__ = ["MemoryManager"]
