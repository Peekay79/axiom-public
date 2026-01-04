#!/usr/bin/env python3
import json
import types

import pytest


def test_select_and_decorate_templates():
    from prompts.retrieval_templates import select_template, decorate_answer

    # ok → no prefix/suffix
    t_ok = select_template("ok")
    assert t_ok["prefix"] == ""
    assert t_ok["suffix"] == ""
    assert decorate_answer("RAW", "ok").startswith("RAW")

    # thin → cautious prefix
    t_thin = select_template("thin")
    assert t_thin["prefix"]
    out_thin = decorate_answer("RAW", "thin")
    assert out_thin.startswith(t_thin["prefix"]) and out_thin.endswith("RAW")

    # none → safety prefix
    t_none = select_template("none")
    assert t_none["prefix"]
    out_none = decorate_answer("RAW", "none")
    assert out_none.startswith(t_none["prefix"]) and out_none.endswith("RAW")


def _monkey_vector_hits(monkeypatch, mod, scores):
    class _Dummy:
        def search(self, req, request_id=None):
            class R:
                def __init__(self, sc):
                    self.hits = [types.SimpleNamespace(score=s, content="", tags=[]) for s in sc]

            return R(scores)

    # Replace the instance used by the module directly for hermetic control
    monkeypatch.setattr(mod, "_unified_vector_client", _Dummy(), raising=False)


@pytest.mark.parametrize(
    "scores,expected_status",
    [([0.80, 0.7, 0.6, 0.5], "ok"), ([0.58, 0.57], "thin"), ([], "none")],
)
def test_answer_retrieval_aware_prefix(monkeypatch, scores, expected_status):
    from pods.memory import pod2_memory_api as mod
    from prompts.retrieval_templates import select_template

    # Ensure vector is considered ready and unified client exists
    monkeypatch.setattr(mod, "vector_ready", True, raising=False)
    _monkey_vector_hits(monkeypatch, mod, scores)

    # Toggle on retrieval-aware answers and style
    monkeypatch.setenv("RETRIEVAL_AWARE_ANSWERS", "1")
    monkeypatch.setenv("RETRIEVAL_TEMPLATE_STYLE", "concise")

    app = mod.app
    client = app.test_client()
    body = {"question": "rare topic", "summary": ""}
    r = client.post(
        "/answer", data=json.dumps(body), content_type="application/json"
    )
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, dict)
    # Schema unchanged
    assert set(["answer", "possible_contradictions"]).issubset(set(data.keys()))

    ans = data.get("answer", "")
    assert isinstance(ans, str)

    if expected_status == "ok":
        # Should not be prefixed; raw answer begins with this phrase
        assert ans.startswith("Given the summary")
    else:
        # Should begin with the corresponding prefix
        tmpl = select_template(expected_status)
        assert ans.startswith(tmpl["prefix"]) and not ans.startswith("Given the summary")

