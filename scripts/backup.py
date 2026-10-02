"""Consistent SQLite snapshots and verified restore to a new path.

Run with the backend's Python environment, or as /app/backup.py in its container.
No operation modifies an existing destination or opens the source for writes.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import tempfile
import time
from importlib.resources import files
from pathlib import Path

# Source checkout execution; installed containers already provide jobbr on sys.path.
backend = Path(__file__).resolve().parents[1] / "backend"
if backend.is_dir():
    sys.path.insert(0, str(backend))

from alembic.config import Config  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

from jobbr import auth_models, models  # noqa: E402, F401
from jobbr.schema import SchemaMismatchError, verify_schema  # noqa: E402
from migrations.baseline import metadata as initial_schema  # noqa: E402
from migrations.drafts_baseline import metadata as drafts_schema  # noqa: E402

BACKUP_TIMEOUT_SECONDS = 60


class BackupError(RuntimeError):
    """A snapshot could not safely be accepted."""


def read_only_connection(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise BackupError("Source must be an existing SQLite database file.")
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)
    connection.execute("PRAGMA query_only=ON")
    return connection


def verify(path: Path) -> None:
    """Check contents and revision without migrating or changing the database."""
    connection = read_only_connection(path)
    try:
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise BackupError("SQLite integrity validation failed.")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise BackupError("SQLite foreign-key validation failed.")
        configuration = Config()
        configuration.set_main_option("script_location", str(files("migrations")))
        heads = set(ScriptDirectory.from_config(configuration).get_heads())
        revisions = {
            row[0] for row in connection.execute("SELECT version_num FROM alembic_version")
        }
        historical_schemas = {
            "0001_v2": initial_schema,
            "0002_saved_drafts": drafts_schema,
        }
        if revisions == heads:
            expected = SQLModel.metadata
        elif len(revisions) == 1 and next(iter(revisions)) in historical_schemas:
            expected = historical_schemas[next(iter(revisions))]
        else:
            raise BackupError("Database revision is not supported by this backend.")
        if "authstoreguard" in expected.tables and connection.execute(
            "SELECT id FROM authstoreguard"
        ).fetchall() != [(1,)]:
            raise BackupError("Database initialization guard validation failed.")
        # Reuse the same read-only connection; never call application startup/init_db here.
        engine = create_engine("sqlite://", creator=lambda: connection)
        try:
            with engine.connect() as sqlalchemy_connection:
                verify_schema(sqlalchemy_connection, expected)
        except (SchemaMismatchError, SQLAlchemyError) as error:
            raise BackupError("Database schema validation failed.") from error
        finally:
            engine.dispose()
    except sqlite3.Error as error:
        raise BackupError("SQLite database validation failed.") from error
    finally:
        connection.close()


def snapshot(source: Path, output: Path) -> None:
    """Publish a validated single-file snapshot, refusing every existing output."""
    if os.path.lexists(output):
        raise BackupError("Destination already exists; choose a new path.")
    if not output.parent.is_dir():
        raise BackupError("Destination parent directory must already exist.")
    source_connection = read_only_connection(source)
    staging_path: Path | None = None
    try:
        # A private staging file in the destination directory permits atomic publication.
        with tempfile.NamedTemporaryFile(
            prefix=".jobbr-snapshot-", suffix=".db", dir=output.parent, delete=False
        ) as staging:
            staging_path = Path(staging.name)
        started = time.monotonic()

        def progress(_status: int, _remaining: int, _total: int) -> None:
            if time.monotonic() - started > BACKUP_TIMEOUT_SECONDS:
                raise BackupError("Database snapshot timed out; retry when writes have settled.")

        target_connection = sqlite3.connect(staging_path)
        try:
            source_connection.backup(target_connection, pages=256, progress=progress, sleep=0.05)
            target_connection.execute("PRAGMA journal_mode=DELETE")
        finally:
            target_connection.close()
        verify(staging_path)
        with staging_path.open("rb") as staging_file:
            os.fsync(staging_file.fileno())
        # Hard-link publication fails if a file or symlink appears while backing up.
        # Never use replace/rename here: those can overwrite an existing destination.
        try:
            os.link(staging_path, output)
        except FileExistsError as error:
            raise BackupError("Destination already exists; choose a new path.") from error
        if os.name == "posix":
            directory_fd = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        source_connection.close()
        if staging_path is not None:
            staging_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("backup", "restore"):
        command = commands.add_parser(name)
        command.add_argument("source", type=Path, help="Existing SQLite database or snapshot")
        command.add_argument("output", type=Path, help="New destination path; never overwritten")
    check = commands.add_parser("verify")
    check.add_argument("source", type=Path)
    arguments = parser.parse_args()
    try:
        if arguments.command == "verify":
            verify(arguments.source)
            print(f"Verified: {arguments.source}")
        else:
            snapshot(arguments.source, arguments.output)
            print(f"Verified {arguments.command}: {arguments.output}")
    except BackupError as error:
        print(f"Backup tool: {error}", file=sys.stderr)
        return 1
    except (OSError, sqlite3.Error):
        # Do not emit database content, configuration or connection secrets.
        print("Backup tool: database or filesystem operation failed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
