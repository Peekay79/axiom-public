from __future__ import annotations

import os
import json
import time
from datetime import datetime


def _clear_dir(path: str) -> None:
	import shutil
	if os.path.isdir(path):
		shutil.rmtree(path, ignore_errors=True)
	os.makedirs(path, exist_ok=True)


def test_boot_normal(tmp_path, monkeypatch):
	# Arrange: fast deps become ready
	os.environ["COCKPIT_SIGNAL_DIR"] = str(tmp_path)
	_clear_dir(str(tmp_path))
	os.environ["BOOT_TOTAL_TIMEOUT_SEC"] = "10"
	os.environ["BOOT_PHASE_TIMEOUT_SEC"] = "2"
	os.environ["BOOT_RETRY_BACKOFF_SEC"] = "1"
	os.environ["BOOT_REQUIRE"] = "vector,journal"
	os.environ["BOOT_DEGRADED_MIN_REQUIRE"] = "journal"

	# Reload reporter to honor tmp signal dir
	import importlib
	import pods.cockpit.cockpit_reporter as reporter
	importlib.reload(reporter)
	from boot.phases import run_boot

	ready = {"vector": False, "journal": True}

	def deps():
		return dict(ready)

	def p0():
		return True

	def p1():
		return True

	def p2():
		return True

	# Make deps pass immediately
	ready["vector"] = True

	status = run_boot("vector", {"Phase0": p0, "Phase1": p1, "Phase2": p2}, deps)
	assert status["ready"] is True
	assert status["mode"] == "normal"

	# Verify boot_complete signal
	fp = tmp_path / "vector.boot_complete.json"
	assert fp.exists()
	data = json.loads(fp.read_text())
	assert data.get("data", {}).get("mode") == "normal"


def test_boot_degraded(tmp_path, monkeypatch):
	os.environ["COCKPIT_SIGNAL_DIR"] = str(tmp_path)
	_clear_dir(str(tmp_path))
	os.environ["BOOT_TOTAL_TIMEOUT_SEC"] = "1"
	os.environ["BOOT_RETRY_BACKOFF_SEC"] = "1"
	os.environ["BOOT_REQUIRE"] = "vector,journal"
	os.environ["BOOT_DEGRADED_MIN_REQUIRE"] = "journal"
	os.environ["BOOT_ALLOW_DEGRADED_ON_TIMEOUT"] = "true"

	# Reload reporter to honor tmp signal dir
	import importlib
	import pods.cockpit.cockpit_reporter as reporter
	importlib.reload(reporter)
	from boot.phases import run_boot

	def deps():
		return {"vector": False, "journal": True}

	status = run_boot("memory", {"Phase0": lambda: True}, deps)
	assert status["ready"] is True
	assert status["mode"] == "degraded"
	# degraded flag emits resilience.degraded
	# check boot_complete exists and aggregator marks degraded active
	fp = tmp_path / "memory.boot_complete.json"
	assert fp.exists()
	from pods.cockpit.cockpit_aggregator import aggregate_status
	ss = aggregate_status()
	res = ss.get("resilience", {}) or {}
	assert bool((res.get("degraded") or {}).get("active")) is True


def test_boot_safe(tmp_path, monkeypatch):
	os.environ["COCKPIT_SIGNAL_DIR"] = str(tmp_path)
	_clear_dir(str(tmp_path))
	os.environ["BOOT_TOTAL_TIMEOUT_SEC"] = "1"
	os.environ["BOOT_RETRY_BACKOFF_SEC"] = "1"
	os.environ["BOOT_REQUIRE"] = "vector,journal"
	os.environ["BOOT_DEGRADED_MIN_REQUIRE"] = "journal"
	os.environ["BOOT_ALLOW_DEGRADED_ON_TIMEOUT"] = "false"

	# Reload reporter to honor tmp signal dir
	import importlib
	import pods.cockpit.cockpit_reporter as reporter
	importlib.reload(reporter)
	from boot.phases import run_boot

	def deps():
		return {"vector": False, "journal": False}

	status = run_boot("llm", {"Phase0": lambda: True}, deps)
	assert status["ready"] is False
	assert status["mode"] == "safe"
	# boot_incomplete signal present
	fp = tmp_path / "llm.boot_incomplete.json"
	assert fp.exists()


def test_version_banner_emitted(tmp_path, monkeypatch):
	# Simulate a pod writing banner via reporter
	os.environ["COCKPIT_SIGNAL_DIR"] = str(tmp_path)
	_clear_dir(str(tmp_path))
	import importlib
	import pods.cockpit.cockpit_reporter as reporter
	importlib.reload(reporter)
	from pods.cockpit.cockpit_reporter import write_signal
	from boot.version_banner import collect_banner

	write_signal("vector", "version_banner", collect_banner())
	fp = tmp_path / "vector.version_banner.json"
	assert fp.exists()
	js = json.loads(fp.read_text())
	assert isinstance(js.get("data"), dict)
	# Snapshot includes banner under pods.vector.version_banner
	import pods.cockpit.cockpit_aggregator as agg
	importlib.reload(agg)
	ss = agg.aggregate_status()
	pods = ss.get("pods", {}) or {}
	assert isinstance((pods.get("vector", {}) or {}).get("version_banner"), dict)

