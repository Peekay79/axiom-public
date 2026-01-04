from pathlib import Path


def test_bootstrap_validator_defaults_to_workspace_persist_venv():
    p = Path(__file__).resolve().parents[1] / "bootstrap_validator.sh"
    body = p.read_text(encoding="utf-8")

    assert "VENV_PATH=\"${VENV_DIR:-/workspace/persist/venv}\"" in body
    # The validator should not hardcode the old RunPod mount default.
    assert "/mnt/data/venv" not in body
