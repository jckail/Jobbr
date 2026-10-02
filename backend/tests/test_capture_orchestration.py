"""Offline orchestration proofs, with optional isolated real PostgreSQL coverage."""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlmodel import Session, select

from jobbr import canonical, canonical_repo, config, db, extract, services
from jobbr.canonical_models import CaptureLease, JobExternalIdentity
from jobbr.extract import Result
from jobbr.models import Application, Extraction, ExtractMethod, Job, pk
from jobbr.schemas import JobCreate, JobExtraction
from tests.conftest import API
from tests.test_extension_capture import capability as capture_capability  # noqa: F401
from tests.test_extension_capture import capture_headers, connect
from tests.test_postgres import postgres  # noqa: F401 - exposes the isolated fixture

URL = "https://boards.greenhouse.io/acme/jobs/123"
ALIAS = "https://job-boards.greenhouse.io/acme/jobs/123?utm_source=test"
TEXT = "Engineer builds reliable Python services and data pipelines for our growing product team."


@pytest.fixture(params=["sqlite", "postgres"])
def store(request):
    request.getfixturevalue("env" if request.param == "sqlite" else "postgres")
    db.init_db()
    with Session(db.get_engine()) as session:
        services.get_profile(session)
        session.commit()
    return db.get_engine()


def result(title="Engineer"):
    return Result(
        data=JobExtraction(title=title, company="Acme", skills=["python"]),
        method=ExtractMethod.llm,
        model="offline-sentinel",
    )


def body(url=URL, text=TEXT):
    return JobCreate(url=url, text=text)


def capture(engine, payload):
    with Session(engine) as session:
        return pk(services.ingest(session, payload))


def rows(engine, model):
    with Session(engine) as session:
        return [row.model_dump() for row in session.exec(select(model)).all()]


def test_alias_contention_releases_transaction_and_dispatches_once(store, monkeypatch):
    entered, finish = Event(), Event()
    calls = []

    def blocked(*args, **kwargs):
        calls.append(args)
        entered.set()
        assert finish.wait(10)
        return result()

    monkeypatch.setattr(services, "extract", blocked)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(capture, store, body())
        try:
            assert entered.wait(10)
            with pytest.raises(canonical_repo.CanonicalConflict) as exc:
                capture(store, body(ALIAS))
            assert exc.value.retry_after is not None
            assert len(calls) == 1
        finally:
            finish.set()
        job_id = pending.result(timeout=10)
    assert len(rows(store, Job)) == len(rows(store, Extraction)) == 1
    assert rows(store, CaptureLease) == []
    assert rows(store, JobExternalIdentity)[0]["job_id"] == job_id


def test_unchanged_alias_preserves_children_and_first_url(store, monkeypatch):
    monkeypatch.setattr(services, "extract", lambda *a, **kw: result())
    job_id = capture(store, body())
    with Session(store) as session:
        app = session.exec(select(Application)).one()
        app.notes = "Private reviewed notes"
        session.add(app)
        session.commit()
    before = {model: rows(store, model) for model in (Job, Application, Extraction)}
    monkeypatch.setattr(
        services, "extract", lambda *a, **kw: pytest.fail("unchanged paid dispatch")
    )
    assert capture(store, body(ALIAS)) == job_id
    assert {model: rows(store, model) for model in before} == before


def test_stale_edit_fences_completion_and_cleans_own_lease(store, monkeypatch):
    monkeypatch.setattr(services, "extract", lambda *a, **kw: result())
    job_id = capture(store, body())

    def editing(*args, **kwargs):
        with Session(store) as writer:
            job = writer.get(Job, job_id)
            job.title = "Owner's corrected title"
            writer.add(job)
            writer.commit()
        return result("Stale provider output")

    monkeypatch.setattr(services, "extract", editing)
    with pytest.raises(canonical_repo.CanonicalConflict):
        capture(store, body(ALIAS, TEXT + " Changed responsibilities."))
    assert rows(store, Job)[0]["title"] == "Owner's corrected title"
    assert len(rows(store, Extraction)) == 1
    assert rows(store, CaptureLease) == []


def test_expired_takeover_fences_late_worker(store, monkeypatch):
    entered, finish = Event(), Event()

    def extracting(text, *args, **kwargs):
        if text == TEXT:
            entered.set()
            assert finish.wait(10)
            return result("Late worker")
        return result("New worker")

    monkeypatch.setattr(services, "extract", extracting)
    with ThreadPoolExecutor(max_workers=2) as pool:
        old = pool.submit(capture, store, body())
        try:
            assert entered.wait(10)
            with Session(store) as session:
                lease = session.exec(select(CaptureLease)).one()
                lease.expires_at = time.time() - 1
                session.add(lease)
                session.commit()
            capture(store, body(ALIAS, TEXT + " Fresh responsibilities."))
        finally:
            finish.set()
        with pytest.raises(canonical_repo.CanonicalConflict):
            old.result(timeout=10)
    assert rows(store, Job)[0]["title"] == "New worker"
    assert len(rows(store, Job)) == len(rows(store, Extraction)) == 1
    assert rows(store, CaptureLease) == []


def test_cancel_releases_reservation_without_job(store, monkeypatch):
    def cancelled(*args, **kwargs):
        raise asyncio.CancelledError("offline cancellation")

    monkeypatch.setattr(services, "extract", cancelled)
    with pytest.raises(asyncio.CancelledError, match="offline cancellation"):
        capture(store, body())
    assert rows(store, Job) == rows(store, CaptureLease) == []


def test_delete_during_capture_prevents_recreation_and_keeps_other_map(store, monkeypatch):
    monkeypatch.setattr(services, "extract", lambda *a, **kw: result())
    job_id = capture(store, body())
    other = capture(store, body("https://boards.greenhouse.io/acme/jobs/456"))

    def deleting(*args, **kwargs):
        with Session(store) as session:
            services.delete_job(session, session.get(Job, job_id))
        return result("Deleted worker")

    monkeypatch.setattr(services, "extract", deleting)
    with pytest.raises(canonical_repo.CanonicalConflict):
        capture(store, body(ALIAS, TEXT + " Changed responsibilities."))
    assert [row["id"] for row in rows(store, Job)] == [other]
    assert [row["job_id"] for row in rows(store, JobExternalIdentity)] == [other]
    assert rows(store, CaptureLease) == []


def test_reextract_reservation_blocks_alias_and_stale_edit(store, monkeypatch):
    monkeypatch.setattr(services, "extract", lambda *a, **kw: result())
    job_id = capture(store, body())

    def editing(*args, **kwargs):
        with pytest.raises(canonical_repo.CanonicalConflict):
            capture(store, body(ALIAS, TEXT + " Changed responsibilities."))
        with Session(store) as writer:
            job = writer.get(Job, job_id)
            job.title = "Corrected during reextract"
            writer.add(job)
            writer.commit()
        return result("Stale reextract")

    monkeypatch.setattr(services, "extract", editing)
    with Session(store) as session, pytest.raises(canonical_repo.CanonicalConflict):
        services.reextract(session, session.get(Job, job_id))
    assert rows(store, Job)[0]["title"] == "Corrected during reextract"
    assert rows(store, CaptureLease) == []


def test_generic_queries_and_text_only_captures_remain_distinct(store, monkeypatch):
    monkeypatch.setattr(services, "extract", lambda *a, **kw: result())
    ids = [
        capture(store, body(url))
        for url in ("https://acme.test/jobs/123?a=1", "https://acme.test/jobs/123?a=2", None, None)
    ]
    assert len(set(ids)) == 4


def test_conflict_api_uses_safe_409_and_retry_after(client, monkeypatch):
    def conflict(*args, **kwargs):
        raise canonical_repo.CanonicalConflict("This posting is already being captured.", 10)

    monkeypatch.setattr(services, "ingest", conflict)
    response = client.post(f"{API}/jobs", json=body().model_dump())
    assert response.status_code == 409
    assert response.headers["Retry-After"] == "10"
    assert response.json()["detail"] == "This posting is already being captured."


def test_provider_runs_without_database_transaction(store, monkeypatch):
    with Session(store) as session:

        def checking(*args, **kwargs):
            assert not session.in_transaction()
            return result()

        monkeypatch.setattr(services, "extract", checking)
        services.ingest(session, body())
    assert canonical.identity_for_url(URL) is not None


def test_failed_extraction_never_replaces_existing_reviewed_details(store, monkeypatch):
    monkeypatch.setattr(services, "extract", lambda *a, **kw: result("Reviewed title"))
    job_id = capture(store, body())
    before = rows(store, Job)
    fallback = result("Weaker fallback title")
    fallback.error = "Provider unavailable"
    monkeypatch.setattr(services, "extract", lambda *a, **kw: fallback)
    assert capture(store, body(ALIAS, TEXT + " Changed responsibilities.")) == job_id
    assert rows(store, Job) == before
    attempts = rows(store, Extraction)
    assert len(attempts) == 2
    assert attempts[-1]["ok"] is False
    assert rows(store, CaptureLease) == []


def test_original_failure_survives_cleanup_failure(store, monkeypatch):
    original = RuntimeError("original offline provider failure")

    def failing(*args, **kwargs):
        raise original

    def broken_cleanup(*args, **kwargs):
        raise RuntimeError("cleanup failed")

    monkeypatch.setattr(services, "extract", failing)
    monkeypatch.setattr(canonical_repo, "release", broken_cleanup)
    with pytest.raises(RuntimeError) as exc:
        capture(store, body())
    assert exc.value is original
    assert len(rows(store, CaptureLease)) == 1  # bounded expiry permits later takeover
    assert rows(store, Job) == []


def test_ambiguous_legacy_aliases_reject_without_extraction(store, monkeypatch):
    monkeypatch.setattr(services, "extract", lambda *a, **kw: result())
    job_id = capture(store, body())
    with Session(store) as session:
        canonical_repo.delete_job_refs(session, job_id)
        first = session.get(Job, job_id)
        session.add(Job(company_id=first.company_id, title="Legacy duplicate", url=ALIAS))
        session.commit()
    monkeypatch.setattr(services, "extract", lambda *a, **kw: pytest.fail("ambiguous dispatch"))
    with pytest.raises(canonical_repo.CanonicalConflict, match="Multiple"):
        capture(store, body())
    assert rows(store, CaptureLease) == []
    assert rows(store, JobExternalIdentity) == []


def test_capacity_conflict_occurs_before_provider_dispatch(store, monkeypatch):
    with Session(store) as session:
        for index in range(canonical_repo.MAX_LEASES):
            session.add(
                CaptureLease(
                    resource_key=str(index), nonce="other-worker", expires_at=time.time() + 200
                )
            )
        session.commit()
    monkeypatch.setattr(services, "extract", lambda *a, **kw: pytest.fail("full-cap dispatch"))
    with pytest.raises(canonical_repo.CanonicalConflict, match="temporarily full"):
        capture(store, body())
    assert rows(store, Job) == []


def test_extension_capture_maps_canonical_conflict_without_private_fields(
    capture_capability,  # noqa: F811 - imported parametrized pytest fixture
    monkeypatch,
):
    connected = capture_capability
    grant = connect(connected)

    def conflict(*args, **kwargs):
        raise canonical_repo.CanonicalConflict("This posting is already being captured.", 7)

    monkeypatch.setattr(services, "ingest", conflict)
    response = connected[0].post(
        API + "/extension/captures", json=body().model_dump(), headers=capture_headers(grant)
    )
    assert response.status_code == 409
    assert response.headers["Retry-After"] == "7"
    assert response.json() == {"detail": "This posting is already being captured."}


def test_long_unchanged_alias_uses_full_hash_and_preserves_children(store, monkeypatch):
    long_text = TEXT + " Additional Python responsibilities." * 800
    assert len(long_text) > services.RAW_TEXT_LIMIT
    monkeypatch.setattr(services, "extract", lambda *a, **kw: result())
    job_id = capture(store, body(text=long_text))
    before = {model: rows(store, model) for model in (Job, Application, Extraction)}
    monkeypatch.setattr(
        services, "extract", lambda *a, **kw: pytest.fail("long unchanged dispatch")
    )
    assert capture(store, body(ALIAS, long_text)) == job_id
    assert {model: rows(store, model) for model in before} == before


@pytest.mark.parametrize("action", ["capture", "reextract"])
@pytest.mark.parametrize("with_headers", [False, True])
def test_generic_http_dispatch_uses_deep_checked_settings_snapshot(
    client, env, monkeypatch, action, with_headers
):
    # Prepare stored text without a provider; the regression exercises actual extraction
    # routing after checking a selected configuration, mocking only structured generation.
    saved = client.post(f"{API}/jobs", json=body().model_dump())
    assert saved.status_code == 201, saved.text
    env.setenv("JOBBR_OPENAI_API_KEY", "offline-unused-key")
    env.setenv("JOBBR_MODEL", "reviewed-model")
    config.get_settings.cache_clear()
    selected = config.get_settings()
    checked = (selected.ai_provider, selected.ai_model, selected.llm_enabled)
    calls = []

    async def structured(name, instructions, content, output_type, *, settings):
        calls.append((settings.ai_provider, settings.ai_model, settings.llm_enabled))
        assert settings is not selected
        return JobExtraction(title="Reviewed generation", company="Acme"), 1, 2

    monkeypatch.setattr(extract, "run_structured", structured)

    def change_live_settings():
        # Mutate the cached instance too: a shallow shared configuration reference fails.
        selected.ai_provider = "anthropic"
        selected.anthropic_api_key = "offline-other-unused-key"
        selected.model = "unreviewed-model"
        selected.anthropic_model = "unreviewed-other-model"

    if action == "capture":
        original = services._load_page

        def loading(payload):
            change_live_settings()
            return original(payload)

        monkeypatch.setattr(services, "_load_page", loading)
        path = f"{API}/jobs"
        payload = body(ALIAS, TEXT + " Changed responsibilities.").model_dump()
    else:
        original = canonical_repo.reserve

        def reserving(*args, **kwargs):
            change_live_settings()
            return original(*args, **kwargs)

        monkeypatch.setattr(canonical_repo, "reserve", reserving)
        path = f"{API}/jobs/{saved.json()['id']}/reextract"
        payload = None
    headers = (
        {
            "X-Jobbr-AI-Provider": checked[0],
            "X-Jobbr-AI-Model": checked[1],
            "X-Jobbr-AI-Enabled": str(checked[2]).lower(),
        }
        if with_headers
        else {}
    )
    response = client.post(path, json=payload, headers=headers)
    assert response.status_code == (201 if action == "capture" else 200), response.text
    assert calls == [checked]
    assert response.json()["title"] == "Reviewed generation"
    if action == "reextract":
        detail = client.get(f"{API}/jobs/{saved.json()['id']}")
        assert detail.json()["extractions"][0]["model"] == checked[1]
