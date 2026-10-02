from io import StringIO
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlmodel import Session

from jobbr import db
from jobbr.models import Company, Job
from jobbr.schema import SchemaMismatchError
from migrations.baseline import metadata as initial_schema


def version() -> str:
    with db.get_engine().connect() as connection:
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()


def test_fresh_database_upgrade_is_repeatable(env: pytest.MonkeyPatch) -> None:
    db.init_db()
    assert version() == "0006_extension_capture"
    assert set(inspect(db.get_engine()).get_table_names()) == {
        "alembic_version",
        "company",
        "job",
        "extraction",
        "profile",
        "match",
        "application",
        "applicationevent",
        "savedcareerdraft",
        "authtransaction",
        "authsession",
        "authstoreguard",
        "profilerevision",
        "profilerevisionhead",
        "tailoringreceipt",
        "savedtailoringdraft",
        "capturepairing",
        "capturegrant",
        "capturereceipt",
        "capturethrottle",
    }
    db.init_db()
    assert version() == "0006_extension_capture"


def test_adopts_unversioned_v2_without_losing_data(env: pytest.MonkeyPatch) -> None:
    initial_schema.create_all(db.get_engine())
    with Session(db.get_engine()) as session:
        company = Company(name="Preserved company")
        session.add(company)
        session.flush()
        job = Job(company_id=company.id, title="Preserved job", skills=["Python"])
        session.add(job)
        session.commit()
        company_id, job_id = company.id, job.id
    db.init_db()
    db.init_db()
    assert version() == "0006_extension_capture"
    with Session(db.get_engine()) as session:
        assert session.get(Company, company_id).name == "Preserved company"
        assert session.get(Job, job_id).skills == ["Python"]


@pytest.mark.parametrize(
    "mutation",
    [
        "ALTER TABLE job ADD COLUMN obsolete TEXT",
        "DROP INDEX ix_company_name",
        "ALTER TABLE job RENAME COLUMN title TO obsolete_title",
        "CREATE TABLE legacy_data (id INTEGER PRIMARY KEY)",
    ],
)
def test_rejects_mismatched_unversioned_schema(
    env: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    initial_schema.create_all(db.get_engine())
    with db.get_engine().begin() as connection:
        connection.execute(text(mutation))
        connection.execute(
            text("INSERT INTO company (name, created_at) VALUES ('Keep me', '2026-01-01')")
        )
    with pytest.raises(SchemaMismatchError, match="Database schema mismatch"):
        db.init_db()
    with db.get_engine().connect() as connection:
        assert connection.execute(text("SELECT name FROM company")).scalar_one() == "Keep me"
        if "alembic_version" in inspect(connection).get_table_names():
            assert (
                connection.execute(text("SELECT count(*) FROM alembic_version")).scalar_one() == 0
            )


def test_rejects_drift_in_versioned_database(env: pytest.MonkeyPatch) -> None:
    db.init_db()
    with db.get_engine().begin() as connection:
        connection.execute(text("DROP INDEX ix_company_name"))
    with pytest.raises(SchemaMismatchError, match="Database schema mismatch"):
        db.init_db()


def test_rejects_partial_or_legacy_database(env: pytest.MonkeyPatch) -> None:
    with db.get_engine().begin() as connection:
        connection.execute(text("CREATE TABLE jobs (id INTEGER PRIMARY KEY, title TEXT)"))
        connection.execute(text("INSERT INTO jobs VALUES (1, 'Legacy job')"))
    with pytest.raises(SchemaMismatchError, match=r"unexpected tables.*jobs"):
        db.init_db()
    with db.get_engine().connect() as connection:
        assert connection.execute(text("SELECT title FROM jobs")).scalar_one() == "Legacy job"
        assert "company" not in inspect(connection).get_table_names()


def test_postgresql_offline_migration_creates_each_enum_once(tmp_path: Path) -> None:
    """Compile PostgreSQL DDL without needing a database server."""
    output = StringIO()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"), output_buffer=output)
    # Offline mode only needs a dialect; keep credentials out of the fixture.
    config.attributes["offline_url"] = "postgresql+psycopg://localhost/jobbr"
    command.upgrade(config, "head", sql=True)
    ddl = output.getvalue()
    assert ddl.count("CREATE TYPE seniority AS ENUM") == 1
    assert ddl.count("CREATE TYPE remotepolicy AS ENUM") == 1
    assert "CREATE TABLE applicationevent" in ddl
    assert "INSERT INTO alembic_version" in ddl


@pytest.mark.parametrize("mismatch", ["nullable", "type", "foreign_key", "primary_key"])
def test_rejects_constraint_and_type_mismatches(
    env: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    altered = sa.MetaData()
    for table in initial_schema.sorted_tables:
        table.to_metadata(altered)
    if mismatch == "nullable":
        altered.tables["company"].c.name.nullable = True
    elif mismatch == "type":
        altered.tables["company"].c.created_at.type = sa.String()
    elif mismatch == "foreign_key":
        job = altered.tables["job"]
        job.constraints = {
            constraint
            for constraint in job.constraints
            if not isinstance(constraint, sa.ForeignKeyConstraint)
        }
    else:
        company = altered.tables["company"]
        company.c.id.primary_key = False
        company.primary_key = sa.PrimaryKeyConstraint()
        company.constraints = {
            constraint
            for constraint in company.constraints
            if not isinstance(constraint, sa.PrimaryKeyConstraint)
        }
    altered.create_all(db.get_engine())
    with pytest.raises(SchemaMismatchError, match="Database schema mismatch"):
        db.init_db()
