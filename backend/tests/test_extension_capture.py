"""Offline capability lifecycle and paid-call reservation proofs, with no provider requests."""

import base64
import hashlib
import json
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlmodel import Session, select

from jobbr import capture_repo, capture_services, config, db, extract, services
from jobbr.auth import ISSUER, SESSION_COOKIE
from jobbr.auth_store import SessionRecord
from jobbr.capture_models import CaptureGrant, CapturePairing, CaptureReceipt, CaptureThrottle
from jobbr.main import create_app
from jobbr.models import Job
from jobbr.schemas import JobExtraction
from tests.conftest import API
from tests.test_backup import backup, source_path
from tests.test_postgres import postgres  # noqa: F401 - dedicated database/schema safety fixture

EXTENSION_ID = "a" * 32
EXTENSION_ORIGIN = "chrome-extension://" + EXTENSION_ID
ORIGIN = "https://jobbr.test"
BODY = {"url": "https://jobs.example/one", "text": "Reviewed posting text"}


def proof():
    verifier = secrets.token_urlsafe(32)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    return verifier, challenge


@pytest.fixture(params=["sqlite", "postgres"])
def capability(env, request):
    if request.param == "postgres":
        request.getfixturevalue("postgres")
    env.setenv("JOBBR_OPENAI_AUTH_ENABLED", "1")
    env.setenv("JOBBR_OPENAI_CLIENT_ID", "oaiapp_offline")
    env.setenv("JOBBR_OPENAI_ALLOWED_SUBJECT", "owner")
    env.setenv("JOBBR_OPENAI_REDIRECT_URI", ORIGIN + "/jobbr/auth/openai/callback")
    env.setenv("JOBBR_OPENAI_TOKEN_AUTH_METHOD", "none")
    env.delenv("JOBBR_OPENAI_CLIENT_SECRET", raising=False)
    env.setenv("JOBBR_OPENAI_STORE_KEY", Fernet.generate_key().decode())
    env.setenv("JOBBR_EXTENSION_ALLOWED_IDS", EXTENSION_ID)
    config.get_settings.cache_clear()
    with TestClient(create_app(), base_url=ORIGIN) as client:
        auth = client.app.state.auth
        cookie = secrets.token_urlsafe(32)
        csrf = auth.store.csrf(cookie)
        auth.store.rotate_session(
            "",
            cookie,
            SessionRecord(
                ISSUER, "oaiapp_offline", "owner", "Owner", None, csrf, time.time() + 3600
            ),
            auth.scope,
        )
        client.cookies.set(SESSION_COOKIE, cookie, domain="jobbr.test", path="/")
        yield client, auth, cookie, {"Origin": ORIGIN, "X-CSRF-Token": csrf}


def approve(capability, challenge):
    client, _auth, _cookie, headers = capability
    settings = config.get_settings()
    response = client.post(
        API + "/extension/pairings",
        headers=headers,
        json={
            "extension_id": EXTENSION_ID,
            "challenge": challenge,
            "challenge_method": "S256",
            "ai_provider": settings.ai_provider,
            "ai_model": settings.ai_model,
            "llm_enabled": settings.llm_enabled,
        },
    )
    assert response.status_code == 200, response.text
    return response


def connect(capability):
    client = capability[0]
    verifier, challenge = proof()
    approve(capability, challenge)
    response = client.post(
        API + "/extension/exchange",
        headers={"Origin": EXTENSION_ORIGIN},
        json={"extension_id": EXTENSION_ID, "challenge": challenge, "verifier": verifier},
    )
    assert response.status_code == 200, response.text
    return response.json()


def capture_headers(grant, key=None):
    settings = config.get_settings()
    return {
        "Origin": EXTENSION_ORIGIN,
        "Authorization": "Bearer " + grant["access_token"],
        "X-Jobbr-Extension-ID": EXTENSION_ID,
        "Idempotency-Key": key or secrets.token_urlsafe(32),
        "X-Jobbr-AI-Provider": settings.ai_provider,
        "X-Jobbr-AI-Model": settings.ai_model,
        "X-Jobbr-AI-Enabled": str(settings.llm_enabled).lower(),
    }


@pytest.fixture
def ingestion(env):
    calls = []

    def ingest(session, body, *, settings):
        calls.append((body.model_dump(), settings))
        return Job(id=41, company_id=1, title="Private existing title", raw_text="Private text")

    env.setattr(services, "ingest", ingest)
    return calls


def test_private_bootstrap_never_writes_before_explicit_csrf_approval(capability):
    client, _auth, _cookie, headers = capability
    verifier, challenge = proof()
    detail = client.get(API + f"/extension/pairings/{EXTENSION_ID}/{challenge}")
    assert detail.status_code == 200
    assert detail.json()["expires_at"] is None
    assert detail.json()["status"] == "pending"
    assert detail.json()["destination"] == ORIGIN + "/jobbr"
    assert (
        detail.json()["comparison_code"]
        == hashlib.sha256((EXTENSION_ID + "\n" + challenge).encode()).hexdigest()[:8].upper()
    )
    with Session(db.get_engine()) as s:
        assert s.exec(select(CapturePairing)).all() == []
        assert s.get(CaptureThrottle, 1).count == 0
    body = {
        "extension_id": EXTENSION_ID,
        "challenge": challenge,
        "challenge_method": "S256",
        "ai_provider": "openai",
        "ai_model": config.get_settings().ai_model,
        "llm_enabled": False,
    }
    assert client.post(API + "/extension/pairings", json=body).status_code == 403
    assert (
        client.post(
            API + "/extension/pairings",
            json=body,
            headers={**headers, "Origin": "https://attacker.example"},
        ).status_code
        == 403
    )
    client.cookies.clear()
    assert client.post(API + "/extension/pairings", json=body, headers=headers).status_code == 401
    assert (
        client.post(
            API + "/extension/exchange",
            json={"extension_id": EXTENSION_ID, "challenge": challenge, "verifier": verifier},
            headers={"Origin": EXTENSION_ORIGIN},
        ).status_code
        == 404
    )
    with Session(db.get_engine()) as s:
        assert s.get(CaptureThrottle, 1).count == 0


def test_pkce_exchange_single_use_hash_only_and_origin_bound(capability):
    client, _auth, _cookie, _headers = capability
    verifier, challenge = proof()
    approve(capability, challenge)
    body = {"extension_id": EXTENSION_ID, "challenge": challenge, "verifier": verifier}
    assert client.post(API + "/extension/exchange", json=body).status_code == 403
    assert (
        client.post(
            API + "/extension/exchange", json=body, headers={"Origin": "https://attacker.example"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            API + "/extension/exchange",
            json={**body, "verifier": secrets.token_urlsafe(32)},
            headers={"Origin": EXTENSION_ORIGIN},
        ).status_code
        == 403
    )
    response = client.post(
        API + "/extension/exchange", json=body, headers={"Origin": EXTENSION_ORIGIN}
    )
    assert response.status_code == 200
    granted = response.json()
    assert set(granted) == {"access_token", "grant_id", "token_type", "scope", "expires_at"}
    assert granted["scope"] == "jobs:capture"
    assert (
        client.post(
            API + "/extension/exchange", json=body, headers={"Origin": EXTENSION_ORIGIN}
        ).status_code
        == 410
    )
    with Session(db.get_engine()) as s:
        metadata = json.dumps(
            [row.model_dump(mode="json") for row in s.exec(select(CaptureGrant)).all()]
        )
        assert granted["access_token"] not in metadata
        assert verifier not in metadata
        assert s.exec(select(CapturePairing)).one().consumed


def test_simultaneous_exchange_consumes_pairing_only_once(capability):
    client = capability[0]
    verifier, challenge = proof()
    approve(capability, challenge)
    body = {"extension_id": EXTENSION_ID, "challenge": challenge, "verifier": verifier}
    gate = Barrier(2)

    def attempt():
        gate.wait(timeout=5)
        return client.post(
            API + "/extension/exchange", json=body, headers={"Origin": EXTENSION_ORIGIN}
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(lambda _: attempt(), range(2)))
    assert sorted(outcomes) == [200, 410]
    with Session(db.get_engine()) as s:
        assert len(s.exec(select(CaptureGrant)).all()) == 1


def test_unknown_proofs_and_capabilities_do_not_acquire_mutation_lock(capability, env):
    client = capability[0]
    verifier, challenge = proof()
    approve(capability, challenge)

    def forbidden(*args, **kwargs):
        pytest.fail("Unauthenticated incorrect proof took the shared mutation lock")

    env.setattr(capture_repo, "lock", forbidden)
    body = {
        "extension_id": EXTENSION_ID,
        "challenge": challenge,
        "verifier": secrets.token_urlsafe(32),
    }
    assert (
        client.post(
            API + "/extension/exchange", json=body, headers={"Origin": EXTENSION_ORIGIN}
        ).status_code
        == 403
    )
    assert (
        client.post(
            API + "/extension/exchange",
            json={**body, "challenge": proof()[1], "verifier": verifier},
            headers={"Origin": EXTENSION_ORIGIN},
        ).status_code
        == 404
    )
    headers = capture_headers({"access_token": secrets.token_urlsafe(32)})
    assert client.post(API + "/extension/captures", json=BODY, headers=headers).status_code == 401
    assert client.post(API + "/extension/disconnect", headers=headers).status_code == 401


def test_simultaneous_last_capture_never_overspends_budget(capability, ingestion):
    client = capability[0]
    grant = connect(capability)
    with Session(db.get_engine()) as s:
        row = s.exec(select(CaptureGrant)).one()
        row.captures_remaining = 1
        s.add(row)
        s.commit()
    gate = Barrier(2)

    def attempt():
        gate.wait(timeout=5)
        return client.post(
            API + "/extension/captures", json=BODY, headers=capture_headers(grant)
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(lambda _: attempt(), range(2)))
    assert outcomes.count(200) == 1
    assert all(code in {200, 401, 409} for code in outcomes)
    assert len(ingestion) == 1
    with Session(db.get_engine()) as s:
        assert s.exec(select(CaptureGrant)).one().captures_remaining == 0


def test_capture_capability_is_not_website_access_and_receipt_is_minimal(capability, ingestion):
    client = capability[0]
    grant = connect(capability)
    client.cookies.clear()
    headers = capture_headers(grant)
    assert client.get(API + "/profile", headers=headers).status_code == 401
    assert client.post(API + "/jobs", headers=headers, json=BODY).status_code == 401
    assert client.get(API + "/extension/grants", headers=headers).status_code == 401
    captured = client.post(API + "/extension/captures", headers=headers, json=BODY)
    assert captured.status_code == 200, captured.text
    assert captured.json() == {"id": 41}
    assert captured.headers["access-control-allow-origin"] == EXTENSION_ORIGIN
    assert "access-control-allow-credentials" not in captured.headers
    assert len(ingestion) == 1
    duplicate = client.post(API + "/extension/captures", headers=headers, json=BODY)
    assert duplicate.json() == {"id": 41}
    assert len(ingestion) == 1
    assert (
        client.post(
            API + "/extension/captures", headers=headers, json={**BODY, "text": "Different posting"}
        ).status_code
        == 409
    )
    with Session(db.get_engine()) as s:
        row = s.exec(select(CaptureGrant)).one()
        assert row.captures_remaining == 4
        metadata = json.dumps(s.exec(select(CaptureReceipt)).one().model_dump())
        assert BODY["text"] not in metadata
        assert BODY["url"] not in metadata


def test_five_capture_limit_policy_pin_and_allowed_id_changes(capability, ingestion, env):
    client = capability[0]
    grant = connect(capability)
    headers = capture_headers(grant)
    assert (
        client.post(
            API + "/extension/captures",
            headers={**headers, "X-Jobbr-AI-Model": "stale-model"},
            json=BODY,
        ).status_code
        == 409
    )
    assert ingestion == []
    for _ in range(5):
        assert (
            client.post(
                API + "/extension/captures", headers=capture_headers(grant), json=BODY
            ).status_code
            == 200
        )
    assert (
        client.post(
            API + "/extension/captures", headers=capture_headers(grant), json=BODY
        ).status_code
        == 401
    )
    assert len(ingestion) == 5
    env.setenv("JOBBR_EXTENSION_ALLOWED_IDS", "")
    config.get_settings.cache_clear()
    assert client.post(API + "/extension/captures", headers=headers, json=BODY).status_code == 403


@pytest.mark.parametrize("reason", ["revoke", "logout", "scope", "expiry", "disconnect"])
def test_revoked_or_expired_session_scope_and_grant_reject_before_ingest(
    capability, ingestion, reason
):
    client, auth, cookie, owner_headers = capability
    grant = connect(capability)
    headers = capture_headers(grant)
    if reason == "revoke":
        assert (
            client.post(
                API + f"/extension/grants/{grant['grant_id']}/revoke", headers=owner_headers
            ).status_code
            == 204
        )
    elif reason == "logout":
        auth.store.revoke_session(cookie, auth.scope)
    elif reason == "scope":
        auth.scope = "different-config-generation"
    elif reason == "disconnect":
        assert client.post(API + "/extension/disconnect", headers=headers).status_code == 204
    else:
        with Session(db.get_engine()) as s:
            row = s.exec(select(CaptureGrant)).one()
            row.expires_at = time.time() - 1
            s.add(row)
            s.commit()
    assert client.post(API + "/extension/captures", headers=headers, json=BODY).status_code == 401
    assert ingestion == []


def test_failed_capture_is_not_retried_and_budget_is_consumed(capability, env):
    client = capability[0]
    grant = connect(capability)
    headers = capture_headers(grant)
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        raise services.UserError("Paste readable posting text.")

    env.setattr(services, "ingest", fail)
    assert client.post(API + "/extension/captures", headers=headers, json=BODY).status_code == 422
    assert client.post(API + "/extension/captures", headers=headers, json=BODY).status_code == 409
    assert calls == [1]
    with Session(db.get_engine()) as s:
        assert s.exec(select(CaptureGrant)).one().busy is False
        assert s.exec(select(CaptureGrant)).one().captures_remaining == 4
        assert s.exec(select(CaptureReceipt)).one().status == "failed"


def test_one_concurrent_capture_and_logout_does_not_abort_reserved_work(capability, env):
    client, auth, cookie, _owner_headers = capability
    grant = connect(capability)
    headers = capture_headers(grant)
    entered, release = Event(), Event()
    calls = []

    def blocked(s, body, *, settings):
        calls.append(1)
        entered.set()
        assert release.wait(timeout=5)
        return Job(id=52, company_id=1, title="Fixture")

    env.setattr(services, "ingest", blocked)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.post, API + "/extension/captures", headers=headers, json=BODY)
        assert entered.wait(timeout=5)
        try:
            assert (
                client.post(API + "/extension/captures", headers=headers, json=BODY).status_code
                == 409
            )
            assert (
                client.post(
                    API + "/extension/captures", headers=capture_headers(grant), json=BODY
                ).status_code
                == 409
            )
            auth.store.revoke_session(cookie, auth.scope)
        finally:
            release.set()
        assert pending.result(timeout=5).json() == {"id": 52}
    assert calls == [1]
    assert client.post(API + "/extension/captures", headers=headers, json=BODY).status_code == 401


def test_selected_settings_snapshot_reaches_actual_provider_dispatch(capability, env):
    client = capability[0]
    env.setenv("JOBBR_OPENAI_API_KEY", "offline-key")
    config.get_settings.cache_clear()
    grant = connect(capability)
    settings = config.get_settings().model_copy(deep=True)
    calls = []

    async def structured(name, instructions, content, output_type, *, settings):
        calls.append(settings.ai_provider)
        return JobExtraction(company="Fixture", title="Engineer"), 1, 2

    env.setattr(extract, "run_structured", structured)
    original = services.ingest

    def change_cache(s, body, *, settings):
        env.setenv("JOBBR_AI_PROVIDER", "anthropic")
        env.setenv("JOBBR_ANTHROPIC_API_KEY", "offline-other-key")
        config.get_settings.cache_clear()
        return original(s, body, settings=settings)

    env.setattr(services, "ingest", change_cache)
    headers = capture_headers(grant)
    response = client.post(API + "/extension/captures", headers=headers, json=BODY)
    assert response.status_code == 200, response.text
    assert calls == ["openai"]
    assert settings.ai_provider == "openai"


def test_cors_is_scoped_to_allowlisted_extension_protocol(capability):
    client = capability[0]
    assert (
        client.options(
            API + "/extension/captures", headers={"Origin": EXTENSION_ORIGIN}
        ).status_code
        == 204
    )
    assert (
        client.options(API + "/extension/grants", headers={"Origin": EXTENSION_ORIGIN}).status_code
        == 403
    )
    assert (
        client.options(
            API + "/extension/captures", headers={"Origin": "chrome-extension://" + "b" * 32}
        ).status_code
        == 403
    )
    response = client.post(
        API + "/extension/exchange", headers={"Origin": EXTENSION_ORIGIN}, json={}
    )
    assert response.status_code == 422
    assert response.headers["access-control-allow-origin"] == EXTENSION_ORIGIN
    assert (
        "access-control-allow-origin"
        not in client.get(API + "/profile", headers={"Origin": EXTENSION_ORIGIN}).headers
    )


def test_approval_and_pair_retention_are_owner_bounded(capability, env):
    client = capability[0]
    env.setattr(capture_services, "PAIRINGS_PER_MINUTE", 1)
    _verifier, challenge = proof()
    approve(capability, challenge)
    _verifier, second = proof()
    settings = config.get_settings()
    response = client.post(
        API + "/extension/pairings",
        headers=capability[3],
        json={
            "extension_id": EXTENSION_ID,
            "challenge": second,
            "challenge_method": "S256",
            "ai_provider": settings.ai_provider,
            "ai_model": settings.ai_model,
            "llm_enabled": settings.llm_enabled,
        },
    )
    assert response.status_code == 429
    with Session(db.get_engine()) as s:
        assert len(s.exec(select(CapturePairing)).all()) == 1


def test_purge_preserves_bounded_busy_completion_metadata(capability):
    connect(capability)
    now = time.time()
    with Session(db.get_engine()) as s:
        row = s.exec(select(CaptureGrant)).one()
        row.busy = True
        row.expires_at = now - 1
        s.add(row)
        s.add(
            CaptureReceipt(
                token_digest=row.token_digest, request_digest="fixture", input_digest="fixture"
            )
        )
        s.commit()
        capture_repo.lock(s)
        capture_repo.purge(s, now)
        s.commit()
        assert len(s.exec(select(CaptureReceipt)).all()) == 1
        capture_repo.lock(s)
        capture_repo.purge(s, now + 601)
        s.commit()
        assert s.exec(select(CaptureGrant)).all() == []
        assert s.exec(select(CaptureReceipt)).all() == []


def test_backup_rejects_missing_extension_initialization_guard(capability):
    if db.get_engine().dialect.name != "sqlite":
        pytest.skip("SQLite archive validation is tested only against an isolated SQLite fixture")
    backup.verify(source_path())
    with Session(db.get_engine()) as s:
        s.execute(delete(CaptureThrottle))
        s.commit()
    with pytest.raises(backup.BackupError, match="Extension initialization guard"):
        backup.verify(source_path())
