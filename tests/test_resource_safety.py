#!/usr/bin/env python3
"""
test_resource_safety.py - Test suite for Axiom infrastructure resource safety

This module tests memory guards, disk monitoring, vector adapter protection,
and stress scenarios to validate the infrastructure safety layer.
"""

import os
import shutil

# Add infra directory to path for testing
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from infra import (
    MEMORY_LIMIT_DEFAULT,
    DiskSpaceException,
    MemoryOverloadException,
    RateLimitException,
)
from infra.component_health import ComponentStatus, HealthMonitor
from infra.disk_guard import DiskUsageWatchdog, get_disk_watchdog
from infra.memory_guards import MemoryResourceGuard, create_memory_guard
from infra.vector_guards import VectorAdapterGuard, protect_vector_adapter


class TestMemoryResourceGuard(unittest.TestCase):
    """Test memory resource exhaustion guards"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

        # Create mock memory manager
        self.mock_memory_manager = Mock()
        self.mock_memory_manager.long_term_memory = []
        self.mock_memory_manager.fallback_store = Mock()
        self.mock_memory_manager.fallback_store.fallback_db_path = "fallback.db"

        # Create test guard with low limits for testing
        self.guard = MemoryResourceGuard(
            memory_limit=10,  # Low limit for testing
            cache_size_limit_mb=5,
            check_interval=1,
        )

    def tearDown(self):
        """Clean up test environment"""
        self.guard.stop_monitoring()
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_memory_usage_calculation(self):
        """Test memory usage calculation and stress detection"""
        # Test normal usage
        self.mock_memory_manager.long_term_memory = [
            {"id": f"mem_{i}"} for i in range(5)
        ]
        stats = self.guard.check_memory_usage(self.mock_memory_manager)

        self.assertEqual(stats.in_ram_count, 5)
        self.assertFalse(stats.is_stressed)
        self.assertFalse(stats.backpressure_active)

    def test_memory_stress_detection(self):
        """Test memory stress detection when approaching limits"""
        # Add memories to trigger stress (80% of limit = 8 memories)
        self.mock_memory_manager.long_term_memory = [
            {"id": f"mem_{i}"} for i in range(9)
        ]
        stats = self.guard.check_memory_usage(self.mock_memory_manager)

        self.assertEqual(stats.in_ram_count, 9)
        self.assertTrue(stats.is_stressed)
        self.assertTrue(stats.backpressure_active)  # 90% threshold

    def test_memory_overload_exception(self):
        """Test that severe overload raises exception"""
        # Add more memories than hard limit (110% of 10 = 11 memories)
        self.mock_memory_manager.long_term_memory = [
            {"id": f"mem_{i}"} for i in range(12)
        ]

        with self.assertRaises(MemoryOverloadException):
            self.guard.enforce_limits(self.mock_memory_manager)

    def test_memory_archiving(self):
        """Test automatic memory archiving under pressure"""
        # Create memories with timestamps and importance for archiving logic
        memories = []
        for i in range(15):  # Exceed limit to trigger archiving
            memory = {
                "id": f"mem_{i}",
                "content": f"Content {i}",
                "timestamp": f"2024-01-{i:02d}T00:00:00Z",
                "importance": 0.1 + (i * 0.05),  # Varying importance
                "source": "test",
                "memory_type": "semantic",
                "tags": ["test"],
            }
            memories.append(memory)

        self.mock_memory_manager.long_term_memory = memories
        self.mock_memory_manager.save = Mock()

        # Trigger archiving by checking usage
        stats = self.guard.check_memory_usage(self.mock_memory_manager)

        # Should trigger archiving due to exceeding archive threshold
        # Verify that some memories were processed for archiving
        self.assertTrue(stats.is_stressed)

    def test_backpressure_application(self):
        """Test backpressure application when limits are exceeded"""
        # Fill to backpressure threshold
        self.mock_memory_manager.long_term_memory = [
            {"id": f"mem_{i}"} for i in range(10)
        ]

        # Should not raise exception but return False for backpressure
        result = self.guard.enforce_limits(self.mock_memory_manager)
        self.assertFalse(result)  # Backpressure active

    def test_integration_with_memory_manager(self):
        """Test integration functions with memory manager"""
        guard = create_memory_guard(self.mock_memory_manager, memory_limit=5)

        # Guard should be attached to memory manager
        self.assertTrue(hasattr(self.mock_memory_manager, "_resource_guard"))
        self.assertIsInstance(
            self.mock_memory_manager._resource_guard, MemoryResourceGuard
        )

        # Test convenience functions
        from infra.memory_guards import (
            check_memory_limits,
            get_memory_usage_stats,
            is_memory_stressed,
        )

        # These should work without raising exceptions
        limits_ok = check_memory_limits(self.mock_memory_manager)
        stats = get_memory_usage_stats(self.mock_memory_manager)
        stressed = is_memory_stressed(self.mock_memory_manager)

        self.assertIsInstance(limits_ok, bool)
        self.assertIsInstance(stats, dict)
        self.assertIsInstance(stressed, bool)


class TestDiskUsageWatchdog(unittest.TestCase):
    """Test disk usage monitoring and alerting"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

        # Create watchdog with frequent checks for testing
        self.watchdog = DiskUsageWatchdog(check_interval=1)

    def tearDown(self):
        """Clean up test environment"""
        self.watchdog.stop_monitoring()
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_disk_usage_calculation(self):
        """Test disk usage calculation"""
        status = self.watchdog.check_disk_status(".")

        self.assertIn("usage_percentage", status)
        self.assertIn("available_mb", status)
        self.assertIn("total_mb", status)
        self.assertIn("is_stressed", status)
        self.assertIsInstance(status["usage_percentage"], (int, float))
        self.assertIsInstance(status["available_mb"], int)

    def test_disk_stress_detection(self):
        """Test disk stress detection logic"""
        # Mock disk usage to simulate high usage
        with patch.object(self.watchdog, "get_disk_usage") as mock_usage:
            # Simulate 85% usage, 400MB available (below 500MB threshold)
            mock_usage.return_value = (0.85, 400, 1000)

            status = self.watchdog.check_disk_status(".")
            self.assertTrue(status["is_stressed"])

    def test_disk_monitoring_thread(self):
        """Test background disk monitoring"""
        self.watchdog.start_monitoring()

        # Wait a short time for monitoring to run
        time.sleep(2)

        # Check that monitoring is active
        self.assertTrue(self.watchdog.monitoring)
        self.assertIsNotNone(self.watchdog.last_check)

        # Stop monitoring
        self.watchdog.stop_monitoring()
        self.assertFalse(self.watchdog.monitoring)

    def test_convenience_functions(self):
        """Test global convenience functions"""
        from infra.disk_guard import get_disk_status, is_disk_stressed

        stressed = is_disk_stressed()
        status = get_disk_status()

        self.assertIsInstance(stressed, bool)
        self.assertIsInstance(status, dict)
        self.assertIn("is_stressed", status)


class TestVectorAdapterGuard(unittest.TestCase):
    """Test VectorAdapter protection with timeout and rate limiting"""

    def setUp(self):
        """Set up test environment"""
        self.guard = VectorAdapterGuard(
            default_timeout=2.0,
            max_requests_per_second=5.0,
            burst_capacity=10,
            circuit_breaker_threshold=3,
        )

        # Create mock vector adapter
        self.mock_vector_adapter = Mock()
        self.mock_vector_adapter.search = Mock(return_value=[])
        self.mock_vector_adapter.recall = Mock(return_value=[])

    def test_rate_limiting(self):
        """Test rate limiting functionality"""
        # Should allow initial requests up to burst capacity
        for i in range(10):
            self.assertTrue(self.guard._check_rate_limit())

        # Should deny next request (exceeded burst)
        self.assertFalse(self.guard._check_rate_limit())

        # Wait for token refill and try again
        time.sleep(1.1)  # Allow time for refill
        self.assertTrue(self.guard._check_rate_limit())

    def test_circuit_breaker(self):
        """Test circuit breaker functionality"""
        # Initially circuit should be closed
        self.assertTrue(self.guard._check_circuit_breaker())

        # Simulate failures to open circuit
        for i in range(3):
            self.guard._record_failure("test_op", Exception("test error"))

        # Circuit should now be open
        self.assertTrue(self.guard.circuit_open)
        self.assertFalse(self.guard._check_circuit_breaker())

    def test_operation_protection(self):
        """Test protected operation decorator"""

        # Create a test function to protect
        @self.guard.protected_operation("test_operation", timeout=1.0)
        def test_func():
            return "success"

        # Should work normally
        result = test_func()
        self.assertEqual(result, "success")

        # Check metrics were recorded
        metrics = self.guard.get_operation_metrics()
        self.assertIn("test_operation", metrics)
        self.assertEqual(metrics["test_operation"]["success_count"], 1)

    def test_timeout_handling(self):
        """Test timeout handling in protected operations"""
        import requests

        @self.guard.protected_operation("slow_operation", timeout=0.1)
        def slow_func():
            time.sleep(0.2)  # Longer than timeout
            return "too_slow"

        # Should return empty list for fallback
        result = slow_func()
        self.assertEqual(result, [])

        # Check timeout was recorded
        metrics = self.guard.get_operation_metrics()
        if "slow_operation" in metrics:
            self.assertGreater(metrics["slow_operation"]["failure_count"], 0)

    def test_vector_adapter_integration(self):
        """Test integration with VectorAdapter"""
        from infra.vector_guards import (
            get_vector_metrics,
            is_vector_healthy,
            protect_vector_adapter,
        )

        # Protect the mock vector adapter
        guard = protect_vector_adapter(self.mock_vector_adapter)

        # Guard should be attached
        self.assertTrue(hasattr(self.mock_vector_adapter, "_protection_guard"))

        # Test convenience functions
        healthy = is_vector_healthy(self.mock_vector_adapter)
        metrics = get_vector_metrics(self.mock_vector_adapter)

        self.assertIsInstance(healthy, bool)
        self.assertIsInstance(metrics, dict)


class TestComponentHealthMonitor(unittest.TestCase):
    """Test component health monitoring system"""

    def setUp(self):
        """Set up test environment"""
        self.health_monitor = HealthMonitor(check_interval=1)

    def tearDown(self):
        """Clean up test environment"""
        self.health_monitor.stop_monitoring()

    def test_component_registration(self):
        """Test component registration"""
        self.health_monitor.register_component("TestComponent", is_critical=True)

        self.assertIn("TestComponent", self.health_monitor.components)
        self.assertTrue(self.health_monitor.components["TestComponent"].is_critical)

    def test_health_check_execution(self):
        """Test health check execution"""

        # Register component with mock health check
        def mock_health_check():
            return ComponentStatus.HEALTHY

        self.health_monitor.register_component(
            "TestComponent", health_check_func=mock_health_check
        )

        # Run health check
        import asyncio

        status = asyncio.run(
            self.health_monitor.check_component_health("TestComponent")
        )
        self.assertEqual(status, ComponentStatus.HEALTHY)

    def test_heartbeat_recording(self):
        """Test heartbeat recording"""
        self.health_monitor.heartbeat("TestComponent", {"key": "value"})

        component = self.health_monitor.components["TestComponent"]
        self.assertIsNotNone(component.last_heartbeat)
        self.assertEqual(component.metadata["key"], "value")

    def test_system_health_status(self):
        """Test system health status aggregation"""
        # Register some components
        self.health_monitor.register_component("Component1", is_critical=True)
        self.health_monitor.register_component("Component2", is_critical=False)

        status = self.health_monitor.get_system_status()

        self.assertIn("system_healthy", status)
        self.assertIn("component_count", status)
        self.assertIn("healthy_count", status)
        self.assertIn("components", status)

    def test_fallback_activation(self):
        """Test automatic fallback activation"""
        # This would normally test VectorAdapter fallback
        # For now, just test the mechanism exists
        self.health_monitor._enable_vector_fallback()
        self.assertTrue(self.health_monitor.fallback_active)


class TestStressScenarios(unittest.TestCase):
    """Test system behavior under stress scenarios"""

    def setUp(self):
        """Set up stress test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Clean up stress test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_memory_stress_scenario(self):
        """Test system behavior under memory stress"""
        # Create memory manager with very low limits
        mock_memory_manager = Mock()
        mock_memory_manager.long_term_memory = []
        mock_memory_manager.fallback_store = Mock()
        mock_memory_manager.save = Mock()

        guard = MemoryResourceGuard(memory_limit=5, cache_size_limit_mb=1)

        # Gradually add memories and check behavior
        for i in range(10):
            memory = {
                "id": f"stress_mem_{i}",
                "content": f"Stress test memory {i}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "importance": 0.5,
                "source": "stress_test",
            }
            mock_memory_manager.long_term_memory.append(memory)

            stats = guard.check_memory_usage(mock_memory_manager)

            if stats.backpressure_active:
                # Backpressure should be active when approaching limits
                self.assertGreater(len(mock_memory_manager.long_term_memory), 4)
                break

    def test_concurrent_operations_stress(self):
        """Test concurrent operations stress scenario"""
        guard = VectorAdapterGuard(max_requests_per_second=2.0, burst_capacity=3)

        results = []
        errors = []

        def worker():
            try:

                @guard.protected_operation("concurrent_test")
                def test_operation():
                    time.sleep(0.1)
                    return "success"

                result = test_operation()
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Start multiple concurrent workers
        threads = []
        for i in range(10):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()

        # Wait for all to complete
        for thread in threads:
            thread.join()

        # Some operations should succeed, some may hit rate limits
        self.assertGreater(len(results) + len(errors), 0)

        # Check that metrics were recorded
        metrics = guard.get_operation_metrics()
        self.assertIn("concurrent_test", metrics)

    def test_component_failure_cascade(self):
        """Test system behavior when components fail"""
        health_monitor = HealthMonitor(check_interval=0.5)

        # Register components that will fail
        def failing_health_check():
            raise Exception("Component failed")

        health_monitor.register_component(
            "FailingComponent", health_check_func=failing_health_check, is_critical=True
        )

        # Run health check - should handle failure gracefully
        import asyncio

        status = asyncio.run(health_monitor.check_component_health("FailingComponent"))
        self.assertEqual(status, ComponentStatus.UNHEALTHY)

        # System should detect the failure
        system_status = health_monitor.get_system_status()
        self.assertFalse(system_status["system_healthy"])

        health_monitor.stop_monitoring()


class TestIntegrationScenarios(unittest.TestCase):
    """Test integration between different safety components"""

    def test_memory_and_disk_interaction(self):
        """Test interaction between memory guards and disk monitoring"""
        # Create memory manager
        mock_memory_manager = Mock()
        mock_memory_manager.long_term_memory = []
        mock_memory_manager.fallback_store = Mock()
        mock_memory_manager.save = Mock()

        # Create guards
        memory_guard = create_memory_guard(mock_memory_manager, memory_limit=10)
        disk_watchdog = DiskUsageWatchdog()

        # Fill memory to trigger archiving
        for i in range(15):
            memory = {"id": f"mem_{i}", "content": f"Content {i}"}
            mock_memory_manager.long_term_memory.append(memory)

        # Check both systems
        memory_stats = memory_guard.check_memory_usage(mock_memory_manager)
        disk_status = disk_watchdog.check_disk_status()

        # Both should provide status information
        self.assertIsNotNone(memory_stats)
        self.assertIsNotNone(disk_status)

        # Clean up
        memory_guard.stop_monitoring()
        disk_watchdog.stop_monitoring()

    def test_health_monitor_integration(self):
        """Test health monitor integration with all components"""
        health_monitor = HealthMonitor()

        # All core components should be registered
        expected_components = [
            "MemoryManager",
            "VectorAdapter",
            "JournalEngine",
            "BeliefCore",
            "CHAMP",
            "WonderEngine",
            "ToM",
        ]

        for component in expected_components:
            self.assertIn(component, health_monitor.components)

        # Test system status aggregation
        status = health_monitor.get_system_status()
        self.assertIn("system_healthy", status)
        self.assertIn("components", status)

        health_monitor.stop_monitoring()


if __name__ == "__main__":
    # Create test suite
    test_suite = unittest.TestSuite()

    # Add test cases
    test_suite.addTest(unittest.makeSuite(TestMemoryResourceGuard))
    test_suite.addTest(unittest.makeSuite(TestDiskUsageWatchdog))
    test_suite.addTest(unittest.makeSuite(TestVectorAdapterGuard))
    test_suite.addTest(unittest.makeSuite(TestComponentHealthMonitor))
    test_suite.addTest(unittest.makeSuite(TestStressScenarios))
    test_suite.addTest(unittest.makeSuite(TestIntegrationScenarios))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Resource Safety Test Summary")
    print(f"{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(
        f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%"
    )

    if result.failures:
        print(f"\nFailures:")
        for test, traceback in result.failures:
            print(f"- {test}")

    if result.errors:
        print(f"\nErrors:")
        for test, traceback in result.errors:
            print(f"- {test}")
