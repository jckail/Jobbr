import importlib.util
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jobbr import db
from jobbr.main import create_app
from tests.conftest import API, reset_settings

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backup.py"
specification = importlib.util.spec_from_file_location("jobbr_backup", SCRIPT)
assert specification is not None
assert specification.loader is not None
backup = importlib.util.module_from_spec(specification)
specification.loader.exec_module(backup)


def source_path() -> Path:
    database = db.get_engine().url.database
    assert database is not None
    return Path(database)


def test_backup_restore_preserves_complete_pipeline_and_wal(
    client: TestClient,
    env: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    profile = client.put(
        f"{API}/profile", json={"name": "Snapshot Owner", "resume_text": "Python SQL Kafka"}
    )
    assert profile.status_code == 200, profile.text
    job_response = client.post(f"{API}/jobs", json={"url": "https://acme.test/jobs/backup"})
    assert job_response.status_code == 201, job_response.text
    job_id = job_response.json()["id"]
    application = client.put(
        f"{API}/jobs/{job_id}/application", json={"stage": "applied", "notes": "Preserve notes"}
    )
    assert application.status_code == 200, application.text
    original_detail = client.get(f"{API}/jobs/{job_id}").json()
    source = source_path()
    assert Path(str(source) + "-wal").exists()
    snapshot = tmp_path / "snapshot.db"
    restored = tmp_path / "restored.db"
    backup.snapshot(source, snapshot)
    assert snapshot.stat().st_mode & 0o777 == 0o600
    assert not Path(str(snapshot) + "-wal").exists()
    backup.verify(snapshot)
    backup.snapshot(snapshot, restored)
    env.setenv("JOBBR_DATABASE_URL", f"sqlite:///{restored}")
    reset_settings()
    with TestClient(create_app()) as restored_client:
        assert restored_client.get(f"{API}/profile").json() == profile.json()
        assert restored_client.get(f"{API}/jobs/{job_id}").json() == original_detail
        assert restored_client.get(f"{API}/stats").json()["totals"]["jobs"] == 1
    # Independent row checks include all child tables, IDs and committed JSON values.
    with sqlite3.connect(source) as original, sqlite3.connect(restored) as restored_connection:
        for table in (
            "profile",
            "company",
            "job",
            "application",
            "applicationevent",
            "match",
            "extraction",
            "alembic_version",
        ):
            assert original.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall() == (
                restored_connection.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()
            )


@pytest.mark.parametrize("existing", ["file", "symlink", "source"])
def test_snapshot_never_overwrites_existing_output(
    env: pytest.MonkeyPatch,
    tmp_path: Path,
    existing: str,
) -> None:
    db.init_db()
    source = source_path()
    output = tmp_path / "existing.db"
    protected = tmp_path / "protected.txt"
    protected.write_text("Preserve existing data")
    if existing == "file":
        output.write_text("Preserve existing data")
    elif existing == "symlink":
        output.symlink_to(protected)
    else:
        output = source
    previous = output.read_bytes()
    with pytest.raises(backup.BackupError, match="Destination already exists"):
        backup.snapshot(source, output)
    assert output.read_bytes() == previous
    assert protected.read_text() == "Preserve existing data"


@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE alembic_version SET version_num = 'wrong_head'",
        "DROP INDEX ix_company_name",
        "INSERT INTO job (id, company_id, title, status, seniority, remote_policy, comp_currency, "
        "first_seen_at, last_seen_at) VALUES (1, 999, 'Orphan', 'active', 'unknown', 'unknown', "
        "'USD', '2026-01-01', '2026-01-01')",
    ],
)
def test_rejects_invalid_snapshot_before_publication(
    env: pytest.MonkeyPatch,
    tmp_path: Path,
    mutation: str,
) -> None:
    db.init_db()
    source = source_path()
    # A separate disposable connection can deliberately create invalid FK data.
    with sqlite3.connect(source) as connection:
        connection.execute(mutation)
    output = tmp_path / "rejected.db"
    with pytest.raises(backup.BackupError):
        backup.snapshot(source, output)
    assert not output.exists()
    assert list(tmp_path.glob(".jobbr-snapshot-*")) == []


def test_missing_or_corrupt_source_never_publishes(tmp_path: Path) -> None:
    source = tmp_path / "missing.db"
    output = tmp_path / "output.db"
    with pytest.raises(backup.BackupError, match="Source must be an existing"):
        backup.snapshot(source, output)
    assert not source.exists()
    source.write_text("not a sqlite database")
    with pytest.raises(sqlite3.DatabaseError):
        backup.snapshot(source, output)
    assert not output.exists()
    assert list(tmp_path.glob(".jobbr-snapshot-*")) == []


def test_cli_backup_restore_and_verify(env: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db.init_db()
    source = source_path()
    snapshot = tmp_path / "cli-snapshot.db"
    restored = tmp_path / "cli-restored.db"
    for arguments in (
        ["backup", str(source), str(snapshot)],
        ["restore", str(snapshot), str(restored)],
        ["verify", str(restored)],
    ):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *arguments], check=False, capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith("Verified")
    protected = restored.read_bytes()
    rejected = subprocess.run(
        [sys.executable, str(SCRIPT), "restore", str(snapshot), str(restored)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode == 1
    assert "Destination already exists" in rejected.stderr
    assert restored.read_bytes() == protected


def test_publication_race_does_not_replace_concurrent_output(
    env: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db.init_db()
    output = tmp_path / "concurrent.db"
    original_link = backup.os.link

    def concurrent_output(source: Path, destination: Path) -> None:
        destination.write_text("Created by another process")
        original_link(source, destination)

    env.setattr(backup.os, "link", concurrent_output)
    with pytest.raises(backup.BackupError, match="Destination already exists"):
        backup.snapshot(source_path(), output)
    assert output.read_text() == "Created by another process"
    assert list(tmp_path.glob(".jobbr-snapshot-*")) == []
