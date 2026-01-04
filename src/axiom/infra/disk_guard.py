#!/usr/bin/env python3
"""
disk_guard.py - Disk usage monitoring and alerting for Axiom

This module monitors disk usage in the current working directory and triggers
warnings when usage exceeds safe thresholds or available space becomes low.
"""

import os
import shutil
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from . import (
    DISK_CRITICAL_THRESHOLD,
    DISK_WARNING_THRESHOLD,
    DiskSpaceException,
    infra_logger,
)


class DiskUsageWatchdog:
    """
    Monitor disk usage and trigger warnings when limits are approached.

    Features:
    - Monitors current working directory disk usage
    - Triggers warnings at 80% usage or <500MB free space
    - Exposes is_disk_stressed() for other modules
    - Thread-safe operation with background monitoring
    """

    def __init__(self, check_interval: int = 60):
        """
        Initialize disk usage watchdog.

        Args:
            check_interval: Seconds between disk usage checks
        """
        self.check_interval = check_interval
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

        # Disk usage state
        self.last_check = None
        self.current_usage = None
        self.available_space_mb = None
        self.is_stressed = False
        self.warning_count = 0
        self.last_warning_time = None

        # Warning throttling (don't spam warnings)
        self.warning_interval = 300  # 5 minutes between repeated warnings

        infra_logger.info("📊 Disk usage watchdog initialized")

    def get_disk_usage(self, path: str = ".") -> Tuple[float, int, int]:
        """
        Get disk usage statistics for given path.

        Args:
            path: Directory path to check (default: current directory)

        Returns:
            Tuple of (usage_percentage, available_mb, total_mb)
        """
        try:
            total, used, free = shutil.disk_usage(path)
            usage_percentage = used / total if total > 0 else 0.0
            available_mb = free // (1024 * 1024)
            total_mb = total // (1024 * 1024)

            return usage_percentage, available_mb, total_mb

        except Exception as e:
            infra_logger.error(f"❌ Failed to get disk usage for {path}: {e}")
            return 0.0, 0, 0

    def check_disk_status(self, path: str = ".") -> Dict[str, any]:
        """
        Check current disk status and update internal state.

        Args:
            path: Directory path to check

        Returns:
            Dict with disk status information
        """
        with self.lock:
            usage_pct, available_mb, total_mb = self.get_disk_usage(path)
            used_mb = total_mb - available_mb

            self.last_check = datetime.now(timezone.utc)
            self.current_usage = usage_pct
            self.available_space_mb = available_mb

            # Determine stress level
            is_over_threshold = usage_pct > DISK_WARNING_THRESHOLD
            is_low_space = available_mb < DISK_CRITICAL_THRESHOLD
            self.is_stressed = is_over_threshold or is_low_space

            # Generate warnings if needed
            should_warn = self.is_stressed and self._should_send_warning()
            if should_warn:
                self._send_disk_warning(usage_pct, available_mb, total_mb)

            status = {
                "timestamp": self.last_check.isoformat(),
                "usage_percentage": round(usage_pct * 100, 2),
                "available_mb": available_mb,
                "used_mb": used_mb,
                "total_mb": total_mb,
                "is_stressed": self.is_stressed,
                "warning_triggered": should_warn,
                "path": os.path.abspath(path),
            }

            infra_logger.debug(
                f"📊 Disk status: {usage_pct:.1%} used, {available_mb}MB free"
            )
            return status

    def _should_send_warning(self) -> bool:
        """Check if enough time has passed since last warning"""
        if not self.last_warning_time:
            return True

        time_since_warning = time.time() - self.last_warning_time
        return time_since_warning >= self.warning_interval

    def _send_disk_warning(self, usage_pct: float, available_mb: int, total_mb: int):
        """Send disk space warning and update warning state"""
        self.warning_count += 1
        self.last_warning_time = time.time()

        warning_msg = (
            f"⚠️ DISK SPACE WARNING #{self.warning_count}: "
            f"{usage_pct:.1%} used, {available_mb}MB available ({total_mb}MB total)"
        )

        if usage_pct > DISK_WARNING_THRESHOLD:
            warning_msg += f" - Usage exceeded {DISK_WARNING_THRESHOLD:.0%} threshold"

        if available_mb < DISK_CRITICAL_THRESHOLD:
            warning_msg += f" - Available space below {DISK_CRITICAL_THRESHOLD}MB critical threshold"

        infra_logger.warning(warning_msg)

        # Log detailed disk usage breakdown
        self._log_disk_breakdown()

    def _log_disk_breakdown(self):
        """Log detailed breakdown of disk usage for debugging"""
        try:
            cwd = os.getcwd()
            infra_logger.info(f"📁 Current working directory: {cwd}")

            # Check sizes of major directories
            for item in os.listdir("."):
                if os.path.isdir(item):
                    try:
                        size_mb = self._get_directory_size_mb(item)
                        infra_logger.info(f"📁 Directory '{item}': {size_mb}MB")
                    except Exception as e:
                        infra_logger.debug(f"Could not get size for {item}: {e}")

        except Exception as e:
            infra_logger.debug(f"Failed to log disk breakdown: {e}")

    def _get_directory_size_mb(self, path: str) -> int:
        """Get directory size in MB (sampling for performance)"""
        total_size = 0
        file_count = 0
        max_files = 1000  # Limit sampling for performance

        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                if file_count >= max_files:
                    break
                try:
                    filepath = os.path.join(dirpath, filename)
                    total_size += os.path.getsize(filepath)
                    file_count += 1
                except (OSError, IOError):
                    continue
            if file_count >= max_files:
                break

        size_mb = total_size // (1024 * 1024)
        if file_count >= max_files:
            # Extrapolate if we hit the sampling limit
            estimated_total = size_mb * 2  # Rough estimate
            infra_logger.debug(
                f"Directory size estimated (sampled {file_count} files): ~{estimated_total}MB"
            )
            return estimated_total

        return size_mb

    def start_monitoring(self):
        """Start background disk monitoring thread"""
        if self.monitoring:
            infra_logger.warning("📊 Disk monitoring already running")
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True
        )
        self.monitor_thread.start()
        infra_logger.info(
            f"📊 Started disk usage monitoring (interval: {self.check_interval}s)"
        )

    def stop_monitoring(self):
        """Stop background disk monitoring"""
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        infra_logger.info("📊 Stopped disk usage monitoring")

    def _monitoring_loop(self):
        """Background monitoring loop"""
        while self.monitoring:
            try:
                self.check_disk_status()
                time.sleep(self.check_interval)
            except Exception as e:
                infra_logger.error(f"❌ Disk monitoring error: {e}")
                time.sleep(self.check_interval)

    def is_disk_stressed(self) -> bool:
        """
        Check if disk is currently under stress.

        Returns:
            True if disk usage is high or available space is low
        """
        # Force a check if we haven't checked recently
        if (
            not self.last_check
            or (datetime.now(timezone.utc) - self.last_check).seconds > 60
        ):
            self.check_disk_status()

        return self.is_stressed

    def get_status(self) -> Dict[str, any]:
        """Get current disk status information"""
        with self.lock:
            return {
                "is_monitoring": self.monitoring,
                "last_check": self.last_check.isoformat() if self.last_check else None,
                "current_usage_pct": (
                    round(self.current_usage * 100, 2) if self.current_usage else None
                ),
                "available_space_mb": self.available_space_mb,
                "is_stressed": self.is_stressed,
                "warning_count": self.warning_count,
                "last_warning_time": self.last_warning_time,
            }


# Global disk watchdog instance
_disk_watchdog = None


def get_disk_watchdog() -> DiskUsageWatchdog:
    """Get global disk watchdog instance (singleton pattern)"""
    global _disk_watchdog
    if _disk_watchdog is None:
        _disk_watchdog = DiskUsageWatchdog()
        _disk_watchdog.start_monitoring()
    return _disk_watchdog


def is_disk_stressed() -> bool:
    """Convenience function to check if disk is stressed"""
    return get_disk_watchdog().is_disk_stressed()


def get_disk_status() -> Dict[str, any]:
    """Convenience function to get disk status"""
    watchdog = get_disk_watchdog()
    status = watchdog.check_disk_status()
    status.update(watchdog.get_status())
    return status


# Auto-start monitoring when module is imported
def _auto_start_monitoring():
    """Auto-start disk monitoring in background"""
    try:
        get_disk_watchdog()  # This will create and start monitoring
    except Exception as e:
        infra_logger.error(f"❌ Failed to auto-start disk monitoring: {e}")


# Start monitoring on module import
_auto_start_monitoring()
