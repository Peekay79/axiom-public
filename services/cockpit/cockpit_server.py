#!/usr/bin/env python3
"""
Project Cockpit – Status Server (Phase 2)

Tiny Flask app exposing GET /status/cockpit returning aggregate_status() JSON.
Binding via COCKPIT_BIND env (default "0.0.0.0:8088").

Fail-closed: on aggregator error, returns 503 with {"error":"unavailable"}.
"""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify


def _aggregate_safe():
    try:
        from .cockpit_aggregator import aggregate_status

        return aggregate_status()
    except Exception:
        return None


app = Flask(__name__)


@app.get("/status/cockpit")
def status_cockpit():
    status = _aggregate_safe()
    if not status:
        return jsonify({"error": "unavailable"}), 503
    return jsonify(status), 200


@app.get("/status/metrics")
def status_metrics():
    try:
        from .cockpit_aggregator import aggregate_status
        from .exporters import as_metrics

        snap = aggregate_status()
        lines = [f"{k.replace('.', '_')} {v}" for k, v in as_metrics(snap).items()]

        # Optional file export
        try:
            if os.environ.get("COCKPIT_EXPORT_METRICS", "").strip().lower() in ("1", "true", "yes"):
                out_path = os.environ.get("PROM_EXPORT_PATH", "").strip()
                if out_path:
                    with open(out_path, "w") as f:
                        f.write("\n".join(lines) + "\n")
        except Exception:
            pass

        return ("\n".join(lines) + "\n", 200, {"Content-Type": "text/plain"})
    except Exception:
        return (jsonify({"error": "metrics_unavailable"}), 503)


@app.get("/status/cockpit/ui")
def status_cockpit_ui():
    # Minimal inline HTML to avoid template dependency (optional)
    status = _aggregate_safe()
    if not status:
        return "<h1>Unavailable</h1>", 503
    pods = status.get("pods", {}) or {}
    def _row(pod: str, s: dict) -> str:
        ready = "✅" if s.get("ready") else "❌"
        err = s.get("error") or ""
        hb = "ok" if s.get("heartbeat_ok") else "stale"
        return f"<tr><td>{pod}</td><td>{ready}</td><td>{hb}</td><td>{err}</td></tr>"

    rows = "".join(_row(p, pods.get(p, {})) for p in ["llm","vector","memory","belief","journal"]) \
        if isinstance(pods, dict) else ""
    html = f"""
    <html><head><title>Cockpit Status</title>
    <style>table{{border-collapse:collapse}} td,th{{border:1px solid #aaa;padding:4px 8px}}</style>
    </head>
    <body>
      <h1>Project Cockpit</h1>
      <p>generated_at: {status.get('generated_at','')}</p>
      <p>vector_blackout_active: {status.get('vector_blackout_active')}</p>
      <p>recall_degraded: {status.get('recall_degraded')}</p>
      <p>last_vector_latency_ms: {status.get('last_vector_latency_ms')}</p>
      <table>
        <thead><tr><th>pod</th><th>ready</th><th>heartbeat</th><th>error</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </body></html>
    """
    return html, 200


def main() -> int:
    bind = os.environ.get("COCKPIT_BIND", "0.0.0.0:8088")
    host, port_s = (bind.split(":", 1) + ["8088"])[:2]
    try:
        port = int(port_s)
    except Exception:
        port = 8088
    app.run(host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

