#!/usr/bin/env python3
"""
test_component_health.py - Test suite for component health monitoring

This module specifically tests component health checks, failure detection,
heartbeat mechanisms, and fallback activation for Axiom components.
"""

import asyncio
import os

# Add infra directory to path for testing
import sys
import threading
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from infra.component_health import (
    ComponentHealthMetrics,
    ComponentStatus,
    HealthMonitor,
    get_component_status,
    get_health_monitor,
    get_system_status,
    heartbeat,
    is_component_healthy,
)


class TestComponentHealthMetrics(unittest.TestCase):
    """Test component health metrics tracking"""

    def test_metrics_initialization(self):
        """Test component metrics initialization"""
        metrics = ComponentHealthMetrics(name="TestComponent")

        self.assertEqual(metrics.name, "TestComponent")
        self.assertEqual(metrics.status, ComponentStatus.UNKNOWN)
        self.assertIsNone(metrics.last_heartbeat)
        self.assertEqual(metrics.error_count, 0)
        self.assertTrue(metrics.is_critical)

    def test_metrics_update(self):
        """Test updating component metrics"""
        metrics = ComponentHealthMetrics(name="TestComponent")

        # Update metrics
        metrics.status = ComponentStatus.HEALTHY
        metrics.last_heartbeat = datetime.now(timezone.utc)
        metrics.response_time_ms = 250.5
        metrics.error_count = 1

        self.assertEqual(metrics.status, ComponentStatus.HEALTHY)
        self.assertIsNotNone(metrics.last_heartbeat)
        self.assertEqual(metrics.response_time_ms, 250.5)
        self.assertEqual(metrics.error_count, 1)


class TestHealthMonitor(unittest.TestCase):
    """Test health monitor functionality"""

    def setUp(self):
        """Set up test environment"""
        self.health_monitor = HealthMonitor(check_interval=0.5)

    def tearDown(self):
        """Clean up test environment"""
        self.health_monitor.stop_monitoring()

    def test_component_registration(self):
        """Test registering components for monitoring"""
        # Register a critical component
        self.health_monitor.register_component("CriticalComponent", is_critical=True)

        # Register a non-critical component
        self.health_monitor.register_component(
            "NonCriticalComponent", is_critical=False
        )

        self.assertIn("CriticalComponent", self.health_monitor.components)
        self.assertIn("NonCriticalComponent", self.health_monitor.components)

        self.assertTrue(self.health_monitor.components["CriticalComponent"].is_critical)
        self.assertFalse(
            self.health_monitor.components["NonCriticalComponent"].is_critical
        )

    def test_health_check_function_registration(self):
        """Test registering health check functions"""

        def mock_health_check():
            return ComponentStatus.HEALTHY

        self.health_monitor.register_component(
            "TestComponent", health_check_func=mock_health_check
        )

        self.assertIn("TestComponent", self.health_monitor.health_checks)
        self.assertEqual(
            self.health_monitor.health_checks["TestComponent"], mock_health_check
        )

    def test_fallback_handler_registration(self):
        """Test registering fallback handlers"""

        def mock_fallback_handler():
            pass

        self.health_monitor.register_component(
            "TestComponent", fallback_handler=mock_fallback_handler
        )

        self.assertIn("TestComponent", self.health_monitor.fallback_handlers)
        self.assertEqual(
            self.health_monitor.fallback_handlers["TestComponent"],
            mock_fallback_handler,
        )

    def test_heartbeat_recording(self):
        """Test heartbeat recording functionality"""
        # Send heartbeat
        self.health_monitor.heartbeat("TestComponent", {"test_key": "test_value"})

        # Component should be auto-registered
        self.assertIn("TestComponent", self.health_monitor.components)

        component = self.health_monitor.components["TestComponent"]
        self.assertIsNotNone(component.last_heartbeat)
        self.assertEqual(component.metadata["test_key"], "test_value")

    def test_component_health_check_execution(self):
        """Test executing health checks for components"""

        # Mock health check that returns healthy
        async def healthy_check():
            return ComponentStatus.HEALTHY

        self.health_monitor.register_component(
            "HealthyComponent", health_check_func=healthy_check
        )

        # Run health check
        status = asyncio.run(
            self.health_monitor.check_component_health("HealthyComponent")
        )
        self.assertEqual(status, ComponentStatus.HEALTHY)

        # Check metrics were updated
        component = self.health_monitor.components["HealthyComponent"]
        self.assertEqual(component.status, ComponentStatus.HEALTHY)
        self.assertIsNotNone(component.last_check)
        self.assertEqual(component.consecutive_failures, 0)

    def test_component_health_check_failure(self):
        """Test handling health check failures"""

        # Mock health check that fails
        async def failing_check():
            raise Exception("Health check failed")

        self.health_monitor.register_component(
            "FailingComponent", health_check_func=failing_check
        )

        # Run health check
        status = asyncio.run(
            self.health_monitor.check_component_health("FailingComponent")
        )
        self.assertEqual(status, ComponentStatus.UNHEALTHY)

        # Check failure tracking
        component = self.health_monitor.components["FailingComponent"]
        self.assertEqual(component.status, ComponentStatus.UNHEALTHY)
        self.assertEqual(component.consecutive_failures, 1)
        self.assertEqual(component.error_count, 1)

    def test_multiple_component_health_checks(self):
        """Test checking health of multiple components"""

        # Register multiple components with different health states
        async def healthy_check():
            return ComponentStatus.HEALTHY

        async def degraded_check():
            return ComponentStatus.DEGRADED

        async def unhealthy_check():
            return ComponentStatus.UNHEALTHY

        self.health_monitor.register_component(
            "Healthy", health_check_func=healthy_check
        )
        self.health_monitor.register_component(
            "Degraded", health_check_func=degraded_check
        )
        self.health_monitor.register_component(
            "Unhealthy", health_check_func=unhealthy_check, is_critical=True
        )

        # Check all components
        results = asyncio.run(self.health_monitor.check_all_components())

        self.assertEqual(results["Healthy"], ComponentStatus.HEALTHY)
        self.assertEqual(results["Degraded"], ComponentStatus.DEGRADED)
        self.assertEqual(results["Unhealthy"], ComponentStatus.UNHEALTHY)

        # System should be unhealthy due to critical component being unhealthy
        self.assertFalse(self.health_monitor.system_healthy)

    def test_fallback_activation(self):
        """Test automatic fallback activation"""
        fallback_called = []

        def mock_fallback():
            fallback_called.append(True)

        # Mock health check that consistently fails
        failure_count = 0

        async def failing_check():
            nonlocal failure_count
            failure_count += 1
            raise Exception(f"Failure {failure_count}")

        self.health_monitor.register_component(
            "FailingComponent",
            health_check_func=failing_check,
            fallback_handler=mock_fallback,
        )

        # Run health checks repeatedly to trigger fallback
        for _ in range(5):  # More than the alert threshold
            asyncio.run(self.health_monitor.check_component_health("FailingComponent"))

        # Fallback should have been called
        self.assertTrue(len(fallback_called) > 0)

        # Component should be in fallback status
        component = self.health_monitor.components["FailingComponent"]
        self.assertEqual(component.status, ComponentStatus.FALLBACK)

    def test_system_status_aggregation(self):
        """Test system health status aggregation"""

        # Register mixed health components
        async def healthy_check():
            return ComponentStatus.HEALTHY

        async def unhealthy_check():
            return ComponentStatus.UNHEALTHY

        self.health_monitor.register_component(
            "Healthy1", health_check_func=healthy_check, is_critical=True
        )
        self.health_monitor.register_component(
            "Healthy2", health_check_func=healthy_check, is_critical=False
        )
        self.health_monitor.register_component(
            "Unhealthy1", health_check_func=unhealthy_check, is_critical=False
        )

        # Check all components
        asyncio.run(self.health_monitor.check_all_components())

        # Get system status
        status = self.health_monitor.get_system_status()

        self.assertIn("system_healthy", status)
        self.assertIn("component_count", status)
        self.assertIn("healthy_count", status)
        self.assertIn("health_percentage", status)
        self.assertIn("components", status)

        # Should be healthy since critical components are healthy
        self.assertTrue(status["system_healthy"])
        self.assertEqual(status["component_count"], 3)
        self.assertEqual(status["healthy_count"], 2)

    def test_monitoring_loop(self):
        """Test background monitoring loop"""
        check_count = 0

        async def counting_check():
            nonlocal check_count
            check_count += 1
            return ComponentStatus.HEALTHY

        self.health_monitor.register_component(
            "MonitoredComponent", health_check_func=counting_check
        )

        # Start monitoring
        self.health_monitor.start_monitoring()

        # Wait for a few monitoring cycles
        time.sleep(2)

        # Stop monitoring
        self.health_monitor.stop_monitoring()

        # Should have run multiple checks
        self.assertGreater(check_count, 1)


class TestCoreComponentHealthChecks(unittest.TestCase):
    """Test health checks for core Axiom components"""

    def setUp(self):
        """Set up test environment"""
        self.health_monitor = HealthMonitor(check_interval=1)

    def tearDown(self):
        """Clean up test environment"""
        self.health_monitor.stop_monitoring()

    def test_memory_manager_health_check(self):
        """Test MemoryManager health check"""
        with patch("infra.component_health.MemoryManager") as mock_manager:
            # Mock successful memory manager
            mock_instance = Mock()
            mock_instance.get_memories.return_value = []
            mock_manager.return_value = mock_instance

            # Run health check
            status = asyncio.run(self.health_monitor._check_memory_manager_health())
            self.assertEqual(status, ComponentStatus.HEALTHY)

    def test_memory_manager_health_check_timeout(self):
        """Test MemoryManager health check with slow response"""
        with patch("infra.component_health.MemoryManager") as mock_manager:
            # Mock slow memory manager
            mock_instance = Mock()

            def slow_get_memories(*args, **kwargs):
                time.sleep(6)  # Longer than 5 second threshold
                return []

            mock_instance.get_memories = slow_get_memories
            mock_manager.return_value = mock_instance

            # Run health check
            status = asyncio.run(self.health_monitor._check_memory_manager_health())
            self.assertEqual(status, ComponentStatus.DEGRADED)

    def test_vector_adapter_health_check(self):
        """Test VectorAdapter health check"""
        with patch("infra.component_health.VectorAdapter") as mock_adapter:
            # Mock successful vector adapter
            mock_instance = Mock()
            mock_instance.search.return_value = []
            mock_adapter.return_value = mock_instance

            # Run health check
            status = asyncio.run(self.health_monitor._check_vector_adapter_health())
            self.assertEqual(status, ComponentStatus.HEALTHY)

    def test_vector_adapter_health_check_failure(self):
        """Test VectorAdapter health check failure"""
        with patch("infra.component_health.VectorAdapter") as mock_adapter:
            # Mock failing vector adapter
            mock_adapter.side_effect = Exception("Connection failed")

            # Run health check
            status = asyncio.run(self.health_monitor._check_vector_adapter_health())
            self.assertEqual(status, ComponentStatus.UNHEALTHY)

    def test_champ_health_check(self):
        """Test CHAMP decision engine health check"""
        with patch("infra.component_health.ChampDecisionEngine") as mock_champ:
            # Mock successful CHAMP engine
            mock_instance = Mock()
            mock_metrics = Mock()
            mock_instance.ChampMetrics = Mock(return_value=mock_metrics)
            mock_instance.calculate_champ_score.return_value = 0.75
            mock_champ.return_value = mock_instance

            # Run health check
            status = asyncio.run(self.health_monitor._check_champ_health())
            self.assertEqual(status, ComponentStatus.HEALTHY)

    def test_champ_health_check_invalid_score(self):
        """Test CHAMP health check with invalid score"""
        with patch("infra.component_health.ChampDecisionEngine") as mock_champ:
            # Mock CHAMP with invalid score
            mock_instance = Mock()
            mock_metrics = Mock()
            mock_instance.ChampMetrics = Mock(return_value=mock_metrics)
            mock_instance.calculate_champ_score.return_value = -1  # Invalid score
            mock_champ.return_value = mock_instance

            # Run health check
            status = asyncio.run(self.health_monitor._check_champ_health())
            self.assertEqual(status, ComponentStatus.DEGRADED)


class TestComponentHangDetection(unittest.TestCase):
    """Test detection of component hangs and timeouts"""

    def setUp(self):
        """Set up test environment"""
        self.health_monitor = HealthMonitor(check_interval=0.5)

    def tearDown(self):
        """Clean up test environment"""
        self.health_monitor.stop_monitoring()

    def test_hanging_component_detection(self):
        """Test detection of hanging components"""

        # Mock a component that hangs
        async def hanging_check():
            await asyncio.sleep(30)  # Hang for 30 seconds
            return ComponentStatus.HEALTHY

        self.health_monitor.register_component(
            "HangingComponent", health_check_func=hanging_check
        )

        # Run health check with timeout
        start_time = time.time()
        status = asyncio.run(
            asyncio.wait_for(
                self.health_monitor.check_component_health("HangingComponent"),
                timeout=2.0,
            )
        )
        elapsed = time.time() - start_time

        # Should timeout and return before hanging completes
        self.assertLess(elapsed, 5.0)

    def test_intermittent_failure_detection(self):
        """Test detection of intermittent component failures"""
        failure_count = 0

        async def intermittent_check():
            nonlocal failure_count
            failure_count += 1
            if failure_count % 3 == 0:  # Fail every 3rd check
                raise Exception("Intermittent failure")
            return ComponentStatus.HEALTHY

        self.health_monitor.register_component(
            "IntermittentComponent", health_check_func=intermittent_check
        )

        # Run multiple health checks
        results = []
        for _ in range(6):
            status = asyncio.run(
                self.health_monitor.check_component_health("IntermittentComponent")
            )
            results.append(status)

        # Should have both healthy and unhealthy results
        self.assertIn(ComponentStatus.HEALTHY, results)
        self.assertIn(ComponentStatus.UNHEALTHY, results)

        # Component should track failures
        component = self.health_monitor.components["IntermittentComponent"]
        self.assertGreater(component.error_count, 0)

    def test_response_time_tracking(self):
        """Test tracking of component response times"""

        async def timed_check():
            await asyncio.sleep(0.1)  # Small delay
            return ComponentStatus.HEALTHY

        self.health_monitor.register_component(
            "TimedComponent", health_check_func=timed_check
        )

        # Run health check
        asyncio.run(self.health_monitor.check_component_health("TimedComponent"))

        # Should have recorded response time
        component = self.health_monitor.components["TimedComponent"]
        self.assertIsNotNone(component.response_time_ms)
        self.assertGreater(component.response_time_ms, 50)  # At least 50ms due to sleep


class TestGlobalHealthFunctions(unittest.TestCase):
    """Test global convenience functions for health monitoring"""

    def test_singleton_health_monitor(self):
        """Test global health monitor singleton"""
        monitor1 = get_health_monitor()
        monitor2 = get_health_monitor()

        # Should return same instance
        self.assertIs(monitor1, monitor2)

        # Clean up
        monitor1.stop_monitoring()

    def test_is_component_healthy_function(self):
        """Test is_component_healthy convenience function"""
        monitor = get_health_monitor()

        # Register a healthy component
        async def healthy_check():
            return ComponentStatus.HEALTHY

        monitor.register_component("TestComponent", health_check_func=healthy_check)

        # Run health check first
        asyncio.run(monitor.check_component_health("TestComponent"))

        # Test convenience function
        self.assertTrue(is_component_healthy("TestComponent"))

        # Test with unknown component
        self.assertFalse(is_component_healthy("UnknownComponent"))

        # Clean up
        monitor.stop_monitoring()

    def test_get_component_status_function(self):
        """Test get_component_status convenience function"""
        monitor = get_health_monitor()

        # Register and check a component
        async def healthy_check():
            return ComponentStatus.HEALTHY

        monitor.register_component("TestComponent", health_check_func=healthy_check)
        asyncio.run(monitor.check_component_health("TestComponent"))

        # Test convenience function
        status = get_component_status("TestComponent")

        self.assertIsNotNone(status)
        self.assertEqual(status["name"], "TestComponent")
        self.assertEqual(status["status"], ComponentStatus.HEALTHY.value)

        # Test with unknown component
        self.assertIsNone(get_component_status("UnknownComponent"))

        # Clean up
        monitor.stop_monitoring()

    def test_heartbeat_function(self):
        """Test heartbeat convenience function"""
        monitor = get_health_monitor()

        # Send heartbeat
        heartbeat("TestComponent", {"key": "value"})

        # Component should be registered and have heartbeat
        self.assertIn("TestComponent", monitor.components)
        component = monitor.components["TestComponent"]
        self.assertIsNotNone(component.last_heartbeat)
        self.assertEqual(component.metadata["key"], "value")

        # Clean up
        monitor.stop_monitoring()

    def test_get_system_status_function(self):
        """Test get_system_status convenience function"""
        monitor = get_health_monitor()

        # Register some components
        monitor.register_component("Component1", is_critical=True)
        monitor.register_component("Component2", is_critical=False)

        # Test convenience function
        status = get_system_status()

        self.assertIsInstance(status, dict)
        self.assertIn("system_healthy", status)
        self.assertIn("component_count", status)
        self.assertEqual(status["component_count"], 9)  # 7 core + 2 test components

        # Clean up
        monitor.stop_monitoring()


if __name__ == "__main__":
    # Create test suite
    test_suite = unittest.TestSuite()

    # Add test cases
    test_suite.addTest(unittest.makeSuite(TestComponentHealthMetrics))
    test_suite.addTest(unittest.makeSuite(TestHealthMonitor))
    test_suite.addTest(unittest.makeSuite(TestCoreComponentHealthChecks))
    test_suite.addTest(unittest.makeSuite(TestComponentHangDetection))
    test_suite.addTest(unittest.makeSuite(TestGlobalHealthFunctions))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Component Health Test Summary")
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

    print(f"\nComponent Health Tests completed!")
