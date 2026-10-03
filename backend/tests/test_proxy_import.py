import sqlite3
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from jobbr import db
from jobbr.models import Application, Job, JobStatus, Stage
from jobbr.proxy_import import import_leads, reviewed_leads
from tests.conftest import API


def test_private_review_evidence_cannot_be_reextracted(client, monkeypatch):
    def forbidden_provider(*args, **kwargs):
        pytest.fail("Private recruiter evidence must never reach posting extraction")

    monkeypatch.setattr("jobbr.services.extract", forbidden_provider)
    with Session(db.get_engine()) as session:
        import_leads(session, [{"id": "sig_no_extract", "summary": "Private review"}], apply=True)
        job = session.exec(select(Job)).one()
        job_id, original = job.id, job.raw_text

    response = client.post(f"{API}/jobs/{job_id}/reextract")
    assert response.status_code == 422
    assert "cannot be re-extracted" in response.json()["detail"]
    with Session(db.get_engine()) as session:
        job = session.get(Job, job_id)
        assert job.raw_text == original
        assert job.summary is None


def test_reviewed_leads_preview_idempotence_and_user_edits():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    leads = [
        {
            "id": "sig_test",
            "company_name": "Example",
            "role_title": "Engineer",
            "summary": "Recruiter pitch",
            "received_at": "2026-10-01T22:00:00Z",
            "contact_name": "Recruiter",
            "contact_url": "https://example.com/contact",
            "conversation_id": "cnv_test",
        }
    ]
    with Session(engine) as session:
        assert import_leads(session, leads) == {"reviewed": 1, "created": 1, "existing": 0}
        assert session.exec(select(Job)).first() is None
        assert import_leads(session, leads, apply=True)["created"] == 1
        job = session.exec(select(Job)).one()
        assert job.status == JobStatus.unknown
        assert job.posted_at is None
        application = session.exec(select(Application)).one()
        assert "2026-10-01T22:00:00Z" in application.notes
        application.stage = Stage.applied
        application.notes = "User edited notes"
        session.add(application)
        session.commit()
        assert import_leads(session, leads, apply=True)["existing"] == 1
        session.refresh(application)
        assert application.stage == Stage.applied
        assert application.notes == "User edited notes"


def test_unknown_employer_and_title_are_not_invented():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        import_leads(session, [{"id": "sig_unknown"}], apply=True)
        job = session.exec(select(Job)).one()
        assert job.title == "Recruiting lead (title not supplied)"
        assert job.status == JobStatus.unknown
        assert job.url is None


def test_source_selection_is_read_only_and_excludes_unreviewed(tmp_path: Path):
    source = tmp_path / "proxy.db"
    with sqlite3.connect(source) as connection:
        connection.executescript("""
            CREATE TABLE recruiter_signal(id, conversation_id, role_title, summary,
                received_at, hiring_company_id, recruiter_person_id, state);
            CREATE TABLE company(id, name);
            CREATE TABLE person(id, full_name, primary_profile_url);
            INSERT INTO recruiter_signal(id, state) VALUES('sig_reviewed','reviewing');
            INSERT INTO recruiter_signal(id, state) VALUES('sig_candidate','new');
            INSERT INTO recruiter_signal(id, state) VALUES('sig_declined','declined');
        """)
    before = source.read_bytes()
    assert [row["id"] for row in reviewed_leads(source)] == ["sig_reviewed"]
    assert source.read_bytes() == before


def test_invalid_batch_does_not_partially_import():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        with pytest.raises(ValueError, match="Invalid proxy signal ID"):
            import_leads(session, [{"id": "sig_valid"}, {"id": "invalid"}], apply=True)
        assert session.exec(select(Job)).first() is None
