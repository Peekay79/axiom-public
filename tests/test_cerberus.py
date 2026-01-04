import os
import shutil
import tarfile
from pathlib import Path

import pytest


os.environ["ENABLE_CERBERUS"] = "true"


def test_risky_event_triggers_snapshot(tmp_path, monkeypatch):
    # Redirect backup dir
    monkeypatch.setenv("CERBERUS_BACKUP_DIR", str(tmp_path / "backups"))
    from Cerberus.backup_manager import list_backups
    from Cerberus.risk_detector import detect_from_argv

    before = list_backups()
    detect_from_argv(["python", "qdrant_ingest.py", "--create-collections"])  # risky
    after = list_backups()
    assert len(after) >= len(before) + 1


def test_rotation_after_three_snapshots(tmp_path, monkeypatch):
    monkeypatch.setenv("CERBERUS_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("CERBERUS_RETENTION", "3")
    from Cerberus.backup_manager import create_snapshot, list_backups

    for i in range(5):
        create_snapshot(f"rotation-test-{i}")
    backups = list_backups()
    assert len(backups) == 3


def test_restore_from_backup(tmp_path, monkeypatch):
    monkeypatch.setenv("CERBERUS_BACKUP_DIR", str(tmp_path / "backups"))
    # Create a file to be included in snapshot
    work_dir = tmp_path / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "memory").mkdir(parents=True, exist_ok=True)
    (work_dir / "memory" / "long_term_memory.json").write_text("{\"ok\": true}")

    # Run from work_dir
    cwd = os.getcwd()
    os.chdir(work_dir)
    try:
        from Cerberus.backup_manager import create_snapshot, restore_backup, list_backups

        backup_id = create_snapshot("restore-test")
        # mutate file to prove restore
        (work_dir / "memory" / "long_term_memory.json").write_text("{}")
        ok = restore_backup(backup_id)
        assert ok
        assert (work_dir / "memory" / "long_term_memory.json").read_text() == "{\"ok\": true}"
    finally:
        os.chdir(cwd)


def test_failed_validation_logs(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CERBERUS_BACKUP_DIR", str(tmp_path / "backups"))
    from Cerberus.backup_manager import create_snapshot, list_backups

    backup_id = create_snapshot("validation-test")
    backups = list_backups()
    target = next(b for b in backups if b["backup_id"] == backup_id)
    # Corrupt the archive
    Path(target["archive_path"]).write_bytes(b"not a real tar.gz")

    from Cerberus.backup_manager import restore_backup

    ok = restore_backup(backup_id)
    assert not ok
    # Ensure error was printed
    captured = capsys.readouterr()
    # Messages go through logger to stdout; verify some presence
    assert "checksum" in (captured.out + captured.err).lower() or "corrupt" in (captured.out + captured.err).lower()

