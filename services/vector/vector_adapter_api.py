"""
Vector Adapter HTTP API (Flask).

Kept separate from `pods/vector/vector_adapter.py` so the adapter can be imported
in minimal pods (e.g. the LLM pod) without requiring Flask.
"""

from __future__ import annotations

import os
import asyncio

from flask import Flask, jsonify, request

from pods.vector.vector_adapter import (
    CERTAINTY_MIN,
    TOP_K_FRAGMENTS,
    VectorAdapter,
    _CB,
    _RID_HEADER,
    _env_bool,
    get_or_create_request_id,
    logger,
    startup_vector_health_check,
)

from security import auth as ax_auth


def create_app() -> Flask:
    app = Flask(__name__)

    _OPEN_PATHS = {"/health"}

    @app.before_request
    def _auth_guard():
        path = request.path or ""
        if path in _OPEN_PATHS:
            return None
        ok, err = ax_auth.verify_request(request)
        if not ok:
            resp = jsonify(err)
            resp.status_code = 401
            resp.headers["WWW-Authenticate"] = 'Bearer realm="Axiom"'
            return resp
        return None

    @app.route("/health", methods=["GET"])
    def health_check():
        writes_enabled = _env_bool("ADAPTER_ENABLE_V1_WRITES", False)
        try:
            rid = get_or_create_request_id(request.headers)
            logger.info(
                "{"
                + f"\"component\":\"vector\",\"event\":\"health\",\"ok\":true,\"req_id\":\"{rid}\""
                + "}"
            )
        except Exception:
            pass
        try:
            circuit_open = bool(_CB.is_open())
        except Exception:
            circuit_open = False
        resp = jsonify(
            {
                "status": "ok",
                "adapter_v1_shim": True,
                "adapter_v1_writes": bool(writes_enabled),
                "circuit_open": circuit_open,
            }
        )
        try:
            rid = get_or_create_request_id(request.headers)
            resp.headers[_RID_HEADER] = rid
        except Exception:
            pass
        return resp, 200

    @app.route("/insert", methods=["POST"])
    def insert_handler():
        data = request.get_json() or {}
        class_name = data.get("class_name")
        payload = data.get("data", {}) or {}
        try:
            if not _CB.can_execute():
                resp = jsonify({"error": "vector backend unavailable"})
                try:
                    rid = get_or_create_request_id(request.headers)
                    resp.headers[_RID_HEADER] = rid
                except Exception:
                    pass
                return resp, 503
        except Exception:
            pass

        adapter = VectorAdapter()
        try:
            result = asyncio.run(adapter.insert(class_name, payload))
            return jsonify({"success": bool(result)}), (200 if result else 500)
        except Exception as e:
            return jsonify({"success": False, "error": str(e)[:240]}), 503

    @app.route("/recall", methods=["POST"])
    def recall_handler():
        data = request.get_json() or {}
        query = data.get("query")
        top_k = data.get("top_k", TOP_K_FRAGMENTS)
        certainty_min = data.get("certainty_min", CERTAINTY_MIN)
        include_metadata = data.get("include_metadata", False)

        if not query:
            return jsonify({"error": "Query missing"}), 400

        try:
            if not _CB.can_execute():
                resp = jsonify({"error": "vector backend unavailable"})
                try:
                    rid = get_or_create_request_id(request.headers)
                    resp.headers[_RID_HEADER] = rid
                except Exception:
                    pass
                return resp, 503
        except Exception:
            pass

        adapter = VectorAdapter()
        try:
            results = asyncio.run(
                adapter.recall_relevant_memories(
                    query=query,
                    top_k=top_k,
                    certainty_min=certainty_min,
                    include_metadata=include_metadata,
                )
            )
            return jsonify({"results": results}), 200
        except Exception as e:
            return jsonify({"results": [], "error": str(e)[:240]}), 503

    @app.route("/vectorize", methods=["POST"])
    def vectorize():
        data = request.get_json() or {}
        text = data.get("text")
        if not isinstance(text, str) or not text.strip():
            return jsonify({"error": "Missing 'text' field in JSON"}), 400
        adapter = VectorAdapter()
        try:
            vec = adapter.embedder.embed_text(text)
            return jsonify({"vector": vec}), 200
        except Exception as e:
            return jsonify({"error": str(e)[:240]}), 503

    # ─────────────────────────────────────────────────────────────
    # Compatibility shim for legacy callers (/v1/*)
    # ─────────────────────────────────────────────────────────────

    @app.route("/v1/search", methods=["POST"])
    def v1_search_handler():
        data = request.get_json() or {}
        query = data.get("query") or data.get("text") or data.get("q") or ""
        top_k = int(data.get("top_k") or data.get("limit") or TOP_K_FRAGMENTS)

        if not query:
            return jsonify({"hits": []}), 200

        try:
            if not _CB.can_execute():
                resp = jsonify({"error": "vector backend unavailable"})
                try:
                    rid = request.headers.get(_RID_HEADER)
                    if rid:
                        resp.headers[_RID_HEADER] = rid
                except Exception:
                    pass
                return resp, 503
        except Exception:
            pass

        adapter = VectorAdapter()
        try:
            results = adapter.search(query=query, top_k=top_k, certainty_min=CERTAINTY_MIN)
        except Exception:
            results = []

        hits = []
        for r in results:
            if isinstance(r, dict):
                text = r.get("text") or r.get("content") or ""
                tags = r.get("tags", [])
                score = None
                add = r.get("_additional") or {}
                if isinstance(add, dict) and "certainty" in add:
                    score = add.get("certainty")
                elif "_similarity" in r:
                    score = r.get("_similarity")
                try:
                    score = float(score) if score is not None else 0.0
                except Exception:
                    score = 0.0
                hits.append({"payload": {"text": text, "tags": tags}, "score": score})
            else:
                hits.append({"payload": {"text": str(r), "tags": []}, "score": 0.0})

        resp = jsonify({"hits": hits})
        try:
            rid = request.headers.get(_RID_HEADER)
            if rid:
                resp.headers[_RID_HEADER] = rid
        except Exception:
            pass
        return resp, 200

    @app.route("/v1/memories", methods=["POST"])
    def v1_memories_handler():
        data = request.get_json() or {}
        items = data.get("items")
        if not isinstance(items, list):
            payload = data
            items = [payload] if isinstance(payload, dict) else []

        writes_enabled = _env_bool("ADAPTER_ENABLE_V1_WRITES", False)
        if not writes_enabled:
            resp = jsonify({"error": "v1 writes disabled; set ADAPTER_ENABLE_V1_WRITES=true to enable"})
            try:
                rid = request.headers.get(_RID_HEADER)
                if rid:
                    resp.headers[_RID_HEADER] = rid
            except Exception:
                pass
            return resp, 403

        try:
            if not _CB.can_execute():
                resp = jsonify({"error": "vector backend unavailable"})
                try:
                    rid = request.headers.get(_RID_HEADER)
                    if rid:
                        resp.headers[_RID_HEADER] = rid
                except Exception:
                    pass
                return resp, 503
        except Exception:
            pass

        adapter = VectorAdapter()
        inserted = 0
        for it in items:
            try:
                content = it.get("content") or (it.get("payload", {}) or {}).get("content") or ""
                metadata = it.get("metadata") or it.get("payload") or {}
                ok = asyncio.run(
                    adapter.insert(
                        class_name="Memory",
                        data={"content": content, **({} if not isinstance(metadata, dict) else metadata)},
                    )
                )
                if ok:
                    inserted += 1
            except Exception:
                continue

        resp = jsonify({"inserted": inserted})
        try:
            rid = get_or_create_request_id(request.headers)
            resp.headers[_RID_HEADER] = rid
        except Exception:
            pass
        return resp, 200

    return app


def main() -> None:
    # Perform health check on startup
    startup_vector_health_check()

    # ── Boot orchestration (additive, flag-gated) ───────────────────────────
    try:
        from boot import BOOT_ORCHESTRATION_ENABLED, BOOT_VERSION_BANNER_ENABLED  # type: ignore
    except Exception:
        BOOT_ORCHESTRATION_ENABLED = True  # type: ignore
        BOOT_VERSION_BANNER_ENABLED = True  # type: ignore
    try:
        if BOOT_ORCHESTRATION_ENABLED:
            from boot.phases import run_boot  # type: ignore
            from pods.cockpit.cockpit_reporter import write_signal  # type: ignore
            from boot.version_banner import collect_banner  # type: ignore

            def _p0():
                return True

            def _p1():
                return True

            def _p2():
                return True

            def _deps():
                try:
                    ok = startup_vector_health_check()
                except Exception:
                    ok = False
                return {"vector": bool(ok), "journal": True}

            _status = run_boot("vector", {"Phase0": _p0, "Phase1": _p1, "Phase2": _p2}, _deps)
            if BOOT_VERSION_BANNER_ENABLED:
                try:
                    write_signal("vector", "version_banner", collect_banner())
                except Exception:
                    pass
    except Exception:
        pass

    # Print resolved mode banner (adapter role)
    try:
        from config.resolved_mode import ResolvedMode  # type: ignore

        rm = ResolvedMode.from_env(os.environ, default_role="vector")
        print(rm.json_line(component="startup"))
    except Exception:
        pass

    app = create_app()
    print("✅ Vector adapter API running on http://0.0.0.0:5001")
    app.run(host="0.0.0.0", port=int(os.getenv("VECTOR_ADAPTER_PORT", "5001") or 5001))


if __name__ == "__main__":
    main()

