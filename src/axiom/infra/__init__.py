"""
Infrastructure safety and monitoring package for Axiom

This package provides resource exhaustion guards, health monitoring,
and safety mechanisms for Axiom's cognitive architecture.
"""

import logging
import os

# Configure infrastructure logging
os.makedirs("data/logs", exist_ok=True)
infra_logger = logging.getLogger("InfraSafety")
handler = logging.FileHandler("data/logs/infrastructure.log")
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s")
handler.setFormatter(formatter)
infra_logger.addHandler(handler)
infra_logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))


# Base exceptions for infrastructure safety
class InfrastructureException(Exception):
    """Base exception for infrastructure-related issues"""

    pass


class MemoryOverloadException(InfrastructureException):
    """Raised when memory usage exceeds safe limits"""

    pass


class DiskSpaceException(InfrastructureException):
    """Raised when disk space is critically low"""

    pass


class ComponentHealthException(InfrastructureException):
    """Raised when a component fails health checks"""

    pass


class RateLimitException(InfrastructureException):
    """Raised when rate limits are exceeded"""

    pass


# Infrastructure configuration constants
MEMORY_LIMIT_DEFAULT = 5000  # Maximum in-RAM memories
MEMORY_CACHE_SIZE_LIMIT_MB = 100  # Fallback cache size limit
DISK_WARNING_THRESHOLD = 0.8  # 80% usage warning
DISK_CRITICAL_THRESHOLD = 500  # 500MB minimum free space
HEALTH_CHECK_INTERVAL = 30  # seconds between health checks
COMPONENT_TIMEOUT_THRESHOLD = 15  # seconds before component considered unhealthy

__all__ = [
    "InfrastructureException",
    "MemoryOverloadException",
    "DiskSpaceException",
    "ComponentHealthException",
    "RateLimitException",
    "infra_logger",
    "MEMORY_LIMIT_DEFAULT",
    "MEMORY_CACHE_SIZE_LIMIT_MB",
    "DISK_WARNING_THRESHOLD",
    "DISK_CRITICAL_THRESHOLD",
    "HEALTH_CHECK_INTERVAL",
    "COMPONENT_TIMEOUT_THRESHOLD",
]
