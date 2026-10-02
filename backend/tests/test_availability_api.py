"""Availability authorization, server identity and unchanged private history."""

from datetime import UTC, datetime

from sqlmodel import Session, select

from jobbr import canonical_repo, db, discovery, services
from jobbr.canonical import Identity
from jobbr.discovery import AvailabilityObservation
from jobbr.models import Job
from tests.conftest import API, reset_settings
from tests.test_extension_capture import capability  # noqa: F401 -- imported pytest fixture
from tests.test_postgres import (
    postgres,  # noqa: F401 -- capability requests dedicated database fixture
)

GH = Identity("greenhouse", "acme", "123")

BODY = {
    "url": "https://boards.greenhouse.io/acme/jobs/123?source=review",
    "text": "Platform Engineer at Acme. Build Python and SQL platforms with a team of engineers. "
    * 3,
}
HEADERS = {"X-Jobbr-Token": "offline-test-token"}


def protect(env):
    env.setenv("JOBBR_API_TOKEN", "offline-test-token")
    reset_settings()


def mock_observation(env, expected=GH):
    calls = []

    async def observe(identity):
        assert identity == expected
        calls.append(identity)
        return AvailabilityObservation(
            state="available" if identity else "unknown",
            reason="listed" if identity else "unsupported_identity",
            source_url="https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true"
            if identity
            else None,
            checked_at=datetime.now(UTC),
        )

    env.setattr(discovery, "observe_identity", observe)
    return calls


def test_unprotected_demo_cannot_dispatch(client, env):
    calls = mock_observation(env)
    assert client.post(API + "/jobs/1/availability").status_code == 403
    assert calls == []


def test_private_token_required_before_outbound_check(client, env):
    protect(env)
    env.setenv("JOBBR_PRIVATE_INSTANCE", "true")
    reset_settings()
    calls = mock_observation(env)
    assert client.post(API + "/jobs/1/availability").status_code == 401
    assert (
        client.post(API + "/jobs/1/availability", headers={"X-Jobbr-Token": "wrong"}).status_code
        == 401
    )
    assert client.post(API + "/jobs/1/availability", headers=HEADERS).status_code == 404
    assert calls == []


def test_check_preserves_job_application_and_events(client, env):
    protect(env)
    job = client.post(API + "/jobs", json=BODY, headers=HEADERS).json()
    assert (
        client.put(
            API + f"/jobs/{job['id']}/application",
            json={"stage": "applied", "notes": "Private follow-up"},
            headers=HEADERS,
        ).status_code
        == 200
    )
    before = client.get(API + f"/jobs/{job['id']}").json()
    calls = mock_observation(env)
    response = client.post(API + f"/jobs/{job['id']}/availability", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["state"] == "available"
    assert len(calls) == 1
    assert client.get(API + f"/jobs/{job['id']}").json() == before


def test_server_mapping_overrides_edited_url_and_releases_transaction(client, env):
    protect(env)
    job = client.post(API + "/jobs", json=BODY, headers=HEADERS).json()
    calls = mock_observation(env)
    with Session(db.get_engine()) as s:
        saved = s.get(Job, job["id"])
        assert saved is not None
        saved.url = "https://unrelated.example/posting"
        s.add(saved)
        s.commit()
        actual = discovery.observe_identity

        async def check_transaction(identity):
            assert not s.in_transaction()
            return await actual(identity)

        env.setattr(discovery, "observe_identity", check_transaction)
        import anyio  # noqa: PLC0415 -- isolated async service execution

        result = anyio.run(services.observe_job_availability, s, saved)
        assert result["state"] == "available"
        assert len(calls) == 1
        assert s.exec(select(Job)).one().url == "https://unrelated.example/posting"


def test_unsupported_saved_url_never_asserts_availability(client, env):
    protect(env)
    calls = mock_observation(env, None)
    body = {**BODY, "url": "https://example.com/role"}
    job = client.post(API + "/jobs", json=body, headers=HEADERS).json()
    response = client.post(API + f"/jobs/{job['id']}/availability", headers=HEADERS)
    assert response.json()["state"] == "unknown"
    assert calls == [None]


def test_multiple_server_identities_are_unknown(client, env):
    protect(env)
    job = client.post(API + "/jobs", json=BODY, headers=HEADERS).json()
    with Session(db.get_engine()) as s:
        canonical_repo.bind_identity(s, Identity("greenhouse", "other", "456"), job["id"])
        s.commit()
    calls = mock_observation(env, None)
    response = client.post(API + f"/jobs/{job['id']}/availability", headers=HEADERS)
    assert response.json()["reason"] == "unsupported_identity"
    assert calls == [None]


def test_owner_session_requires_csrf(capability, env):  # noqa: F811 -- imported pytest fixture
    client, _auth, _cookie, csrf_headers = capability
    calls = mock_observation(env)
    job = client.post(API + "/jobs", json=BODY, headers=csrf_headers).json()
    route = API + f"/jobs/{job['id']}/availability"
    assert client.post(route).status_code == 403
    assert (
        client.post(
            route,
            headers={
                "Origin": "https://wrong.example",
                "X-CSRF-Token": csrf_headers["X-CSRF-Token"],
            },
        ).status_code
        == 403
    )
    assert calls == []
    assert client.post(route, headers=csrf_headers).status_code == 200
    assert len(calls) == 1
