"""Provider-isolated OIDC verification and first-party cookie security tests."""

import base64
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, insert, select, update

from jobbr.auth import (
    DISCOVERY,
    ISSUER,
    SESSION_COOKIE,
    TRANSACTION_COOKIE,
    AuthService,
    AuthSettings,
    build_auth_router,
    require_csrf,
    require_session,
)
from jobbr.auth_store import GUARDS, SESSIONS, TRANSACTIONS, DatabaseAuthStore
from jobbr.main import create_app

BASE = "/jobbr"
ORIGIN = "https://jobbr.example"
CALLBACK = ORIGIN + BASE + "/auth/openai/callback"


@pytest.fixture
def provider(tmp_path):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    public.update({"kid": "test-key", "alg": "RS256", "use": "sig"})
    engine = create_engine(
        f"sqlite:///{tmp_path}/auth.db", connect_args={"check_same_thread": False}
    )
    for table in (TRANSACTIONS, SESSIONS, GUARDS):
        table.create(engine)
    with engine.begin() as connection:
        connection.execute(insert(GUARDS).values(id=1))
    state = {
        "_engine": engine,
        "_key": Fernet.generate_key().decode(),
        "claims": {},
        "nonce": "",
        "calls": [],
        "token_body": {},
        "token_headers": {},
    }

    def handle(request):
        state["calls"].append(str(request.url))
        if str(request.url) == DISCOVERY:
            return httpx.Response(
                200,
                json={
                    "issuer": ISSUER,
                    "authorization_endpoint": ISSUER + "/authorize",
                    "token_endpoint": ISSUER + "/token",
                    "jwks_uri": ISSUER + "/keys",
                    "token_endpoint_auth_methods_supported": ["none", "client_secret_basic"],
                    "id_token_signing_alg_values_supported": ["RS256"],
                },
            )
        if request.url.path == "/keys":
            return httpx.Response(200, json={"keys": state.get("keys", [public])})
        if request.url.path == "/token":
            state["token_body"] = parse_qs(request.content.decode())
            state["token_headers"] = dict(request.headers)
            claims = {
                "iss": ISSUER,
                "aud": "oaiapp_test",
                "sub": "owner",
                "iat": int(time.time()),
                "exp": int(time.time()) + 300,
                "nonce": state["nonce"],
                "name": "Owner",
            }
            claims.update(state["claims"])
            signing_key = state.get("signing_key", private)
            token = jwt.encode(
                claims,
                signing_key,
                algorithm="RS256",
                headers=state.get("headers", {"kid": "test-key"}),
            )
            return httpx.Response(200, json={"id_token": token})
        raise AssertionError(f"Unexpected provider URL {request.url}")

    return state, httpx.MockTransport(handle)


def make_client(provider, **overrides):
    values = {
        "auth_enabled": True,
        "client_id": "oaiapp_test",
        "allowed_subject": "owner",
        "redirect_uri": CALLBACK,
        "store_key": provider[0]["_key"],
    }
    values.update(overrides)
    service = AuthService(
        AuthSettings(_env_file=None, **values),
        BASE,
        transport=provider[1],
        engine=provider[0]["_engine"],
    )
    app = FastAPI()
    app.state.auth = service
    app.include_router(build_auth_router(service), prefix=BASE)

    @app.get(BASE + "/private")
    def private(request: Request):
        return require_session(request).user()

    @app.post(BASE + "/private")
    def write(request: Request):
        require_csrf(request)
        return {"ok": True}

    return TestClient(app, base_url=ORIGIN, follow_redirects=False), service


def active_count(service, table):
    if service.store is None:
        return 0
    assert isinstance(service.store, DatabaseAuthStore)
    with service.store.engine.connect() as connection:
        return connection.scalar(
            select(func.count()).select_from(table).where(table.c.expires_at > time.time())
        )


def start(client, provider):
    response = client.get(BASE + "/auth/openai")
    assert response.status_code == 302
    params = parse_qs(urlsplit(response.headers["location"]).query)
    provider[0]["nonce"] = params["nonce"][0]
    return params, response


def finish(client, params):
    return client.get(
        BASE + "/auth/openai/callback",
        params={"state": params["state"][0], "code": "one-time-code"},
    )


def test_pkce_session_csrf_and_logout(provider):
    client, service = make_client(provider)
    assert client.get(BASE + "/private").status_code == 401
    params, response = start(client, provider)
    cookie = response.headers["set-cookie"]
    assert "Secure" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "code_verifier" not in params
    assert params["scope"] == ["openid profile email"]
    with provider[0]["_engine"].connect() as connection:
        payload = connection.scalar(select(TRANSACTIONS.c.encrypted_payload))
    tx = SimpleNamespace(
        **json.loads(Fernet(provider[0]["_key"].encode()).decrypt(payload.encode()))
    )
    expected = base64.urlsafe_b64encode(hashlib.sha256(tx.verifier.encode()).digest()).rstrip(b"=")
    assert params["code_challenge"] == [expected.decode()]
    response = finish(client, params)
    assert response.status_code == 303
    assert TRANSACTION_COOKIE not in client.cookies
    assert SESSION_COOKIE in client.cookies
    assert active_count(service, TRANSACTIONS) == 0
    assert provider[0]["token_body"]["code_verifier"] == [tx.verifier]
    assert provider[0]["token_body"]["redirect_uri"] == [CALLBACK]
    assert "authorization" not in provider[0]["token_headers"]
    status = client.get(BASE + "/api/auth/session").json()
    assert status["authenticated"]
    assert status["user"]["subject"] == "owner"
    assert "id_token" not in json.dumps(status)
    assert client.get(BASE + "/private").status_code == 200
    assert client.post(BASE + "/private").status_code == 403
    assert client.post(BASE + "/api/auth/logout").status_code == 403
    headers = {"Origin": ORIGIN, "X-CSRF-Token": status["csrf_token"]}
    assert (
        client.post(
            BASE + "/private", headers={**headers, "Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert client.post(BASE + "/private", headers=headers).status_code == 200
    assert client.post(BASE + "/api/auth/logout", headers=headers).status_code == 204
    assert active_count(service, SESSIONS) == 0
    assert SESSION_COOKIE not in client.cookies
    assert client.get(BASE + "/private").status_code == 401
    assert finish(client, params).status_code == 400


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "https://evil.example"},
        {"aud": "another-client"},
        {"nonce": "wrong"},
        {"exp": 1},
        {"iat": int(time.time()) + 3600},
        {"sub": "another-owner"},
        {"sub": ""},
        {"aud": ["oaiapp_test", "other"]},
        {"azp": "other"},
    ],
)
def test_invalid_identity_rejected(provider, claims):
    client, service = make_client(provider)
    params, _ = start(client, provider)
    provider[0]["claims"] = claims
    assert finish(client, params).status_code == 400
    assert active_count(service, SESSIONS) == 0
    assert TRANSACTION_COOKIE not in client.cookies
    assert active_count(service, TRANSACTIONS) == 0


def test_invalid_signature_rejected(provider):
    client, service = make_client(provider)
    params, _ = start(client, provider)
    provider[0]["signing_key"] = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert finish(client, params).status_code == 400
    assert active_count(service, SESSIONS) == 0


@pytest.mark.parametrize("kind", ["missing", "mismatch", "expired", "provider_error", "duplicate"])
def test_transaction_failures_do_not_redeem_codes(provider, kind):
    client, _service = make_client(provider)
    params, _ = start(client, provider)
    query = {"state": params["state"][0], "code": "code"}
    if kind == "missing":
        client.cookies.clear()
    elif kind == "mismatch":
        query["state"] = "bad"
    elif kind == "expired":
        with provider[0]["_engine"].begin() as connection:
            connection.execute(update(TRANSACTIONS).values(expires_at=0))
    elif kind == "provider_error":
        query["error"] = "access_denied"
    elif kind == "duplicate":
        query["state"] = [params["state"][0], params["state"][0]]
    assert client.get(BASE + "/auth/openai/callback", params=query).status_code == 400
    assert not any(url.endswith("/token") for url in provider[0]["calls"])
    assert TRANSACTION_COOKIE not in client.cookies


@pytest.mark.parametrize(
    "settings",
    [
        {"auth_enabled": False},
        {"client_id": ""},
        {"allowed_subject": ""},
        {"redirect_uri": "http://jobbr.example/jobbr/auth/openai/callback"},
        {"redirect_uri": ORIGIN + "/wrong"},
        {"token_auth_method": "client_secret_basic"},
        {"client_secret": "not-valid-for-public-client"},
        {"client_id": "dynamic_agent_client"},
        {"store_key": ""},
        {"store_key": "invalid"},
    ],
)
def test_incomplete_configuration_fails_closed(provider, settings):
    client, service = make_client(provider, **settings)
    status = client.get(BASE + "/api/auth/session").json()
    assert not status["ready"]
    assert not status["authenticated"]
    assert status["reason"]
    assert client.get(BASE + "/auth/openai").status_code == 503
    assert client.get(BASE + "/private").status_code == 503
    assert active_count(service, SESSIONS) == 0
    assert not provider[0]["calls"]


def test_confidential_client_basic_secret_only(provider):
    client, _ = make_client(
        provider, token_auth_method="client_secret_basic", client_secret="a:b c"
    )
    params, _ = start(client, provider)
    assert finish(client, params).status_code == 303
    assert (
        provider[0]["token_headers"]["authorization"]
        == "Basic " + base64.b64encode(b"oaiapp_test:a%3Ab+c").decode()
    )
    assert "client_secret" not in provider[0]["token_body"]


def test_session_expiration(provider):

    client, service = make_client(provider)
    params, _ = start(client, provider)
    assert finish(client, params).status_code == 303
    with provider[0]["_engine"].begin() as connection:
        connection.execute(update(SESSIONS).values(expires_at=0))
    assert client.get(BASE + "/private").status_code == 401
    assert active_count(service, SESSIONS) == 0


def test_discovery_untrusted_endpoint_is_not_contacted(provider):
    def handle(request):
        assert str(request.url) == DISCOVERY
        return httpx.Response(
            200,
            json={
                "issuer": ISSUER,
                "authorization_endpoint": "https://evil.example/authorize",
                "token_endpoint": ISSUER + "/token",
                "jwks_uri": ISSUER + "/keys",
            },
        )

    client, _ = make_client((provider[0], httpx.MockTransport(handle)))
    assert client.get(BASE + "/auth/openai").status_code == 503


def test_non_ascii_state_rejected_without_server_error(provider):
    client, _ = make_client(provider)
    start(client, provider)
    assert (
        client.get(BASE + "/auth/openai/callback", params={"state": "é", "code": "x"}).status_code
        == 400
    )


@pytest.mark.parametrize("kind", ["timeout", "oversized", "invalid_json", "bad_issuer", "redirect"])
def test_provider_failures_are_bounded_and_fail_closed(provider, kind):
    def handle(request):
        if kind == "timeout":
            raise httpx.ReadTimeout("mock timeout", request=request)
        if kind == "oversized":
            return httpx.Response(200, content=b"x" * 131073)
        if kind == "invalid_json":
            return httpx.Response(200, content=b"not json")
        if kind == "redirect":
            return httpx.Response(302, headers={"Location": "https://evil.example"})
        return httpx.Response(200, json={"issuer": "https://evil.example"})

    client, service = make_client((provider[0], httpx.MockTransport(handle)))
    assert client.get(BASE + "/auth/openai").status_code == 503
    assert active_count(service, TRANSACTIONS) == 0


@pytest.mark.parametrize("headers", [{"kid": "unknown"}, {"kid": "test-key", "crit": ["unknown"]}])
def test_unknown_key_and_critical_headers_rejected(provider, headers):
    client, service = make_client(provider)
    params, _ = start(client, provider)
    provider[0]["headers"] = headers
    assert finish(client, params).status_code == 400
    assert active_count(service, SESSIONS) == 0


def test_jwks_refresh_accepts_rotated_signing_key(provider):
    client, service = make_client(provider)
    params, _ = start(client, provider)
    assert finish(client, params).status_code == 303
    rotated = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(rotated.public_key()))
    public.update({"kid": "rotated-key", "alg": "RS256", "use": "sig"})
    provider[0]["keys"] = [public]
    provider[0]["signing_key"] = rotated
    provider[0]["headers"] = {"kid": "rotated-key"}
    service._keys_last_fetch -= 6
    params, _ = start(client, provider)
    assert finish(client, params).status_code == 303
    assert len([url for url in provider[0]["calls"] if url.endswith("/keys")]) == 2
    assert active_count(service, SESSIONS) == 1


def test_login_can_finish_on_another_instance_and_logout_is_shared(provider):
    first, _first_service = make_client(provider)
    second, _second_service = make_client(provider)
    params, _response = start(first, provider)
    second.cookies.update(first.cookies)
    assert finish(second, params).status_code == 303
    first.cookies.update(second.cookies)
    status = first.get(BASE + "/api/auth/session").json()
    assert status["authenticated"]
    other_status = second.get(BASE + "/api/auth/session").json()
    assert status["csrf_token"] == other_status["csrf_token"]
    assert (
        second.post(
            BASE + "/api/auth/logout",
            headers={"Origin": ORIGIN, "X-CSRF-Token": status["csrf_token"]},
        ).status_code
        == 204
    )
    assert first.get(BASE + "/private").status_code == 401


def test_concurrent_callbacks_redeem_provider_code_only_once(provider):
    first, _first_service = make_client(provider)
    second, _second_service = make_client(provider)
    params, _response = start(first, provider)
    second.cookies.update(first.cookies)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [pool.submit(finish, client, params) for client in (first, second)]
        statuses = sorted(future.result(timeout=10).status_code for future in pending)
    assert statuses == [303, 400]
    assert len([url for url in provider[0]["calls"] if url.endswith("/token")]) == 1


@pytest.mark.parametrize("mode", ["missing_key", "missing_tables", "configured"])
def test_application_health_reports_persistent_auth_readiness(provider, env, tmp_path, mode):
    env.setenv("JOBBR_OPENAI_AUTH_ENABLED", "true")
    env.setenv("JOBBR_OPENAI_CLIENT_ID", "oaiapp_test")
    env.setenv("JOBBR_OPENAI_ALLOWED_SUBJECT", "owner")
    env.setenv("JOBBR_OPENAI_REDIRECT_URI", CALLBACK)
    env.setenv("JOBBR_OPENAI_TOKEN_AUTH_METHOD", "none")
    env.delenv("JOBBR_OPENAI_CLIENT_SECRET", raising=False)
    if mode == "missing_key":
        env.delenv("JOBBR_OPENAI_STORE_KEY", raising=False)
    else:
        env.setenv("JOBBR_OPENAI_STORE_KEY", provider[0]["_key"])
    engine = provider[0]["_engine"]
    if mode == "missing_tables":
        engine = create_engine(
            f"sqlite:///{tmp_path}/unmigrated.db", connect_args={"check_same_thread": False}
        )
    env.setattr("jobbr.main.get_engine", lambda: engine)
    # Deliberately avoid lifespan/migration: readiness itself must detect absent tables.
    client = TestClient(create_app(), base_url=ORIGIN, follow_redirects=False)
    health = client.get("/healthz")
    status = client.get(BASE + "/api/auth/session").json()
    assert health.status_code == (200 if mode == "configured" else 503)
    assert status["ready"] is (mode == "configured")
    assert not status["authenticated"]
    assert not provider[0]["calls"]
    if mode != "configured":
        assert client.get(BASE + "/auth/openai").status_code == 503
        assert client.get(BASE + "/api/profile").status_code == 503
    client.close()


def test_non_ascii_csrf_header_is_rejected(provider):
    client, _service = make_client(provider)
    params, _response = start(client, provider)
    assert finish(client, params).status_code == 303
    # ASGI header values are latin-1 bytes; no Unicode timing-compare TypeError may escape.
    assert (
        client.post(
            BASE + "/private", headers={"Origin": ORIGIN, "X-CSRF-Token": b"\xe9"}
        ).status_code
        == 403
    )
