from copy import deepcopy

import pytest
from sqlmodel import Session, select

from jobbr import db, services
from jobbr.extract import Result
from jobbr.models import (
    Application,
    ApplicationEvent,
    Company,
    Extraction,
    ExtractMethod,
    Job,
    Match,
    Profile,
    SavedCareerDraft,
)
from jobbr.schemas import JobExtraction
from tests.conftest import API, ARTICLE

URL = "https://acme.test/jobs/unchanged"
TEXT = "Engineer\nBuild reliable Python services and help improve our platform."


@pytest.fixture
def extraction_calls(monkeypatch):
    calls = []

    def recording(text, html=None, title=None, company=None):
        calls.append((text, html, title, company))
        return Result(
            data=JobExtraction(
                company=company or "Acme", title=title or "Engineer", skills=["python"]
            ),
            method=ExtractMethod.llm,
            model="sentinel-model",
            input_tokens=11,
            output_tokens=7,
            latency_ms=99,
            cost_usd=0.25,
        )

    monkeypatch.setattr(services, "extract", recording)
    return calls


def add(client, **overrides):
    response = client.post(f"{API}/jobs", json={"url": URL, "text": TEXT, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def state():
    with Session(db.get_engine()) as session:
        return {
            model.__name__: [
                row.model_dump(mode="json") for row in session.exec(select(model)).all()
            ]
            for model in (
                Job,
                Company,
                Match,
                Application,
                ApplicationEvent,
                Extraction,
                SavedCareerDraft,
            )
        }


@pytest.mark.parametrize("same_hints", [False, True])
def test_unchanged_repeat_preserves_all_records_without_extracting(
    client, extraction_calls, same_hints
):
    job = add(client)
    assert len(extraction_calls) == 1
    job_id = job["id"]
    client.put(
        f"{API}/jobs/{job_id}/application",
        json={
            "stage": "interview",
            "notes": "Keep my private notes",
            "next_step_at": "2026-10-20T09:30:00",
        },
    )
    corrected = client.patch(
        f"{API}/jobs/{job_id}",
        json={
            "title": "Reviewed Engineer",
            "company": "Reviewed Acme",
            "summary": "Keep my corrected summary",
            "skills": ["python", "sql"],
        },
    )
    assert corrected.status_code == 200
    with Session(db.get_engine()) as session:
        owner = session.exec(select(Profile)).first()
        assert owner is not None
        session.add(
            SavedCareerDraft(
                job_id=job_id,
                profile_id=owner.id,
                result={"kind": "cover_letter", "draft": {"cover_letter": "Keep my saved draft"}},
                source_fingerprint="x" * 64,
            )
        )
        session.commit()
    before = deepcopy(state())

    def unexpected(*args, **kwargs):
        pytest.fail("An unchanged repeat reached extraction")

    # Fail at the extractor boundary even if the provider happens to be disabled.
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(services, "extract", unexpected)
        hints = {"title": "Reviewed Engineer", "company": " Reviewed Acme "} if same_hints else {}
        repeated = add(client, text="\n " + TEXT + " \n", **hints)
    assert repeated["id"] == job_id
    assert repeated["title"] == "Reviewed Engineer"
    assert state() == before
    assert len(extraction_calls) == 1


@pytest.mark.parametrize("change", ["text", "title", "company"])
def test_changed_text_or_explicit_hint_still_extracts(client, extraction_calls, change):
    original = add(client)
    change_body = {
        "text": {"text": TEXT + "\nA newly disclosed requirement."},
        "title": {"title": "Changed title"},
        "company": {"company": "Different company"},
    }[change]
    updated = add(client, **change_body)
    assert updated["id"] == original["id"]
    assert len(extraction_calls) == 2
    with Session(db.get_engine()) as session:
        assert len(session.exec(select(Extraction)).all()) == 2
    if change == "title":
        assert updated["title"] == "Changed title"
    if change == "company":
        assert updated["company"]["name"] == "Different company"


def test_saved_prefix_of_truncated_source_is_not_unchanged(client, extraction_calls):
    full = "Engineer\n" + "x" * (services.RAW_TEXT_LIMIT + 100)
    first = add(client, text=full)
    assert len(first["raw_text"]) == services.RAW_TEXT_LIMIT
    add(client, text=first["raw_text"])
    assert len(extraction_calls) == 2


def test_changed_tail_after_truncation_still_extracts(client, extraction_calls):
    prefix = "Engineer\n" + "x" * services.RAW_TEXT_LIMIT
    add(client, text=prefix + "first tail")
    add(client, text=prefix + "changed tail")
    assert len(extraction_calls) == 2


def test_repeat_without_url_still_creates_distinct_jobs(client, extraction_calls):
    first = add(client, url=None)
    second = add(client, url=None)
    assert first["id"] != second["id"]
    assert len(extraction_calls) == 2


def test_different_exact_url_still_extracts(client, extraction_calls):
    first = add(client)
    second = add(client, url=URL + "?source=other")
    assert first["id"] != second["id"]
    assert len(extraction_calls) == 2


def test_explicit_reextract_remains_explicit(client, extraction_calls):
    job = add(client)
    response = client.post(f"{API}/jobs/{job['id']}/reextract")
    assert response.status_code == 200
    assert len(extraction_calls) == 2


def test_fetched_jsonld_updates_even_when_visible_text_is_unchanged(client, monkeypatch):
    monkeypatch.setattr(services, "fetch_html", lambda url: (url, ARTICLE))
    first = client.post(f"{API}/jobs", json={"url": URL}).json()
    changed_html = ARTICLE.replace('"minValue":90', '"minValue":100')
    monkeypatch.setattr(services, "fetch_html", lambda url: (url, changed_html))
    response = client.post(f"{API}/jobs", json={"url": URL})
    assert response.status_code == 201
    changed = response.json()
    assert changed["id"] == first["id"]
    assert changed["raw_text"] == first["raw_text"]
    assert changed["comp_min"] == 100 * 2080
    assert changed["comp_min"] != first["comp_min"]
    assert len(client.get(f"{API}/jobs/{first['id']}").json()["extractions"]) == 2
