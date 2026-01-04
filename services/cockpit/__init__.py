"""Project Cockpit (Phase 1)

Lightweight observability helpers for Axiom pods.

Modules:
- cockpit_reporter: Per‑pod signaling helpers (ready/error/heartbeat/custom JSON)
- cockpit_aggregator: CLI to summarize pod health from signal files

Signals are written under the directory indicated by the environment variable
COCKPIT_SIGNAL_DIR (defaults to "axiom_boot").
"""

