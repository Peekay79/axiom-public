import os
import json
from unittest.mock import patch


def _mock_safe_pipeline_response(payload_text: str):
    class _Resp:
        def __init__(self, text):
            self.content = text
            self.tokens_used = 0
            self.latency = 0.0
            self.model = "test"

    # safe_multiquery_context_pipeline returns list of dicts with 'response'
    return [{"response": payload_text, "tokens_used": 0, "latency": 0.0, "model": "test"}]


def test_llm_causal_valid_json(monkeypatch):
    os.environ["AXIOM_CAUSAL_EXTRACTION_MODE"] = "llm"

    with patch("llm_connector.safe_multiquery_context_pipeline") as mock_pipe:
        mock_pipe.return_value = _mock_safe_pipeline_response(
            json.dumps([
                {"subject": "Rain", "relation": "cause_of", "object": "Wet ground"}
            ])
        )

        from causal_utils import extract_causal_relations

        out = extract_causal_relations("Rain causes wet ground")
        assert out == [("Rain", "cause_of", "Wet ground")]


def test_llm_causal_invalid_json(monkeypatch):
    os.environ["AXIOM_CAUSAL_EXTRACTION_MODE"] = "llm"

    with patch("llm_connector.safe_multiquery_context_pipeline") as mock_pipe:
        mock_pipe.return_value = _mock_safe_pipeline_response("{not valid JSON}")

        from causal_utils import extract_causal_relations

        out = extract_causal_relations("X because of Y")
        assert out == []


def test_causal_mode_switch_rules(monkeypatch):
    os.environ["AXIOM_CAUSAL_EXTRACTION_MODE"] = "rules"
    from causal_utils import extract_causal_relations

    text = "Project slipped because QA was late"
    out = extract_causal_relations(text)
    # rules should find a cause_of
    assert any(rel[1] == "cause_of" for rel in out)

