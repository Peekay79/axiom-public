#!/usr/bin/env python3
"""
component_health.py - Component health monitoring and fallback management for Axiom

This module provides comprehensive health monitoring for all core Axiom components,
including heartbeat checks, status logging, and automatic fallback mechanisms.
"""

import asyncio
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from . import (
    COMPONENT_TIMEOUT_THRESHOLD,
    HEALTH_CHECK_INTERVAL,
    ComponentHealthException,
    infra_logger,
)


class ComponentStatus(Enum):
    """Component health status enumeration"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    FALLBACK = "fallback"


@dataclass
class ComponentHealthMetrics:
    """Health metrics for a component"""

    name: str
    status: ComponentStatus = ComponentStatus.UNKNOWN
    last_heartbeat: Optional[datetime] = None
    last_check: Optional[datetime] = None
    response_time_ms: Optional[float] = None
    error_count: int = 0
    consecutive_failures: int = 0
    uptime_percentage: float = 100.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_critical: bool = True


class HealthMonitor:
    """
    Central health monitoring system for Axiom components.

    Features:
    - Periodic heartbeat checks for all registered components
    - Status logging every 30 seconds
    - Automatic fallback mode switching for critical components
    - Component-specific health check functions
    - Alert mechanisms for failures
    """

    def __init__(self, check_interval: int = HEALTH_CHECK_INTERVAL):
        """
        Initialize health monitor.

        Args:
            check_interval: Seconds between health checks
        """
        self.check_interval = check_interval
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

        # Component registry
        self.components: Dict[str, ComponentHealthMetrics] = {}
        self.health_checks: Dict[str, Callable] = {}
        self.fallback_handlers: Dict[str, Callable] = {}

        # Global health state
        self.system_healthy = True
        self.fallback_active = False
        self.last_status_log = None

        # Alert configuration
        self.webhook_url = None
        self.alert_threshold = 3  # consecutive failures before alert

        infra_logger.info("🏥 Component health monitor initialized")

        # Register core Axiom components
        self._register_core_components()

    def _register_core_components(self):
        """Register all core Axiom components for monitoring"""
        core_components = [
            ("MemoryManager", True),
            ("VectorAdapter", True),
            ("JournalEngine", True),
            ("BeliefCore", True),
            ("CHAMP", True),
            ("WonderEngine", False),
            ("ToM", False),
        ]

        for name, is_critical in core_components:
            self.register_component(name, is_critical=is_critical)
            self._setup_component_health_check(name)

    def register_component(
        self,
        name: str,
        health_check_func: Optional[Callable] = None,
        fallback_handler: Optional[Callable] = None,
        is_critical: bool = True,
    ):
        """
        Register a component for health monitoring.

        Args:
            name: Component name
            health_check_func: Function to check component health
            fallback_handler: Function to handle component failures
            is_critical: Whether component is critical to system operation
        """
        with self.lock:
            if name not in self.components:
                self.components[name] = ComponentHealthMetrics(
                    name=name, is_critical=is_critical
                )
                infra_logger.info(f"🏥 Registered component for monitoring: {name}")

            if health_check_func:
                self.health_checks[name] = health_check_func

            if fallback_handler:
                self.fallback_handlers[name] = fallback_handler

    def _setup_component_health_check(self, component_name: str):
        """Setup health check function for a core component"""
        if component_name == "MemoryManager":
            self.health_checks[component_name] = self._check_memory_manager_health
        elif component_name == "VectorAdapter":
            self.health_checks[component_name] = self._check_vector_adapter_health
            self.fallback_handlers[component_name] = self._enable_vector_fallback
        elif component_name == "JournalEngine":
            self.health_checks[component_name] = self._check_journal_engine_health
        elif component_name == "BeliefCore":
            self.health_checks[component_name] = self._check_belief_core_health
        elif component_name == "CHAMP":
            self.health_checks[component_name] = self._check_champ_health
        elif component_name == "WonderEngine":
            self.health_checks[component_name] = self._check_wonder_engine_health
        elif component_name == "ToM":
            self.health_checks[component_name] = self._check_tom_health

    async def _check_memory_manager_health(self) -> ComponentStatus:
        """Check MemoryManager health"""
        try:
            # Try to import and create instance
            from pods.memory.memory_manager import MemoryManager

            manager = MemoryManager()

            # Perform lightweight health check
            start_time = time.time()
            memories = manager.get_memories(limit=1)  # Minimal query
            response_time = (time.time() - start_time) * 1000

            if response_time > 5000:  # 5 second threshold
                return ComponentStatus.DEGRADED

            return ComponentStatus.HEALTHY

        except Exception as e:
            infra_logger.warning(f"🏥 MemoryManager health check failed: {e}")
            return ComponentStatus.UNHEALTHY

    async def _check_vector_adapter_health(self) -> ComponentStatus:
        """Check VectorAdapter health"""
        try:
            from pods.vector.vector_adapter import VectorAdapter

            adapter = VectorAdapter()

            # Test with minimal query
            start_time = time.time()
            results = adapter.search("test", top_k=1)
            response_time = (time.time() - start_time) * 1000

            if response_time > 10000:  # 10 second threshold
                return ComponentStatus.DEGRADED

            return ComponentStatus.HEALTHY

        except Exception as e:
            infra_logger.warning(f"🏥 VectorAdapter health check failed: {e}")
            return ComponentStatus.UNHEALTHY

    async def _check_journal_engine_health(self) -> ComponentStatus:
        """Check JournalEngine health"""
        try:
            from journal_engine import JournalEngine

            engine = JournalEngine()

            # Simple health ping
            if hasattr(engine, "health_check"):
                return (
                    ComponentStatus.HEALTHY
                    if engine.health_check()
                    else ComponentStatus.DEGRADED
                )

            return ComponentStatus.HEALTHY

        except Exception as e:
            infra_logger.warning(f"🏥 JournalEngine health check failed: {e}")
            return ComponentStatus.UNHEALTHY

    async def _check_belief_core_health(self) -> ComponentStatus:
        """Check BeliefCore health"""
        try:
            from belief_core import BeliefCore

            # BeliefCore doesn't have a simple instantiation, check if importable
            return ComponentStatus.HEALTHY

        except Exception as e:
            infra_logger.warning(f"🏥 BeliefCore health check failed: {e}")
            return ComponentStatus.UNHEALTHY

    async def _check_champ_health(self) -> ComponentStatus:
        """Check CHAMP decision engine health"""
        try:
            from champ_decision_engine import ChampDecisionEngine

            champ = ChampDecisionEngine()

            # Test basic functionality
            test_metrics = champ.ChampMetrics(confidence=0.5, payoff=0.5, tempo=0.5)
            score = champ.calculate_champ_score(test_metrics)

            if isinstance(score, (int, float)) and 0 <= score <= 1:
                return ComponentStatus.HEALTHY
            else:
                return ComponentStatus.DEGRADED

        except Exception as e:
            infra_logger.warning(f"🏥 CHAMP health check failed: {e}")
            return ComponentStatus.UNHEALTHY

    async def _check_wonder_engine_health(self) -> ComponentStatus:
        """Check WonderEngine health"""
        try:
            from wonder_engine import WonderEngine

            engine = WonderEngine()
            return ComponentStatus.HEALTHY

        except Exception as e:
            infra_logger.debug(f"🏥 WonderEngine health check failed: {e}")
            return ComponentStatus.UNHEALTHY

    async def _check_tom_health(self) -> ComponentStatus:
        """Check Theory of Mind engine health"""
        try:
            from axiom.theory_of_mind.engine import simulate_perspective

            return ComponentStatus.HEALTHY

        except Exception as e:
            infra_logger.debug(f"🏥 ToM health check failed: {e}")
            return ComponentStatus.UNHEALTHY

    def _enable_vector_fallback(self):
        """Enable fallback mode for VectorAdapter"""
        try:
            infra_logger.warning("🔄 Enabling VectorAdapter fallback mode")
            # This would typically set a flag in the VectorAdapter to use local fallback
            # For now, just log the event
            self.fallback_active = True

        except Exception as e:
            infra_logger.error(f"❌ Failed to enable VectorAdapter fallback: {e}")

    async def check_component_health(self, name: str) -> ComponentStatus:
        """
        Check health of a specific component.

        Args:
            name: Component name

        Returns:
            ComponentStatus indicating health
        """
        if name not in self.components:
            infra_logger.warning(f"🏥 Unknown component: {name}")
            return ComponentStatus.UNKNOWN

        component = self.components[name]

        try:
            # Run health check if available
            if name in self.health_checks:
                start_time = time.time()
                status = await self.health_checks[name]()
                response_time = (time.time() - start_time) * 1000

                component.response_time_ms = response_time
                component.last_check = datetime.now(timezone.utc)

                # Update failure tracking
                if status == ComponentStatus.HEALTHY:
                    component.consecutive_failures = 0
                else:
                    component.consecutive_failures += 1
                    component.error_count += 1

                component.status = status

                # Trigger fallback if component has been unhealthy too long
                if (
                    status == ComponentStatus.UNHEALTHY
                    and component.consecutive_failures >= self.alert_threshold
                    and name in self.fallback_handlers
                ):

                    infra_logger.warning(
                        f"🔄 Triggering fallback for {name} after {component.consecutive_failures} failures"
                    )
                    self.fallback_handlers[name]()
                    component.status = ComponentStatus.FALLBACK

                return status
            else:
                # No health check function, assume healthy
                component.status = ComponentStatus.HEALTHY
                component.last_check = datetime.now(timezone.utc)
                return ComponentStatus.HEALTHY

        except Exception as e:
            infra_logger.error(f"🏥 Health check error for {name}: {e}")
            component.status = ComponentStatus.UNHEALTHY
            component.error_count += 1
            component.consecutive_failures += 1
            return ComponentStatus.UNHEALTHY

    async def check_all_components(self) -> Dict[str, ComponentStatus]:
        """Check health of all registered components"""
        results = {}

        with self.lock:
            component_names = list(self.components.keys())

        # Run health checks in parallel
        tasks = []
        for name in component_names:
            task = asyncio.create_task(self.check_component_health(name))
            tasks.append((name, task))

        for name, task in tasks:
            try:
                status = await task
                results[name] = status
            except Exception as e:
                infra_logger.error(f"🏥 Health check task failed for {name}: {e}")
                results[name] = ComponentStatus.UNHEALTHY

        # Update system health
        critical_components = [
            name for name, comp in self.components.items() if comp.is_critical
        ]
        critical_unhealthy = [
            name
            for name in critical_components
            if results.get(name) == ComponentStatus.UNHEALTHY
        ]

        self.system_healthy = len(critical_unhealthy) == 0

        return results

    def heartbeat(self, component_name: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Record a heartbeat from a component.

        Args:
            component_name: Name of the component
            metadata: Optional metadata about component state
        """
        if component_name not in self.components:
            self.register_component(component_name)

        with self.lock:
            component = self.components[component_name]
            component.last_heartbeat = datetime.now(timezone.utc)
            if metadata:
                component.metadata.update(metadata)

    def get_component_status(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed status for a component"""
        if name not in self.components:
            return None

        with self.lock:
            component = self.components[name]
            return {
                "name": component.name,
                "status": component.status.value,
                "last_heartbeat": (
                    component.last_heartbeat.isoformat()
                    if component.last_heartbeat
                    else None
                ),
                "last_check": (
                    component.last_check.isoformat() if component.last_check else None
                ),
                "response_time_ms": component.response_time_ms,
                "error_count": component.error_count,
                "consecutive_failures": component.consecutive_failures,
                "uptime_percentage": component.uptime_percentage,
                "is_critical": component.is_critical,
                "metadata": component.metadata,
            }

    def is_component_healthy(self, name: str) -> bool:
        """Check if a specific component is healthy"""
        if name not in self.components:
            return False

        component = self.components[name]
        return component.status in [ComponentStatus.HEALTHY, ComponentStatus.DEGRADED]

    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system health status"""
        with self.lock:
            component_statuses = {
                name: comp.status.value for name, comp in self.components.items()
            }

            healthy_count = sum(
                1
                for status in component_statuses.values()
                if status == ComponentStatus.HEALTHY.value
            )
            total_count = len(component_statuses)

            return {
                "system_healthy": self.system_healthy,
                "fallback_active": self.fallback_active,
                "monitoring": self.monitoring,
                "component_count": total_count,
                "healthy_count": healthy_count,
                "health_percentage": (
                    round((healthy_count / total_count) * 100, 1)
                    if total_count > 0
                    else 0
                ),
                "last_status_log": (
                    self.last_status_log.isoformat() if self.last_status_log else None
                ),
                "components": component_statuses,
            }

    def start_monitoring(self):
        """Start background health monitoring"""
        if self.monitoring:
            infra_logger.warning("🏥 Health monitoring already running")
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True
        )
        self.monitor_thread.start()
        infra_logger.info(
            f"🏥 Started component health monitoring (interval: {self.check_interval}s)"
        )

    def stop_monitoring(self):
        """Stop background health monitoring"""
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        infra_logger.info("🏥 Stopped component health monitoring")

    def _monitoring_loop(self):
        """Background monitoring loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self.monitoring:
            try:
                # Run health checks
                results = loop.run_until_complete(self.check_all_components())

                # Log status summary
                self._log_status_summary(results)

                time.sleep(self.check_interval)

            except Exception as e:
                infra_logger.error(f"❌ Health monitoring error: {e}")
                time.sleep(self.check_interval)

        loop.close()

    def _log_status_summary(self, results: Dict[str, ComponentStatus]):
        """Log summary of component health status"""
        self.last_status_log = datetime.now(timezone.utc)

        healthy = [
            name
            for name, status in results.items()
            if status == ComponentStatus.HEALTHY
        ]
        degraded = [
            name
            for name, status in results.items()
            if status == ComponentStatus.DEGRADED
        ]
        unhealthy = [
            name
            for name, status in results.items()
            if status == ComponentStatus.UNHEALTHY
        ]
        fallback = [
            name
            for name, status in results.items()
            if status == ComponentStatus.FALLBACK
        ]

        status_msg = f"🏥 Component Health: {len(healthy)} healthy, {len(degraded)} degraded, {len(unhealthy)} unhealthy"

        if fallback:
            status_msg += f", {len(fallback)} in fallback"

        if unhealthy:
            status_msg += f" | Unhealthy: {', '.join(unhealthy)}"

        if degraded:
            status_msg += f" | Degraded: {', '.join(degraded)}"

        if len(unhealthy) > 0:
            infra_logger.warning(status_msg)
        else:
            infra_logger.info(status_msg)


# Global health monitor instance
_health_monitor = None


def get_health_monitor() -> HealthMonitor:
    """Get global health monitor instance (singleton pattern)"""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor()
        _health_monitor.start_monitoring()
    return _health_monitor


def is_component_healthy(name: str) -> bool:
    """Convenience function to check if a component is healthy"""
    return get_health_monitor().is_component_healthy(name)


def get_component_status(name: str) -> Optional[Dict[str, Any]]:
    """Convenience function to get component status"""
    return get_health_monitor().get_component_status(name)


def heartbeat(component_name: str, metadata: Optional[Dict[str, Any]] = None):
    """Convenience function to send component heartbeat"""
    get_health_monitor().heartbeat(component_name, metadata)


def get_system_status() -> Dict[str, Any]:
    """Convenience function to get system status"""
    return get_health_monitor().get_system_status()


# Auto-start monitoring when module is imported
def _auto_start_monitoring():
    """Auto-start health monitoring in background"""
    try:
        get_health_monitor()  # This will create and start monitoring
    except Exception as e:
        infra_logger.error(f"❌ Failed to auto-start health monitoring: {e}")


# Start monitoring on module import
_auto_start_monitoring()
