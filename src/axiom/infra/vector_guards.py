#!/usr/bin/env python3
"""
vector_guards.py - VectorAdapter protection with timeout guards and rate limiting

This module provides timeout protection and rate limiting for VectorAdapter
operations to prevent resource exhaustion and improve reliability.
"""

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

import requests

from . import COMPONENT_TIMEOUT_THRESHOLD, RateLimitException, infra_logger


@dataclass
class VectorOperationMetrics:
    """Metrics for vector operations"""

    operation_name: str
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0
    avg_response_time_ms: float = 0.0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    consecutive_failures: int = 0


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting"""

    max_tokens: int
    current_tokens: int
    refill_rate: float  # tokens per second
    last_refill: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class VectorAdapterGuard:
    """
    Protection layer for VectorAdapter operations.

    Features:
    - Timeout guards with configurable limits
    - Rate limiting with token bucket algorithm
    - Operation metrics tracking
    - Failure detection and circuit breaker patterns
    - Automatic fallback mode activation
    """

    def __init__(
        self,
        default_timeout: float = COMPONENT_TIMEOUT_THRESHOLD,
        max_requests_per_second: float = 10.0,
        burst_capacity: int = 20,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: int = 60,
    ):
        """
        Initialize VectorAdapter guard.

        Args:
            default_timeout: Default timeout for operations in seconds
            max_requests_per_second: Maximum requests per second allowed
            burst_capacity: Maximum burst requests allowed
            circuit_breaker_threshold: Consecutive failures before circuit opens
            circuit_breaker_timeout: Seconds to wait before trying again
        """
        self.default_timeout = default_timeout
        self.max_requests_per_second = max_requests_per_second
        self.burst_capacity = burst_capacity
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout

        # Rate limiting
        self.rate_limit_bucket = RateLimitBucket(
            max_tokens=burst_capacity,
            current_tokens=burst_capacity,
            refill_rate=max_requests_per_second,
        )

        # Operation tracking
        self.operation_metrics: Dict[str, VectorOperationMetrics] = {}
        self.lock = threading.Lock()

        # Circuit breaker state
        self.circuit_open = False
        self.circuit_open_time: Optional[datetime] = None
        self.consecutive_failures = 0

        # Fallback state
        self.fallback_active = False
        self.fallback_reason = None

        infra_logger.info(
            f"🛡️ VectorAdapter guard initialized (timeout: {default_timeout}s, "
            f"rate limit: {max_requests_per_second}/s, burst: {burst_capacity})"
        )

    def _refill_tokens(self):
        """Refill rate limit tokens based on elapsed time"""
        now = datetime.now(timezone.utc)
        elapsed = (now - self.rate_limit_bucket.last_refill).total_seconds()

        tokens_to_add = elapsed * self.rate_limit_bucket.refill_rate
        self.rate_limit_bucket.current_tokens = min(
            self.rate_limit_bucket.max_tokens,
            self.rate_limit_bucket.current_tokens + tokens_to_add,
        )
        self.rate_limit_bucket.last_refill = now

    def _check_rate_limit(self) -> bool:
        """Check if operation is within rate limits"""
        with self.lock:
            self._refill_tokens()

            if self.rate_limit_bucket.current_tokens >= 1:
                self.rate_limit_bucket.current_tokens -= 1
                return True
            else:
                return False

    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker allows operation"""
        if not self.circuit_open:
            return True

        # Check if enough time has passed to try again
        if self.circuit_open_time:
            elapsed = (
                datetime.now(timezone.utc) - self.circuit_open_time
            ).total_seconds()
            if elapsed > self.circuit_breaker_timeout:
                infra_logger.info(
                    "🔄 Circuit breaker timeout elapsed, attempting to close circuit"
                )
                self.circuit_open = False
                self.circuit_open_time = None
                return True

        return False

    def _record_success(self, operation_name: str, response_time_ms: float):
        """Record successful operation"""
        with self.lock:
            if operation_name not in self.operation_metrics:
                self.operation_metrics[operation_name] = VectorOperationMetrics(
                    operation_name
                )

            metrics = self.operation_metrics[operation_name]
            metrics.success_count += 1
            metrics.last_success = datetime.now(timezone.utc)
            metrics.consecutive_failures = 0

            # Update average response time
            total_ops = metrics.success_count + metrics.failure_count
            metrics.avg_response_time_ms = (
                metrics.avg_response_time_ms * (total_ops - 1) + response_time_ms
            ) / total_ops

            # Reset circuit breaker if it was open
            if self.circuit_open:
                infra_logger.info(
                    f"🟢 Circuit breaker closed after successful {operation_name}"
                )
                self.circuit_open = False
                self.circuit_open_time = None
                self.consecutive_failures = 0

    def _record_failure(
        self, operation_name: str, error: Exception, is_timeout: bool = False
    ):
        """Record failed operation"""
        with self.lock:
            if operation_name not in self.operation_metrics:
                self.operation_metrics[operation_name] = VectorOperationMetrics(
                    operation_name
                )

            metrics = self.operation_metrics[operation_name]
            metrics.failure_count += 1
            metrics.last_failure = datetime.now(timezone.utc)
            metrics.consecutive_failures += 1

            if is_timeout:
                metrics.timeout_count += 1

            # Update global consecutive failures
            self.consecutive_failures += 1

            # Check if circuit breaker should open
            if (
                metrics.consecutive_failures >= self.circuit_breaker_threshold
                and not self.circuit_open
            ):

                infra_logger.warning(
                    f"🔴 Circuit breaker opened for VectorAdapter after {metrics.consecutive_failures} "
                    f"consecutive failures in {operation_name}"
                )
                self.circuit_open = True
                self.circuit_open_time = datetime.now(timezone.utc)

                # Activate fallback mode
                self._activate_fallback(f"Circuit breaker opened: {error}")

    def _activate_fallback(self, reason: str):
        """Activate fallback mode"""
        if not self.fallback_active:
            self.fallback_active = True
            self.fallback_reason = reason
            infra_logger.warning(f"🔄 VectorAdapter fallback activated: {reason}")

    def _deactivate_fallback(self):
        """Deactivate fallback mode"""
        if self.fallback_active:
            self.fallback_active = False
            self.fallback_reason = None
            infra_logger.info("✅ VectorAdapter fallback deactivated")

    def protected_operation(
        self,
        operation_name: str,
        timeout: Optional[float] = None,
        allow_fallback: bool = True,
    ):
        """
        Decorator to protect vector operations with timeout and rate limiting.

        Args:
            operation_name: Name of the operation for metrics
            timeout: Operation timeout (uses default if None)
            allow_fallback: Whether to allow fallback mode activation
        """

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Check rate limits
                if not self._check_rate_limit():
                    infra_logger.warning(f"🚦 Rate limit exceeded for {operation_name}")
                    if allow_fallback:
                        raise RateLimitException(
                            f"Rate limit exceeded for {operation_name}"
                        )
                    time.sleep(0.1)  # Brief delay before retrying

                # Check circuit breaker
                if not self._check_circuit_breaker():
                    infra_logger.warning(
                        f"🔴 Circuit breaker open for {operation_name}"
                    )
                    if allow_fallback:
                        return []  # Return empty result for fallback
                    raise Exception(f"Circuit breaker open for {operation_name}")

                # Execute operation with timeout
                effective_timeout = timeout or self.default_timeout
                start_time = time.time()

                try:
                    # Set timeout for requests operations
                    if "timeout" not in kwargs and hasattr(func, "__name__"):
                        kwargs["timeout"] = effective_timeout

                    result = func(*args, **kwargs)

                    # Record success
                    response_time_ms = (time.time() - start_time) * 1000
                    self._record_success(operation_name, response_time_ms)

                    # Deactivate fallback if operation succeeded
                    if self.fallback_active and not self.circuit_open:
                        self._deactivate_fallback()

                    return result

                except requests.exceptions.Timeout as e:
                    response_time_ms = (time.time() - start_time) * 1000
                    infra_logger.warning(
                        f"⏰ Timeout in {operation_name} after {response_time_ms:.0f}ms"
                    )
                    self._record_failure(operation_name, e, is_timeout=True)

                    if allow_fallback:
                        return []  # Return empty result for fallback
                    raise

                except (
                    requests.exceptions.ConnectionError,
                    requests.exceptions.RequestException,
                ) as e:
                    response_time_ms = (time.time() - start_time) * 1000
                    infra_logger.warning(
                        f"🔌 Connection error in {operation_name}: {e}"
                    )
                    self._record_failure(operation_name, e)

                    if allow_fallback:
                        return []  # Return empty result for fallback
                    raise

                except Exception as e:
                    response_time_ms = (time.time() - start_time) * 1000
                    infra_logger.error(f"❌ Error in {operation_name}: {e}")
                    self._record_failure(operation_name, e)

                    if allow_fallback:
                        return []  # Return empty result for fallback
                    raise

            return wrapper

        return decorator

    def get_operation_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all operations"""
        with self.lock:
            metrics = {}
            for name, metric in self.operation_metrics.items():
                total_ops = metric.success_count + metric.failure_count
                success_rate = (
                    (metric.success_count / total_ops) if total_ops > 0 else 0.0
                )

                metrics[name] = {
                    "success_count": metric.success_count,
                    "failure_count": metric.failure_count,
                    "timeout_count": metric.timeout_count,
                    "success_rate": round(success_rate * 100, 1),
                    "avg_response_time_ms": round(metric.avg_response_time_ms, 1),
                    "consecutive_failures": metric.consecutive_failures,
                    "last_success": (
                        metric.last_success.isoformat() if metric.last_success else None
                    ),
                    "last_failure": (
                        metric.last_failure.isoformat() if metric.last_failure else None
                    ),
                }

            return metrics

    def get_status(self) -> Dict[str, Any]:
        """Get current guard status"""
        with self.lock:
            return {
                "circuit_open": self.circuit_open,
                "circuit_open_time": (
                    self.circuit_open_time.isoformat()
                    if self.circuit_open_time
                    else None
                ),
                "fallback_active": self.fallback_active,
                "fallback_reason": self.fallback_reason,
                "consecutive_failures": self.consecutive_failures,
                "current_tokens": self.rate_limit_bucket.current_tokens,
                "max_tokens": self.rate_limit_bucket.max_tokens,
                "rate_limit_per_sec": self.max_requests_per_second,
                "default_timeout": self.default_timeout,
                "operation_count": len(self.operation_metrics),
            }

    def reset_circuit_breaker(self):
        """Manually reset circuit breaker"""
        with self.lock:
            self.circuit_open = False
            self.circuit_open_time = None
            self.consecutive_failures = 0
            infra_logger.info("🔄 Circuit breaker manually reset")

    def is_healthy(self) -> bool:
        """Check if VectorAdapter is considered healthy"""
        return not self.circuit_open and not self.fallback_active


def create_vector_guard(vector_adapter, **kwargs) -> VectorAdapterGuard:
    """
    Create and attach a protection guard to a VectorAdapter instance.

    Args:
        vector_adapter: The VectorAdapter instance to protect
        **kwargs: Configuration options for the guard

    Returns:
        VectorAdapterGuard instance
    """
    guard = VectorAdapterGuard(**kwargs)

    # Attach guard to vector adapter
    vector_adapter._protection_guard = guard

    return guard


def protect_vector_method(vector_adapter, method_name: str, **guard_kwargs):
    """
    Protect a specific VectorAdapter method with guards.

    Args:
        vector_adapter: The VectorAdapter instance
        method_name: Name of the method to protect
        **guard_kwargs: Options for the protection decorator
    """
    if not hasattr(vector_adapter, "_protection_guard"):
        create_vector_guard(vector_adapter)

    guard = vector_adapter._protection_guard
    original_method = getattr(vector_adapter, method_name)

    # Apply protection decorator
    protected_method = guard.protected_operation(
        operation_name=method_name, **guard_kwargs
    )(original_method)

    # Replace original method
    setattr(vector_adapter, method_name, protected_method)

    infra_logger.info(f"🛡️ Protected VectorAdapter.{method_name} with guards")


def protect_vector_adapter(vector_adapter, **guard_kwargs) -> VectorAdapterGuard:
    """
    Protect all key VectorAdapter methods with guards.

    Args:
        vector_adapter: The VectorAdapter instance to protect
        **guard_kwargs: Configuration options for the guard

    Returns:
        VectorAdapterGuard instance
    """
    guard = create_vector_guard(vector_adapter, **guard_kwargs)

    # List of methods to protect
    methods_to_protect = [
        ("search", {"timeout": 10.0}),
        ("recall", {"timeout": 8.0}),
        ("query_related_memories", {"timeout": 8.0}),
        ("get_vector_matches", {"timeout": 8.0}),
        ("search_memory_vectors", {"timeout": 8.0}),
    ]

    for method_name, method_options in methods_to_protect:
        if hasattr(vector_adapter, method_name):
            protect_vector_method(vector_adapter, method_name, **method_options)

    infra_logger.info(
        "🛡️ VectorAdapter fully protected with timeout and rate limiting guards"
    )
    return guard


def is_vector_healthy(vector_adapter) -> bool:
    """Check if VectorAdapter is healthy"""
    if hasattr(vector_adapter, "_protection_guard"):
        return vector_adapter._protection_guard.is_healthy()
    return True  # Assume healthy if no guard


def get_vector_metrics(vector_adapter) -> Dict[str, Any]:
    """Get VectorAdapter operation metrics"""
    if hasattr(vector_adapter, "_protection_guard"):
        guard = vector_adapter._protection_guard
        return {
            "status": guard.get_status(),
            "operations": guard.get_operation_metrics(),
        }
    return {"status": "no_guard", "operations": {}}


def reset_vector_circuit_breaker(vector_adapter):
    """Reset VectorAdapter circuit breaker"""
    if hasattr(vector_adapter, "_protection_guard"):
        vector_adapter._protection_guard.reset_circuit_breaker()
        infra_logger.info("🔄 VectorAdapter circuit breaker reset")
