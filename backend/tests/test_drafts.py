from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier

import pytest
from sqlmodel import Session, select

from jobbr import config, db, drafts
from jobbr.career import CareerResult
from jobbr.models import Job, Profile, SavedCareerDraft
from tests.conftest import API


def result():
    return {
        "kind": "cover_letter",
        "model": "test-model",
        "input_tokens": 100,
        "output_tokens": 80,
        "requires_review": True,
        "draft": {
            "cover_letter": "Dear hiring team, I build Python services.",
            "interview_questions": [],
            "strengths": ["Python"],
            "gaps": ["SQL needs a real example"],
            "questions_to_ask": ["How do you measure reliability?"],
            "evidence_quotes": ["Python"],
            "review_notes": ["Verify every claim before use."],
        },
    }


@pytest.fixture
def owner(client, env):
    env.setenv("JOBBR_API_TOKEN", "draft-token")
    config.get_settings.cache_clear()
    client.headers["X-Jobbr-Token"] = "draft-token"
    response = client.post(
        f"{API}/jobs", json={"text": "Engineer Python services", "company": "Acme"}
    )
    assert response.status_code == 201
    return client, response.json()["id"]


def test_explicit_save_reload_delete_and_job_cleanup(owner):
    client, job_id = owner
    path = f"{API}/jobs/{job_id}/career/drafts"
    assert client.get(path).json() == []
    body = {"result": result()}
    response = client.post(path, json=body)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["result"]["draft"] == body["result"]["draft"]
    assert saved["result"]["requires_review"] is True
    assert saved["result"]["generated_at"] is None
    assert len(saved["source_fingerprint"]) == 64
    assert "profile_id" not in saved
    assert client.get(path).json() == [saved]
    assert client.get(f"{path}/{saved['id']}").json() == saved
    assert client.delete(f"{path}/{saved['id']}").status_code == 204
    assert client.get(f"{path}/{saved['id']}").status_code == 404
    assert client.get(path).json() == []
    assert client.post(path, json=body).status_code == 201
    assert client.delete(f"{API}/jobs/{job_id}").status_code == 204
    with Session(db.get_engine()) as session:
        assert session.exec(select(SavedCareerDraft)).all() == []


def test_generation_remains_transient(owner, monkeypatch):
    client, job_id = owner

    async def generated(*args, **kwargs):
        return CareerResult.model_validate(result())

    monkeypatch.setattr("jobbr.api.generate_career", generated)
    assert client.post(f"{API}/jobs/{job_id}/career/cover_letter").status_code == 200
    assert client.get(f"{API}/jobs/{job_id}/career/drafts").json() == []


def test_public_read_only_mode_never_exposes_drafts(owner):
    client, job_id = owner
    path = f"{API}/jobs/{job_id}/career/drafts"
    saved = client.post(path, json={"result": result()}).json()
    client.headers.pop("X-Jobbr-Token")
    assert client.get(f"{API}/jobs/{job_id}").status_code == 200
    assert client.get(path).status_code == 401
    assert client.get(f"{path}/{saved['id']}").status_code == 401
    assert client.post(path, json={"result": result()}).status_code == 401
    assert client.delete(f"{path}/{saved['id']}").status_code == 401
    client.headers["X-Jobbr-Token"] = "wrong-token"
    assert client.get(path).status_code == 401


def test_unprotected_instance_cannot_save_or_read_private_drafts(client):
    path = f"{API}/jobs/1/career/drafts"
    assert client.get(path).status_code == 401
    assert client.post(path, json={"result": result()}).status_code == 401


def test_draft_job_and_profile_scope(owner):
    client, job_id = owner
    path = f"{API}/jobs/{job_id}/career/drafts"
    saved = client.post(path, json={"result": result()}).json()
    other_job = client.post(f"{API}/jobs", json={"text": "Another Python role"}).json()["id"]
    assert client.get(f"{API}/jobs/{other_job}/career/drafts/{saved['id']}").status_code == 404
    assert client.delete(f"{API}/jobs/{other_job}/career/drafts/{saved['id']}").status_code == 404
    with Session(db.get_engine()) as session:
        other_profile = Profile(name="Other")
        session.add(other_profile)
        session.flush()
        foreign = SavedCareerDraft(
            job_id=job_id,
            profile_id=other_profile.id,
            result=result(),
            source_fingerprint="x" * 64,
        )
        session.add(foreign)
        session.commit()
        foreign_id = foreign.id
    assert client.get(f"{path}/{foreign_id}").status_code == 404
    assert len(client.get(path).json()) == 1


@pytest.mark.parametrize(
    "mutation", ["null", "extra", "too_long", "too_many", "negative", "unreviewed", "budget"]
)
def test_saved_payload_is_bounded_and_shape_validated(owner, mutation):
    client, job_id = owner
    submitted = deepcopy(result())
    if mutation == "null":
        submitted["draft"] = None
    elif mutation == "extra":
        submitted["resume_text"] = "Must not be stored"
    elif mutation == "too_long":
        submitted["draft"]["cover_letter"] = "a" * 12_001
    elif mutation == "too_many":
        submitted["draft"]["evidence_quotes"] = ["Python"] * 21
    elif mutation == "negative":
        submitted["input_tokens"] = -1
    elif mutation == "unreviewed":
        submitted["requires_review"] = False
    else:
        submitted["draft"]["strengths"] = ["a" * 2000] * 20
        submitted["draft"]["gaps"] = ["a" * 2000] * 20
    path = f"{API}/jobs/{job_id}/career/drafts"
    assert client.post(path, json={"result": submitted}).status_code == 422
    assert client.get(path).json() == []


def test_submitted_evidence_is_not_certified_and_source_blob_not_copied(owner):
    client, job_id = owner
    client.put(f"{API}/profile", json={"resume_text": "Private resume source that is not a draft"})
    path = f"{API}/jobs/{job_id}/career/drafts"
    saved = client.post(path, json={"result": result()})
    assert saved.status_code == 201
    assert "Private resume source" not in saved.text
    assert saved.json()["result"]["draft"]["evidence_quotes"] == ["Python"]
    assert saved.json()["result"]["requires_review"] is True
    client.put(f"{API}/profile", json={"resume_text": "Changed profile facts"})
    changed = client.post(path, json={"result": result()}).json()
    assert changed["source_fingerprint"] != saved.json()["source_fingerprint"]
    assert client.get(path).json()[0]["id"] == changed["id"]


def test_saved_draft_capacity_is_bounded(owner):
    client, job_id = owner
    with Session(db.get_engine()) as session:
        profile = session.exec(select(Profile)).first()
        assert profile is not None
        session.add_all(
            [
                SavedCareerDraft(
                    job_id=job_id,
                    profile_id=profile.id,
                    result=result(),
                    source_fingerprint="x" * 64,
                )
                for _ in range(50)
            ]
        )
        session.commit()
    path = f"{API}/jobs/{job_id}/career/drafts"
    assert len(client.get(path).json()) == 50
    assert client.post(path, json={"result": result()}).status_code == 409


def test_concurrent_saves_cannot_exceed_capacity(owner):
    _, job_id = owner
    engine = db.get_engine()
    with Session(engine) as session:
        profile = session.exec(select(Profile)).first()
        assert profile is not None
        profile_id = profile.id
        session.add_all(
            [
                SavedCareerDraft(
                    job_id=job_id,
                    profile_id=profile_id,
                    result=result(),
                    source_fingerprint="x" * 64,
                )
                for _ in range(49)
            ]
        )
        session.commit()
    barrier = Barrier(2)

    def save_once():
        with Session(engine) as session:
            job = session.get(Job, job_id)
            profile = session.get(Profile, profile_id)
            assert job is not None
            assert profile is not None
            barrier.wait(timeout=3)
            try:
                drafts.save(session, job, profile, "Acme", drafts.DraftSave(result=result()))
            except drafts.DraftLimitError:
                return False
            return True

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: save_once(), range(2)))
    assert sorted(results) == [False, True]
    with Session(engine) as session:
        assert len(session.exec(select(SavedCareerDraft)).all()) == 50
