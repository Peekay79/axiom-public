from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from typing import Any, Dict, Iterable, List, Optional
import logging

try:
    from confidence import calculate_confidence, _parse_weights  # type: ignore
except Exception:  # fallback if module unavailable
    def calculate_confidence(belief: Dict[str, Any], context: Dict[str, Any] | None = None) -> float:  # type: ignore
        try:
            return float(belief.get("confidence", 0.5) or 0.5)
        except Exception:
            return 0.5

    def _parse_weights(env_val: Optional[str]) -> Dict[str, float]:  # type: ignore
        return {"recency": 0.3, "reinforcement": 0.3, "source": 0.2, "contradiction": 0.2}

from .base import BeliefGraphBase


def _ensure_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


class SQLiteBeliefGraph(BeliefGraphBase):
    def __init__(self, db_path: Optional[str] = None) -> None:
        default_path = os.getenv("AXIOM_BELIEF_SQLITE_PATH") or os.path.join(
            os.getcwd(), "beliefs", "belief_graph.sqlite"
        )
        self.db_path = db_path or default_path
        _ensure_dir(self.db_path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._init_schema()
        self._logger = logging.getLogger(__name__)

    def _init_schema(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS beliefs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    recency INTEGER NOT NULL,
                    created_at INTEGER NOT NULL DEFAULT 0,
                    sources TEXT,
                    reinforcement_count INTEGER NOT NULL DEFAULT 0,
                    last_updated INTEGER NOT NULL DEFAULT 0,
                    inactive INTEGER NOT NULL DEFAULT 0,
                    state TEXT NOT NULL DEFAULT 'active',
                    time_start INTEGER,
                    time_end INTEGER
                )
                """
            )
            # Backfill/ALTER existing tables to add new columns if they are missing
            try:
                cur.execute("ALTER TABLE beliefs ADD COLUMN reinforcement_count INTEGER NOT NULL DEFAULT 0")
            except Exception:
                pass
            try:
                cur.execute("ALTER TABLE beliefs ADD COLUMN last_updated INTEGER NOT NULL DEFAULT 0")
            except Exception:
                pass
            try:
                cur.execute("ALTER TABLE beliefs ADD COLUMN inactive INTEGER NOT NULL DEFAULT 0")
            except Exception:
                pass
            try:
                cur.execute("ALTER TABLE beliefs ADD COLUMN state TEXT NOT NULL DEFAULT 'active'")
            except Exception:
                pass
            try:
                cur.execute("ALTER TABLE beliefs ADD COLUMN created_at INTEGER NOT NULL DEFAULT 0")
            except Exception:
                pass
            try:
                cur.execute("ALTER TABLE beliefs ADD COLUMN time_start INTEGER")
            except Exception:
                pass
            try:
                cur.execute("ALTER TABLE beliefs ADD COLUMN time_end INTEGER")
            except Exception:
                pass
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS belief_relations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    belief_id1 INTEGER NOT NULL,
                    belief_id2 INTEGER NOT NULL,
                    relation_type TEXT NOT NULL,
                    created_at INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(belief_id1) REFERENCES beliefs(id),
                    FOREIGN KEY(belief_id2) REFERENCES beliefs(id)
                )
                """
            )
            try:
                cur.execute("ALTER TABLE belief_relations ADD COLUMN created_at INTEGER NOT NULL DEFAULT 0")
            except Exception:
                pass
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_beliefs_subject ON beliefs(subject)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_beliefs_object ON beliefs(object)"
            )
            self._conn.commit()

    def upsert_belief(
        self,
        subject: str,
        predicate: str,
        obj: str,
        *,
        confidence: float = 0.5,
        sources: Optional[Iterable[str]] = None,
    ) -> Optional[str]:
        if not subject or not predicate or not obj:
            return None
        try:
            ts = int(time.time())
            src = json.dumps(list(sources) if sources is not None else [])
            with self._lock:
                cur = self._conn.cursor()
                # Try to find existing triple
                cur.execute(
                    "SELECT id, confidence, reinforcement_count, recency, last_updated, sources, inactive, state, created_at FROM beliefs WHERE subject=? AND predicate=? AND object=?",
                    (subject.strip(), predicate.strip(), obj.strip()),
                )
                row = cur.fetchone()
                if row:
                    bid, conf_old, rcount_old, rec_old, last_upd_old, src_old, inactive_old, state_old, created_old = row
                    # Merge sources (best-effort JSON arrays)
                    try:
                        existing_sources = json.loads(src_old or "[]") if src_old else []
                    except Exception:
                        existing_sources = []
                    try:
                        new_sources = list(set((existing_sources or []) + (json.loads(src) if src else [])))
                    except Exception:
                        new_sources = existing_sources or []

                    rcount_new = int(rcount_old or 0) + 1
                    belief_ctx = {
                        "recency": ts,
                        "last_updated": ts,
                        "reinforcement_count": rcount_new,
                    }
                    # Respect flag gating
                    enabled = str(os.getenv("AXIOM_CONFIDENCE_ENABLED", "1")).strip().lower() in {"1", "true", "yes"}
                    if enabled:
                        conf_new = calculate_confidence(belief_ctx, context={"source_reliability": 0.5})
                    else:
                        conf_new = float(confidence)

                    cur.execute(
                        """
                        UPDATE beliefs
                        SET confidence=?, reinforcement_count=?, recency=?, last_updated=?, sources=?, inactive=?, state=?, created_at=COALESCE(NULLIF(created_at,0), ?)
                        WHERE id=?
                        """,
                        (
                            float(conf_new),
                            int(rcount_new),
                            ts,
                            ts,
                            json.dumps(new_sources),
                            int(inactive_old or 0),
                            str(state_old or "active"),
                            int(created_old or 0) or ts,
                            int(bid),
                        ),
                    )
                    self._conn.commit()
                    return str(bid)
                else:
                    # Insert fresh belief
                    # Initial reinforcement_count = 1 (first observation counts as reinforcement)
                    rcount_init = 1
                    belief_ctx = {
                        "recency": ts,
                        "last_updated": ts,
                        "reinforcement_count": rcount_init,
                    }
                    enabled = str(os.getenv("AXIOM_CONFIDENCE_ENABLED", "1")).strip().lower() in {"1", "true", "yes"}
                    if enabled:
                        conf_init = calculate_confidence(belief_ctx, context={"source_reliability": 0.5})
                    else:
                        conf_init = float(confidence)

                    cur.execute(
                        """
                        INSERT INTO beliefs (subject, predicate, object, confidence, recency, created_at, sources, reinforcement_count, last_updated, inactive, state)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'active')
                        """,
                        (
                            subject.strip(),
                            predicate.strip(),
                            obj.strip(),
                            float(conf_init),
                            ts,
                            ts,
                            src,
                            int(rcount_init),
                            ts,
                        ),
                    )
                    self._conn.commit()
                    return str(cur.lastrowid)
        except Exception:
            return None

    def get_beliefs(self, subjects: List[str], *, hops: int = 1) -> List[Dict[str, Any]]:
        if not subjects:
            return []
        try:
            params = [s.strip() for s in subjects if isinstance(s, str) and s.strip()]
            if not params:
                return []
            placeholders = ",".join(["?"] * len(params))
            sql = (
                f"SELECT id, subject, predicate, object, confidence, recency, created_at, sources, reinforcement_count, last_updated, inactive, state, time_start, time_end "
                f"FROM beliefs WHERE subject IN ({placeholders}) OR object IN ({placeholders}) "
                f"ORDER BY confidence DESC, recency DESC LIMIT 20"
            )
            with self._lock:
                cur = self._conn.cursor()
                cur.execute(sql, params + params)
                rows = cur.fetchall()
            hits: List[Dict[str, Any]] = []
            for r in rows:
                bid, subj, pred, obj, conf, rec, created_at, src, rcount, last_upd, inactive_flag, state_val, time_start, time_end = r
                try:
                    sources = json.loads(src) if src else []
                except Exception:
                    sources = []
                content = f"{subj} {pred} {obj}"
                # Phase 25: mark episodes inactive when all children decayed
                try:
                    if str(state_val or "").strip().lower() == "episode":
                        self._maybe_mark_episode_inactive(int(bid), sources)
                        # Reload inactive flag if it changed
                        with self._lock:
                            cur3 = self._conn.cursor()
                            cur3.execute("SELECT inactive FROM beliefs WHERE id=?", (int(bid),))
                            row_in = cur3.fetchone()
                            if row_in:
                                inactive_flag = int(row_in[0] or 0)
                    # Phase 26: update procedure confidence from supporting evidence
                    if str(state_val or "").strip().lower() == "procedure":
                        self._maybe_update_procedure_confidence(int(bid), sources)
                        # Reload updated confidence/inactive after procedure aggregation
                        with self._lock:
                            cur3b = self._conn.cursor()
                            cur3b.execute("SELECT confidence, inactive FROM beliefs WHERE id=?", (int(bid),))
                            row_pc = cur3b.fetchone()
                            if row_pc:
                                try:
                                    conf = float(row_pc[0] if row_pc[0] is not None else conf)
                                except Exception:
                                    pass
                                try:
                                    inactive_flag = int(row_pc[1] or inactive_flag)
                                except Exception:
                                    pass
                except Exception:
                    pass
                # Optional retrieval-time decay and inactive tagging
                enabled = str(os.getenv("AXIOM_CONFIDENCE_ENABLED", "1")).strip().lower() in {"1", "true", "yes"}
                conf_val = float(conf)
                if enabled:
                    # Compute decayed confidence
                    belief_ctx = {
                        "recency": int(rec),
                        "last_updated": int(last_upd or rec),
                        "reinforcement_count": int(rcount or 0),
                    }
                    conf_new = float(calculate_confidence(belief_ctx, context={"source_reliability": 0.5}))
                    min_thr = float(os.getenv("AXIOM_CONFIDENCE_MIN_THRESHOLD", "0.2") or 0.2)
                    if conf_new < conf_val or (inactive_flag and conf_new >= min_thr):
                        try:
                            # Persist decay and possibly mark inactive
                            new_inactive = 1 if conf_new < min_thr else 0
                            with self._lock:
                                cur2 = self._conn.cursor()
                                cur2.execute(
                                    "UPDATE beliefs SET confidence=?, inactive=? WHERE id=?",
                                    (conf_new, new_inactive, int(bid)),
                                )
                                self._conn.commit()
                            try:
                                self._logger.info(
                                    f"[Confidence] Decayed belief {bid} from {conf_val:.3f} → {conf_new:.3f}"
                                )
                            except Exception:
                                pass
                            conf_val = conf_new
                            inactive_flag = new_inactive
                        except Exception:
                            pass
                hits.append(
                    {
                        "id": str(bid),
                        "content": content,
                        "type": "belief",
                        "subject": subj,
                        "predicate": pred,
                        "object": obj,
                        "confidence": float(conf_val),
                        "recency": int(rec),
                        "created_at": int(created_at or rec),
                        "sources": sources,
                        "tags": [
                            t
                            for t in (
                                "belief",
                                ("inactive" if inactive_flag else None),
                                (state_val if (state_val and state_val != "active") else None),
                            )
                            if t is not None
                        ],
                        "reinforcement_count": int(rcount or 0),
                        "last_updated": int(last_upd or rec),
                        "resolution_state": str(state_val or "active"),
                        "time_start": int(time_start) if time_start is not None else None,
                        "time_end": int(time_end) if time_end is not None else None,
                    }
                )
            return hits
        except Exception:
            return []

    def link_beliefs(self, id1: str, id2: str, relation: str) -> Optional[str]:
        try:
            if not id1 or not id2 or not relation:
                return None
            with self._lock:
                cur = self._conn.cursor()
                ts = int(time.time())
                rel = relation.strip()
                cur.execute(
                    """
                    INSERT INTO belief_relations (belief_id1, belief_id2, relation_type, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (int(id1), int(id2), rel, ts),
                )
                # Phase 13: insert inverse where defined
                try:
                    inverse_map = {
                        "cause_of": "effect_of",
                        "effect_of": "cause_of",
                        "enables": "results_in",
                        "results_in": "enables",
                    }
                    inv = inverse_map.get(rel)
                    if inv:
                        cur.execute(
                            """
                            INSERT INTO belief_relations (belief_id1, belief_id2, relation_type, created_at)
                            VALUES (?, ?, ?, ?)
                            """,
                            (int(id2), int(id1), inv, ts),
                        )
                except Exception:
                    pass
                self._conn.commit()
                return str(cur.lastrowid)
        except Exception:
            return None

    # Phase 14: Counterfactual simulation
    def simulate_counterfactual(self, node: str, remove_edge: tuple[str, str, str] | None = None) -> List[Dict[str, Any]]:  # type: ignore[override]
        try:
            target = (node or "").strip()
            if not target:
                return []
            try:
                min_conf = float(os.getenv("AXIOM_COUNTERFACTUAL_MIN_CONFIDENCE", "0.4") or 0.4)
            except Exception:
                min_conf = 0.4

            try:
                self._logger.info("[RECALL][Counterfactual] starting simulation for node=%s", target)
            except Exception:
                pass

            with self._lock:
                cur = self._conn.cursor()
                # Seed set: beliefs where subject or object matches target string
                cur.execute(
                    "SELECT id FROM beliefs WHERE subject = ? OR object = ?",
                    (target, target),
                )
                seed_rows = cur.fetchall()
                if not seed_rows:
                    return []
                seed_ids = {int(r[0]) for r in seed_rows}

                # Collect candidate forward edges (cause_of/enables/results_in) from seeds
                forward_types = {"cause_of", "enables", "results_in"}

                # Optionally filter to a specific remove_edge triple
                filter_subject = filter_relation = filter_object = None
                if isinstance(remove_edge, tuple) and len(remove_edge) == 3:
                    filter_subject, filter_relation, filter_object = remove_edge
                    filter_subject = (filter_subject or "").strip() or None
                    filter_relation = (filter_relation or "").strip() or None
                    filter_object = (filter_object or "").strip() or None

                removed_labels: List[str] = []
                alt_effects: List[Dict[str, Any]] = []

                # Find all seed beliefs with their fields to compute confidences/labels
                placeholders = ",".join(["?"] * len(seed_ids))
                cur.execute(
                    f"SELECT id, subject, predicate, object, confidence FROM beliefs WHERE id IN ({placeholders})",
                    list(seed_ids),
                )
                seed_map = {}
                for bid, subj, pred, obj, conf in cur.fetchall():
                    seed_map[int(bid)] = {
                        "id": int(bid),
                        "subject": subj,
                        "predicate": pred,
                        "object": obj,
                        "confidence": float(conf or 0.0),
                    }

                # Explore outgoing relations from seed nodes
                placeholders = ",".join(["?"] * len(seed_ids))
                rel_types_ph = ",".join(["?"] * len(forward_types))
                cur.execute(
                    f"SELECT belief_id1, belief_id2, relation_type FROM belief_relations WHERE relation_type IN ({rel_types_ph}) AND belief_id1 IN ({placeholders})",
                    list(forward_types) + list(seed_ids),
                )
                edges = cur.fetchall()

                # Preload effect belief details
                effect_ids = {int(b) for _, b, _ in edges}
                effects_map: Dict[int, Dict[str, Any]] = {}
                if effect_ids:
                    placeholders = ",".join(["?"] * len(effect_ids))
                    cur.execute(
                        f"SELECT id, subject, predicate, object, confidence FROM beliefs WHERE id IN ({placeholders})",
                        list(effect_ids),
                    )
                    for bid, subj, pred, obj, conf in cur.fetchall():
                        effects_map[int(bid)] = {
                            "id": int(bid),
                            "subject": subj,
                            "predicate": pred,
                            "object": obj,
                            "confidence": float(conf or 0.0),
                        }

                # Helper to make a concise label for an effect belief
                def _effect_label(e: Dict[str, Any]) -> str:
                    subj = (e.get("subject") or "").strip()
                    obj = (e.get("object") or "").strip()
                    # Prefer a proper noun style subject if present
                    if subj:
                        return subj
                    return (obj or (e.get("predicate") or "")).strip() or str(e.get("id"))

                # Iterate edges and compute counterfactual impacts
                for a, b, rtyp in edges:
                    a = int(a)
                    b = int(b)
                    r = str(rtyp or "").strip()
                    cause = seed_map.get(a)
                    effect = effects_map.get(b)
                    if not cause or not effect:
                        continue

                    # Apply remove_edge filter if provided
                    if filter_subject and filter_subject != cause.get("subject") and filter_subject != cause.get("object"):
                        continue
                    if filter_relation and filter_relation != r:
                        continue
                    if filter_object and filter_object not in {effect.get("subject"), effect.get("object")}:
                        continue

                    # Inherit edge confidence conservatively as min(cause, effect)
                    edge_conf = min(float(cause.get("confidence", 0.0)), float(effect.get("confidence", 0.0)))
                    if edge_conf < min_conf:
                        # Skip edges too weak for counterfactual simulation
                        continue

                    # Log removed edge
                    try:
                        c_label = (cause.get("subject") or cause.get("object") or str(cause.get("id")))
                        e_label = (effect.get("subject") or effect.get("object") or str(effect.get("id")))
                        msg = f"{c_label} --({r})-> {e_label}"
                        removed_labels.append(msg)
                        self._logger.info("[RECALL][Counterfactual] removed edge: %s", msg)
                    except Exception:
                        pass

                    # Determine if there are alternate causes for the same effect
                    cur.execute(
                        "SELECT belief_id1, relation_type FROM belief_relations WHERE relation_type IN (?,?,?) AND belief_id2 = ?",
                        ("cause_of", "enables", "results_in", int(b)),
                    )
                    alt_rows = cur.fetchall()
                    alt_causes = [int(x[0]) for x in alt_rows if int(x[0]) != a]

                    label = _effect_label(effect)
                    if not alt_causes:
                        # Effect likely avoided
                        eff_text = f"{label} avoided"
                        alt_effects.append({
                            "effect": eff_text,
                            "impact": "avoided",
                            "confidence": edge_conf,
                            "removed": {
                                "cause": c_label,
                                "relation": r,
                                "effect": e_label,
                            },
                        })
                        try:
                            self._logger.info("[RECALL][Counterfactual] alternate path: %s", eff_text)
                        except Exception:
                            pass
                    else:
                        # Effect may persist via alternative paths; infer reduced/maintained by max alt cause conf
                        placeholders = ",".join(["?"] * len(alt_causes))
                        cur.execute(
                            f"SELECT confidence FROM beliefs WHERE id IN ({placeholders})",
                            list(alt_causes),
                        )
                        alt_conf = [float(row[0] or 0.0) for row in cur.fetchall()]
                        new_conf = max(alt_conf) if alt_conf else 0.0
                        impact = "reduced" if new_conf < edge_conf else "maintained"
                        eff_text = f"{label} {impact}"
                        alt_effects.append({
                            "effect": eff_text,
                            "impact": impact,
                            "confidence": new_conf,
                            "removed": {
                                "cause": c_label,
                                "relation": r,
                                "effect": e_label,
                            },
                        })
                        try:
                            self._logger.info("[RECALL][Counterfactual] alternate path: %s", eff_text)
                        except Exception:
                            pass

                # Return a compact list of effects (dicts) ordered by confidence desc
                alt_effects.sort(key=lambda d: float(d.get("confidence", 0.0)), reverse=True)
                return alt_effects
        except Exception:
            return []

    # Phase 4: traversal by subject
    def get_related_beliefs(self, subject: str, depth: int = 1) -> List[Dict[str, Any]]:
        if not isinstance(subject, str) or not subject.strip():
            return []
        try:
            depth = max(1, int(depth))
        except Exception:
            depth = 1

        try:
            with self._lock:
                cur = self._conn.cursor()
                # Seed: beliefs where subject or object matches input subject
                cur.execute(
                    """
                    SELECT id FROM beliefs WHERE subject = ? OR object = ?
                    """,
                    (subject.strip(), subject.strip()),
                )
                seed_rows = cur.fetchall()
                frontier = {int(r[0]) for r in seed_rows}
                visited = set(frontier)

                # BFS over belief_relations up to depth
                for _ in range(depth):
                    if not frontier:
                        break
                    placeholders = ",".join(["?"] * len(frontier))
                    params = list(frontier)
                    # Explore both directions
                    cur.execute(
                        f"SELECT belief_id1, belief_id2 FROM belief_relations WHERE belief_id1 IN ({placeholders}) OR belief_id2 IN ({placeholders})",
                        params + params,
                    )
                    rows = cur.fetchall()
                    next_frontier = set()
                    for a, b in rows:
                        a = int(a)
                        b = int(b)
                        if a in frontier and b not in visited:
                            next_frontier.add(b)
                        if b in frontier and a not in visited:
                            next_frontier.add(a)
                    visited.update(next_frontier)
                    frontier = next_frontier

                if not visited:
                    return []

                placeholders = ",".join(["?"] * len(visited))
                cur.execute(
                    f"SELECT id, subject, predicate, object, confidence, recency, created_at, sources, reinforcement_count, last_updated, inactive, state, time_start, time_end FROM beliefs WHERE id IN ({placeholders}) ORDER BY confidence DESC, recency DESC LIMIT 50",
                    list(visited),
                )
                rows = cur.fetchall()

            hits: List[Dict[str, Any]] = []
            for r in rows:
                bid, subj, pred, obj, conf, rec, created_at, src, rcount, last_upd, inactive_flag, state_val, time_start, time_end = r
                try:
                    sources = json.loads(src) if src else []
                except Exception:
                    sources = []
                content = f"{subj} {pred} {obj}"
                # Phase 25: episode inactivity propagation
                try:
                    if str(state_val or "").strip().lower() == "episode":
                        self._maybe_mark_episode_inactive(int(bid), sources)
                        with self._lock:
                            cur3 = self._conn.cursor()
                            cur3.execute("SELECT inactive FROM beliefs WHERE id=?", (int(bid),))
                            row_in = cur3.fetchone()
                            if row_in:
                                inactive_flag = int(row_in[0] or 0)
                    # Phase 26: procedure confidence aggregation from evidence
                    if str(state_val or "").strip().lower() == "procedure":
                        self._maybe_update_procedure_confidence(int(bid), sources)
                        # Refresh local confidence so returned hit reflects update
                        with self._lock:
                            cur3b = self._conn.cursor()
                            cur3b.execute("SELECT confidence, inactive FROM beliefs WHERE id=?", (int(bid),))
                            row_pc = cur3b.fetchone()
                            if row_pc:
                                try:
                                    conf_val = float(row_pc[0] if row_pc[0] is not None else conf_val)
                                except Exception:
                                    pass
                                try:
                                    inactive_flag = int(row_pc[1] or inactive_flag)
                                except Exception:
                                    pass
                except Exception:
                    pass
                enabled = str(os.getenv("AXIOM_CONFIDENCE_ENABLED", "1")).strip().lower() in {"1", "true", "yes"}
                conf_val = float(conf)
                if enabled:
                    belief_ctx = {
                        "recency": int(rec),
                        "last_updated": int(last_upd or rec),
                        "reinforcement_count": int(rcount or 0),
                    }
                    conf_new = float(calculate_confidence(belief_ctx, context={"source_reliability": 0.5}))
                    if conf_new < conf_val:
                        min_thr = float(os.getenv("AXIOM_CONFIDENCE_MIN_THRESHOLD", "0.2") or 0.2)
                        try:
                            with self._lock:
                                cur2 = self._conn.cursor()
                                cur2.execute(
                                    "UPDATE beliefs SET confidence=?, inactive=? WHERE id=?",
                                    (conf_new, int(1 if conf_new < min_thr else (inactive_flag or 0)), int(bid)),
                                )
                                self._conn.commit()
                            try:
                                self._logger.info(
                                    f"[Confidence] Decayed belief {bid} from {conf_val:.3f} → {conf_new:.3f}"
                                )
                            except Exception:
                                pass
                            conf_val = conf_new
                        except Exception:
                            pass
                hits.append(
                    {
                        "id": str(bid),
                        "content": content,
                        "type": "belief",
                        "subject": subj,
                        "predicate": pred,
                        "object": obj,
                        "confidence": float(conf_val),
                        "recency": int(rec),
                        "created_at": int(created_at or rec),
                        "sources": sources,
                        "tags": [
                            t
                            for t in (
                                "belief",
                                ("inactive" if inactive_flag else None),
                                (state_val if (state_val and state_val != "active") else None),
                            )
                            if t is not None
                        ],
                        "reinforcement_count": int(rcount or 0),
                        "last_updated": int(last_upd or rec),
                        "resolution_state": str(state_val or "active"),
                        "time_start": int(time_start) if time_start is not None else None,
                        "time_end": int(time_end) if time_end is not None else None,
                    }
                )
            return hits
        except Exception:
            return []

    # Phase 10: associative traversal by entity name
    def get_associative_beliefs(self, entity: str, depth: int = 2) -> List[Dict[str, Any]]:  # type: ignore[override]
        try:
            if not isinstance(entity, str) or not entity.strip():
                return []
            try:
                depth = max(1, int(depth))
            except Exception:
                depth = 2
            hits = self.get_related_beliefs(entity.strip(), depth=depth) or []
            # Cap aggressively for safety
            return hits[:20]
        except Exception:
            return []

    # Phase 13: directional causal traversal by entity name
    def get_causal_beliefs(self, entity: str, *, direction: str = "forward", depth: int = 1) -> List[Dict[str, Any]]:  # type: ignore[override]
        try:
            if not isinstance(entity, str) or not entity.strip():
                return []
            try:
                depth = max(1, int(depth))
            except Exception:
                depth = 1

            with self._lock:
                cur = self._conn.cursor()
                cur.execute(
                    """
                    SELECT id FROM beliefs WHERE subject = ? OR object = ?
                    """,
                    (entity.strip(), entity.strip()),
                )
                seed_rows = cur.fetchall()
                frontier = {int(r[0]) for r in seed_rows}
                visited = set(frontier)

                forward_types = {"cause_of", "enables", "results_in"}
                backward_types = {"effect_of"}

                for _ in range(depth):
                    if not frontier:
                        break
                    placeholders = ",".join(["?"] * len(frontier))
                    params = list(frontier)
                    if str(direction or "").strip().lower() == "backward":
                        rel_types = ",".join(["?"] * len(backward_types))
                        cur.execute(
                            f"SELECT belief_id1, belief_id2, relation_type FROM belief_relations WHERE relation_type IN ({rel_types}) AND (belief_id1 IN ({placeholders}) OR belief_id2 IN ({placeholders}))",
                            list(backward_types) + params + params,
                        )
                    else:
                        rel_types = ",".join(["?"] * len(forward_types))
                        cur.execute(
                            f"SELECT belief_id1, belief_id2, relation_type FROM belief_relations WHERE relation_type IN ({rel_types}) AND (belief_id1 IN ({placeholders}) OR belief_id2 IN ({placeholders}))",
                            list(forward_types) + params + params,
                        )
                    rows = cur.fetchall()
                    next_frontier = set()
                    for a, b, rtyp in rows:
                        a = int(a)
                        b = int(b)
                        if str(direction or "").strip().lower() == "backward":
                            if b in frontier and a not in visited:
                                next_frontier.add(a)
                            if a in frontier and b not in visited and (rtyp == "effect_of"):
                                next_frontier.add(b)
                        else:
                            if a in frontier and b not in visited:
                                next_frontier.add(b)
                            if b in frontier and a not in visited and (rtyp in {"results_in"}):
                                next_frontier.add(a)
                    visited.update(next_frontier)
                    frontier = next_frontier

                if not visited:
                    return []

                placeholders = ",".join(["?"] * len(visited))
                cur.execute(
                    f"SELECT id, subject, predicate, object, confidence, recency, created_at, sources, reinforcement_count, last_updated, inactive, state, time_start, time_end FROM beliefs WHERE id IN ({placeholders}) ORDER BY confidence DESC, recency DESC LIMIT 50",
                    list(visited),
                )
                rows = cur.fetchall()

            hits: List[Dict[str, Any]] = []
            for r in rows:
                bid, subj, pred, obj, conf, rec, created_at, src, rcount, last_upd, inactive_flag, state_val, time_start, time_end = r
                try:
                    sources = json.loads(src) if src else []
                except Exception:
                    sources = []
                content = f"{subj} {pred} {obj}"
                # Phase 25: episode inactivity propagation
                try:
                    if str(state_val or "").strip().lower() == "episode":
                        self._maybe_mark_episode_inactive(int(bid), sources)
                        with self._lock:
                            cur3 = self._conn.cursor()
                            cur3.execute("SELECT inactive FROM beliefs WHERE id=?", (int(bid),))
                            row_in = cur3.fetchone()
                            if row_in:
                                inactive_flag = int(row_in[0] or 0)
                except Exception:
                    pass
                enabled = str(os.getenv("AXIOM_CONFIDENCE_ENABLED", "1")).strip().lower() in {"1", "true", "yes"}
                conf_val = float(conf)
                if enabled:
                    belief_ctx = {
                        "recency": int(rec),
                        "last_updated": int(last_upd or rec),
                        "reinforcement_count": int(rcount or 0),
                    }
                    conf_new = float(calculate_confidence(belief_ctx, context={"source_reliability": 0.5}))
                    if conf_new < conf_val:
                        try:
                            min_thr = float(os.getenv("AXIOM_CONFIDENCE_MIN_THRESHOLD", "0.2") or 0.2)
                            with self._lock:
                                cur2 = self._conn.cursor()
                                cur2.execute(
                                    "UPDATE beliefs SET confidence=?, inactive=? WHERE id=?",
                                    (conf_new, int(1 if conf_new < min_thr else (inactive_flag or 0)), int(bid)),
                                )
                                self._conn.commit()
                            try:
                                self._logger.info(
                                    f"[Confidence] Decayed belief {bid} from {conf_val:.3f} → {conf_new:.3f}"
                                )
                            except Exception:
                                pass
                            conf_val = conf_new
                        except Exception:
                            pass
            
                hits.append(
                    {
                        "id": str(bid),
                        "content": content,
                        "type": "belief",
                        "subject": subj,
                        "predicate": pred,
                        "object": obj,
                        "confidence": float(conf_val),
                        "recency": int(rec),
                        "created_at": int(created_at or rec),
                        "sources": sources,
                        "tags": [t for t in ("belief",) if t is not None],
                        "reinforcement_count": int(rcount or 0),
                        "last_updated": int(last_upd or rec),
                        "resolution_state": str(state_val or "active"),
                        "time_start": int(time_start) if time_start is not None else None,
                        "time_end": int(time_end) if time_end is not None else None,
                    }
                )
            return hits
        except Exception:
            return []

    # Optional helper: apply contradiction penalty (not part of base interface)
    def apply_contradiction_penalty(self, belief_id: str, penalty: float) -> bool:  # type: ignore
        try:
            if not belief_id:
                return False
            with self._lock:
                cur = self._conn.cursor()
                cur.execute("SELECT confidence FROM beliefs WHERE id=?", (int(belief_id),))
                row = cur.fetchone()
                if not row:
                    return False
                conf_old = float(row[0] or 0.0)
                weights = _parse_weights(os.getenv("AXIOM_CONFIDENCE_WEIGHTS"))
                w_contra = float(weights.get("contradiction", 0.2))
                new_conf = max(0.0, min(1.0, conf_old - float(penalty) * w_contra))
                min_thr = float(os.getenv("AXIOM_CONFIDENCE_MIN_THRESHOLD", "0.2") or 0.2)
                cur.execute(
                    "UPDATE beliefs SET confidence=?, inactive=? WHERE id=?",
                    (new_conf, int(1 if new_conf < min_thr else 0), int(belief_id)),
                )
                self._conn.commit()
                try:
                    self._logger.info(
                        f"[Confidence] Contradiction penalty: belief {belief_id} {conf_old:.3f} → {new_conf:.3f}"
                    )
                except Exception:
                    pass
                return True
        except Exception:
            return False

    # Phase 7/24: set belief state (active|superseded|uncertain|archived|retired)
    def set_belief_state(self, belief_id: str, state: str) -> bool:  # type: ignore[override]
        try:
            if not belief_id:
                return False
            state_norm = str(state or "").strip().lower()
            if state_norm not in {"active", "superseded", "uncertain", "archived", "retired", "episode", "procedure"}:
                return False
            with self._lock:
                cur = self._conn.cursor()
                cur.execute("UPDATE beliefs SET state=? WHERE id=?", (state_norm, int(belief_id)))
                self._conn.commit()
            try:
                self._logger.info(f"[BeliefGraph][State] id={belief_id} state={state_norm}")
            except Exception:
                pass
            return True
        except Exception:
            return False

    # ---- Phase 25 helpers ----
    def _maybe_mark_episode_inactive(self, belief_id: int, sources: List[Any]) -> None:
        """If all child memories' confidence < threshold, mark episode inactive.

        Safe no-op on any error. Looks up child memories via Memory snapshot when available.
        """
        try:
            if not sources:
                return
            try:
                thr = float(os.getenv("AXIOM_CONFIDENCE_MIN_THRESHOLD", "0.2") or 0.2)
            except Exception:
                thr = 0.2
            # Import Memory lazily to avoid hard dependency
            Memory = None
            try:
                from pods.memory.memory_manager import Memory as _Mem  # type: ignore
                Memory = _Mem
            except Exception:
                try:
                    from memory_manager import Memory as _Mem2  # type: ignore
                    Memory = _Mem2
                except Exception:
                    Memory = None
            if Memory is None:
                return
            mem = Memory()
            snap = mem.snapshot() if hasattr(mem, "snapshot") else []
            idset = {str(s) for s in sources if s}
            if not idset:
                return
            child_confs: List[float] = []
            for m in snap:
                try:
                    mid = str(m.get("id"))
                    if mid not in idset:
                        continue
                    child_confs.append(float(m.get("confidence", 0.0) or 0.0))
                except Exception:
                    continue
            if not child_confs:
                return
            if all(c < thr for c in child_confs):
                with self._lock:
                    cur = self._conn.cursor()
                    cur.execute("UPDATE beliefs SET inactive=? WHERE id=?", (1, int(belief_id)))
                    self._conn.commit()
                try:
                    self._logger.info(f"[RECALL][Loop25] episode_inactivated id={belief_id} children_below_thr={len(child_confs)}")
                except Exception:
                    pass
        except Exception:
            return

    # ---- Phase 26 helpers ----
    def _maybe_update_procedure_confidence(self, belief_id: int, sources: List[Any]) -> None:
        """Update procedure belief confidence based on supporting evidence average.

        Computes the average confidence of child memory entries referenced by `sources`.
        If the aggregate is lower than the stored belief confidence, update it and mark
        inactive when falling below AXIOM_CONFIDENCE_MIN_THRESHOLD.
        """
        try:
            if not sources:
                return
            try:
                thr = float(os.getenv("AXIOM_CONFIDENCE_MIN_THRESHOLD", "0.2") or 0.2)
            except Exception:
                thr = 0.2
            # Read current confidence
            with self._lock:
                cur = self._conn.cursor()
                cur.execute("SELECT confidence FROM beliefs WHERE id=?", (int(belief_id),))
                row = cur.fetchone()
            if not row:
                return
            conf_old = float(row[0] or 0.0)

            # Import Memory lazily
            Memory = None
            try:
                from pods.memory.memory_manager import Memory as _Mem  # type: ignore
                Memory = _Mem
            except Exception:
                try:
                    from memory_manager import Memory as _Mem2  # type: ignore
                    Memory = _Mem2
                except Exception:
                    Memory = None
            if Memory is None:
                return
            mem = Memory()
            snap = mem.snapshot() if hasattr(mem, "snapshot") else []
            idset = {str(s) for s in sources if s}
            vals: List[float] = []
            for m in snap:
                try:
                    mid = str(m.get("id"))
                    if mid not in idset:
                        continue
                    vals.append(float(m.get("confidence", 0.0) or 0.0))
                except Exception:
                    continue
            if not vals:
                return
            conf_new = sum(vals) / float(len(vals))
            conf_new = max(0.0, min(1.0, conf_new))
            if conf_new < conf_old or conf_new < thr:
                with self._lock:
                    cur2 = self._conn.cursor()
                    cur2.execute(
                        "UPDATE beliefs SET confidence=?, inactive=? WHERE id=?",
                        (conf_new, int(1 if conf_new < thr else 0), int(belief_id)),
                    )
                    self._conn.commit()
                try:
                    self._logger.info(
                        f"[RECALL][Loop26] procedure_conf_updated id={belief_id} {conf_old:.3f}→{conf_new:.3f}"
                    )
                except Exception:
                    pass
        except Exception:
            return

