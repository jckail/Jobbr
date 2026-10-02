"""Opt-in integration tests isolated inside a dedicated PostgreSQL test database."""

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlmodel import Session, SQLModel, select

from jobbr import db
from jobbr.main import create_app
from jobbr.models import Application, ApplicationEvent, Company, Extraction, Job, Match
from jobbr.schema import SchemaMismatchError, verify_schema
from migrations.baseline import metadata as initial_schema
from tests.conftest import API, ARTICLE, reset_settings
from tests.test_profile_revisions import concurrent_revision_saves
from tests.test_tailoring import (
    concurrent_tailoring_saves,
    source_capture_saved_during_active_change,
)


@pytest.fixture
def postgres(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    raw_url = os.environ.get("JOBBR_TEST_POSTGRES_URL")
    if not raw_url:
        pytest.skip("Set JOBBR_TEST_POSTGRES_URL to run dedicated PostgreSQL integration tests")
    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql" or url.database != "jobbr_test":
        pytest.fail("PostgreSQL integration tests require the dedicated database named jobbr_test")
    if "options" in url.query:
        pytest.fail("Test URL must not override PostgreSQL options or schema search_path")
    url = url.set(drivername="postgresql+psycopg")
    admin = create_engine(url)
    schema_name = f"jobbr_test_{uuid4().hex}"
    with admin.begin() as connection:
        actual_database, actual_schema = connection.execute(
            text("SELECT current_database(), current_schema()")
        ).one()
        if actual_database != "jobbr_test" or actual_schema != "public":
            pytest.fail("Refusing to run tests outside jobbr_test with the default public schema")
        connection.execute(CreateSchema(schema_name))
    isolated_url = url.update_query_dict({"options": f"-csearch_path={schema_name}"})
    monkeypatch.setenv("JOBBR_DATABASE_URL", isolated_url.render_as_string(hide_password=False))
    monkeypatch.setenv("JOBBR_STATIC_DIR", "/nonexistent")
    for variable in (
        "JOBBR_OPENAI_API_KEY",
        "OPENAI_API_KEY",
        "JOBBR_ANTHROPIC_API_KEY",
        "ANTHROPIC_API_KEY",
        "JOBBR_AI_PROVIDER",
        "JOBBR_ANTHROPIC_MODEL",
        "JOBBR_API_TOKEN",
    ):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr("jobbr.services.fetch_html", lambda url: (url, ARTICLE))
    reset_settings()
    try:
        with db.get_engine().connect() as connection:
            assert connection.execute(text("SELECT current_schema()")).scalar_one() == schema_name
        yield
    finally:
        db.get_engine().dispose()
        reset_settings()
        # Only this fixture's newly created schema is removed; public is never modified.
        with admin.begin() as connection:
            connection.execute(DropSchema(schema_name, cascade=True))
        admin.dispose()


def test_postgres_migrations_and_pipeline_survive_reopening(postgres: None) -> None:
    db.init_db()
    db.init_db()
    with db.get_engine().connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "0007_canonical_capture"
        )
        verify_schema(connection, SQLModel.metadata)
        assert set(inspect(connection).get_table_names()) == {
            "company",
            "profile",
            "job",
            "extraction",
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
            "jobexternalidentity",
            "capturelease",
            "alembic_version",
        }

    with TestClient(create_app()) as client:
        profile = client.put(f"{API}/profile", json={"resume_text": "Python SQL Airflow"})
        assert profile.status_code == 200, profile.text
        response = client.post(f"{API}/jobs", json={"url": "https://acme.test/jobs/postgres"})
        assert response.status_code == 201, response.text
        job = response.json()
        job_id = job["id"]
        assert job["company"]["name"] == "Acme"
        assert "kafka" in job["match"]["missing_skills"]
        rematched = client.put(f"{API}/profile", json={"resume_text": "Python SQL Kafka Airflow"})
        assert rematched.status_code == 200, rematched.text
        moved = client.put(
            f"{API}/jobs/{job_id}/application", json={"stage": "applied", "notes": "Keep notes"}
        )
        assert moved.status_code == 200, moved.text
        assert moved.json()["application"]["stage"] == "applied"

    db.get_engine().dispose()
    reset_settings()
    # A new pool and transaction must see the data committed by API transactions.
    with Session(db.get_engine()) as session:
        persisted_job = session.get(Job, job_id)
        assert persisted_job is not None
        assert persisted_job.skills == job["skills"]
        assert {"python", "sql", "kafka"} <= set(persisted_job.skills)
        application = session.exec(select(Application).where(Application.job_id == job_id)).one()
        assert application.notes == "Keep notes"
        assert application.applied_at is not None
        assert len(session.exec(select(ApplicationEvent)).all()) == 2
        assert len(session.exec(select(Extraction)).all()) == 1

    with TestClient(create_app()) as client:
        detail = client.get(f"{API}/jobs/{job_id}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["match"]["missing_skills"] == []
        assert detail.json()["application"]["stage"] == "applied"
        assert client.delete(f"{API}/jobs/{job_id}").status_code == 204
        assert client.get(f"{API}/jobs/{job_id}").status_code == 404
    with Session(db.get_engine()) as session:
        for model in (Job, Application, ApplicationEvent, Extraction, Match):
            assert session.exec(select(model)).all() == []
        assert session.exec(select(Company)).one().name == "Acme"


def test_postgres_adopts_existing_v2_without_rewriting_data(postgres: None) -> None:
    initial_schema.create_all(db.get_engine())
    with Session(db.get_engine()) as session:
        company = Company(name="Preserved PostgreSQL company")
        session.add(company)
        session.commit()
        company_id = company.id
    db.init_db()
    db.init_db()
    with Session(db.get_engine()) as session:
        preserved = session.get(Company, company_id)
        assert preserved is not None
        assert preserved.name == "Preserved PostgreSQL company"


def test_postgres_rejects_enum_schema_drift(postgres: None) -> None:
    db.init_db()
    with db.get_engine().begin() as connection:
        connection.execute(text("ALTER TYPE seniority ADD VALUE 'obsolete_level'"))
    with pytest.raises(SchemaMismatchError, match="Database schema mismatch"):
        db.init_db()


def test_concurrent_postgres_startup_serializes_migrations(postgres, monkeypatch):
    engine = db.get_engine()
    initial_schema.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO company (name, created_at) "
                "VALUES ('Concurrent survivor', '2026-01-01')"
            )
        )
    first_inside = Event()
    release_first = Event()
    second_attempting = Event()
    second_pid = []
    observed = []
    actual_upgrade = db.command.upgrade

    def hold_first(*args, **kwargs):
        if not first_inside.is_set():
            first_inside.set()
            assert release_first.wait(timeout=1.5), "Migration release exceeded the lock budget"
        return actual_upgrade(*args, **kwargs)

    def before_statement(connection, cursor, statement, parameters, context, executemany):
        if "pg_advisory_xact_lock" in statement:
            observed.append(connection.connection.driver_connection.info.backend_pid)
            if len(observed) == 2:
                second_pid.append(observed[-1])
                second_attempting.set()

    monkeypatch.setattr(db.command, "upgrade", hold_first)
    event.listen(engine, "before_cursor_execute", before_statement)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(db.init_db)
            assert first_inside.wait(timeout=1)
            second = workers.submit(db.init_db)
            try:
                assert second_attempting.wait(timeout=0.5)
                waiting = False
                with engine.connect() as observer:
                    for _ in range(40):
                        waiting = observer.execute(
                            text(
                                "SELECT EXISTS (SELECT 1 FROM pg_locks "
                                "WHERE pid = :pid AND NOT granted)"
                            ),
                            {"pid": second_pid[0]},
                        ).scalar_one()
                        if waiting:
                            break
                        second_attempting.clear()
                        second_attempting.wait(timeout=0.01)
                assert waiting, "Second instance did not block on the migration advisory lock"
            finally:
                release_first.set()
            first.result(timeout=5)
            second.result(timeout=5)
    finally:
        release_first.set()
        event.remove(engine, "before_cursor_execute", before_statement)
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0007_canonical_capture"
        )
        assert (
            connection.execute(text("SELECT name FROM company")).scalar_one()
            == "Concurrent survivor"
        )
        verify_schema(connection, SQLModel.metadata)


def test_first_owner_creation_is_serialized_in_postgres(postgres):
    from tests.test_profile_concurrency import concurrent_owner_ids  # noqa: PLC0415

    db.init_db()
    concurrent_owner_ids()


def test_postgres_revision_save_serializes_expected_check(postgres: None) -> None:
    db.init_db()
    concurrent_revision_saves()


def test_postgres_tailoring_provenance_acceptance_and_concurrent_capacity(postgres, monkeypatch):
    db.init_db()
    profile_id, job_id, revision_id, receipt_id, content = (
        source_capture_saved_during_active_change(monkeypatch)
    )
    concurrent_tailoring_saves(profile_id, job_id, revision_id, receipt_id, content)
