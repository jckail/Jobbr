"""Saved identity API hydration across ATS aliases and legacy ambiguity."""

from sqlalchemy import delete, func
from sqlmodel import Session, select

from jobbr import canonical_repo, db
from jobbr.canonical import Identity
from jobbr.canonical_models import JobExternalIdentity
from jobbr.models import Job
from tests.conftest import API

BODY = {
    "url": "https://boards.greenhouse.io/acme/jobs/123?source=original",
    "text": "Platform Engineer at Acme. Build Python and SQL platforms with a team of engineers. "
    * 3,
}
EXPECTED = {"provider": "greenhouse", "board": "acme", "posting_id": "123"}


def test_list_and_detail_expose_identity_without_rewriting_first_url(client):
    saved = client.post(API + "/jobs", json=BODY).json()
    alias = client.post(
        API + "/jobs", json={**BODY, "url": "https://job-boards.greenhouse.io/acme/jobs/123#apply"}
    ).json()
    assert alias["id"] == saved["id"]
    listed = client.get(API + "/jobs").json()
    assert len(listed) == 1
    assert listed[0]["external_identity"] == EXPECTED
    assert listed[0]["url"] == BODY["url"]
    detail = client.get(API + f"/jobs/{saved['id']}").json()
    assert detail["external_identity"] == EXPECTED
    assert detail["url"] == BODY["url"]


def test_legacy_hydration_does_not_adopt_or_merge_duplicate_jobs(client):
    saved = client.post(API + "/jobs", json=BODY).json()
    with Session(db.get_engine()) as s:
        s.execute(delete(JobExternalIdentity))
        job = s.get(Job, saved["id"])
        assert job is not None
        duplicate = Job.model_validate(
            {
                **job.model_dump(),
                "id": None,
                "url": "https://job-boards.greenhouse.io/acme/jobs/123",
            }
        )
        s.add(duplicate)
        s.commit()
        duplicate_id = duplicate.id
    listed = client.get(API + "/jobs").json()
    assert len(listed) == 2
    assert {job["id"] for job in listed} == {saved["id"], duplicate_id}
    assert all(job["external_identity"] == EXPECTED for job in listed)
    with Session(db.get_engine()) as s:
        assert s.exec(select(func.count()).select_from(JobExternalIdentity)).one() == 0
        assert s.exec(select(func.count()).select_from(Job)).one() == 2


def test_mapping_survives_url_edit_but_ambiguous_mapping_is_unknown(client):
    saved = client.post(API + "/jobs", json=BODY).json()
    with Session(db.get_engine()) as s:
        job = s.get(Job, saved["id"])
        assert job is not None
        job.url = "https://example.com/edited"
        s.add(job)
        s.commit()
    assert client.get(API + "/jobs").json()[0]["external_identity"] == EXPECTED
    with Session(db.get_engine()) as s:
        canonical_repo.bind_identity(s, Identity("greenhouse", "other", "456"), saved["id"])
        s.commit()
    assert client.get(API + "/jobs").json()[0]["external_identity"] is None


def test_generic_url_has_no_asserted_ats_identity(client):
    job = client.post(API + "/jobs", json={**BODY, "url": "https://example.com/role"}).json()
    assert job["external_identity"] is None
    assert client.get(API + "/jobs").json()[0]["external_identity"] is None
