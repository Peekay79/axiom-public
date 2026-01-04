import json
import os
import pathlib


def test_stress_harness_creates_jsonl(monkeypatch, tmp_path):
    # Configure small run
    log_path = tmp_path / "stress_out.jsonl"
    monkeypatch.setenv("AXIOM_STRESS_TURNS", "10")
    monkeypatch.setenv("AXIOM_STRESS_THREADS", "1")
    monkeypatch.setenv("AXIOM_STRESS_LOG_FILE", str(log_path))

    # Import harness
    import importlib
    stress = importlib.import_module("stress_harness")

    out_file = stress.run()

    assert out_file == str(log_path)
    assert os.path.exists(out_file)

    # Read a few lines and validate fields
    with open(out_file, "r", encoding="utf-8") as f:
        count = 0
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            # required fields
            assert obj.get("ns") == "RECALL.Stress"
            assert isinstance(obj.get("turn"), int)
            assert isinstance(obj.get("latency_ms"), int)
            # vitals fields present (may be empty dicts)
            assert "latency_hist_ms" in obj
            assert "contradictions" in obj
            assert "tripwires" in obj
            assert "champ_bias" in obj
            count += 1
            if count >= 3:
                break
    assert count >= 1
