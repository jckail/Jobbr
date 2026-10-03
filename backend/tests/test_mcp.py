"""Actual MCP HTTP messages with ephemeral signed tokens and synthetic DB/provider data."""

import asyncio
import json
import time
from collections.abc import Iterator
from datetime import datetime, timedelta

import httpx
import httpx2
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, select

from jobbr import db
from jobbr.mcp_auth import READ_SCOPE, SHORTLIST_SCOPE, WRITE_SCOPE, JWTVerifier, MCPSettings
from jobbr.mcp_server import build_app, create_app
from jobbr.models import (
    Application,
    Company,
    Extraction,
    ExtractMethod,
    Job,
    Profile,
    Stage,
    utcnow,
)
from jobbr.proxy_import import import_leads
from tests.test_postgres import postgres  # noqa: F401 - shared isolated PostgreSQL fixture

RESOURCE = "https://jobbr.test/jobbr/mcp"
ISSUER = "https://issuer.test"
CLIENT = "synthetic-mcp-client"
OWNER = "synthetic-owner"
PATH = "/jobbr/mcp"
HEADERS = {"Accept": "application/json, text/event-stream"}


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def settings() -> MCPSettings:
    return MCPSettings(
        _env_file=None,
        resource_url=RESOURCE,
        issuer=ISSUER,
        jwks_url=ISSUER + "/keys",
        client_id=CLIENT,
        owner_subject=OWNER,
        enable_shortlist_write=True,
    )


@pytest.fixture
def sign(signing_key):
    def token(*, headers=None, drop=(), **claims):
        now = int(time.time())
        payload = {
            "iss": ISSUER,
            "aud": RESOURCE,
            "sub": OWNER,
            "client_id": CLIENT,
            "scope": " ".join([READ_SCOPE, SHORTLIST_SCOPE, WRITE_SCOPE]),
            "iat": now,
            "exp": now + 600,
            **claims,
        }
        for claim in drop:
            payload.pop(claim)
        return jwt.encode(
            payload,
            signing_key,
            algorithm="RS256",
            headers=headers or {"kid": "test", "typ": "at+jwt"},
        )

    return token


@pytest.fixture
def verifier(settings, signing_key) -> JWTVerifier:
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(signing_key.public_key()))
    jwk.update({"kid": "test", "alg": "RS256", "use": "sig"})

    def provider(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == ISSUER + "/keys"
        assert "authorization" not in request.headers  # no downstream credential passthrough
        return httpx.Response(200, json={"keys": [jwk]})

    return JWTVerifier(settings, httpx.MockTransport(provider))


def seed_catalog() -> None:
    with Session(db.get_engine()) as session:
        company = Company(name="Synthetic Systems", domain="synthetic.example")
        session.add(company)
        session.flush()
        job = Job(
            company_id=company.id,
            title="Data Platform Engineer",
            department="Agent Infrastructure",
            skills=["Python", "SQL"],
            summary="Build synthetic pipelines.",
            url="https://synthetic.example/roles/1",
            posted_at=datetime(2026, 9, 1),
            first_seen_at=datetime(2026, 9, 10),
            last_seen_at=utcnow() - timedelta(days=10),
            raw_text="PRIVATE RAW POSTING MARKER",
        )
        session.add(job)
        session.flush()
        session.add(Application(job_id=job.id, stage=Stage.saved, notes="Shortlist note"))
        session.add(Extraction(job_id=job.id, url=job.url, method=ExtractMethod.jsonld, ok=True))
        session.add(
            Extraction(
                job_id=job.id,
                method=ExtractMethod.heuristic,
                ok=False,
                error="PRIVATE PROVIDER ERROR MARKER",
                created_at=utcnow() + timedelta(seconds=1),
            )
        )
        session.add(Profile(resume_text="PRIVATE RESUME MARKER"))
        session.add(Job(company_id=company.id, title="Another synthetic role"))
        session.commit()


@pytest.fixture
def client(env, settings, verifier) -> Iterator[TestClient]:
    db.init_db()
    seed_catalog()
    with TestClient(
        build_app(settings, db.get_engine(), verifier), base_url="https://jobbr.test"
    ) as c:
        yield c


def rpc(client, token, method="tools/list", params=None, **headers):
    return client.post(
        PATH,
        headers={**HEADERS, "Authorization": "Bearer " + token, **headers},
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
    )


def call(client, token, tool, **arguments):
    response = rpc(client, token, "tools/call", {"name": tool, "arguments": arguments})
    assert response.status_code == 200
    return response.json()["result"]


def test_initialize_discovery_and_tools(client, sign):
    response = rpc(
        client,
        sign(),
        "initialize",
        {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "synthetic-test", "version": "1"},
        },
    )
    assert response.status_code == 200
    assert "mcp-session-id" not in response.headers  # no server session shared between users
    metadata = client.get("/.well-known/oauth-protected-resource/jobbr/mcp").json()
    assert metadata["resource"] == RESOURCE
    assert metadata["authorization_servers"] == [ISSUER]
    assert metadata["scopes_supported"] == [READ_SCOPE]
    tools = rpc(client, sign()).json()["result"]["tools"]
    assert len(tools) == 6
    for tool in tools:
        is_write = tool["name"] == "update_shortlist_notes"
        assert tool["annotations"]["readOnlyHint"] is not is_write
        assert tool["annotations"]["destructiveHint"] is is_write
        assert tool["_meta"]["securitySchemes"][0]["type"] == "oauth2"
        assert "owner_subject" not in tool["inputSchema"]["properties"]


def test_imported_review_summary_requires_shortlist_scope_including_legacy_rows(client, sign):
    private_review = "PRIVATE RECRUITER REVIEW SUMMARY"
    with Session(db.get_engine()) as session:
        import_leads(
            session,
            [{"id": "sig_scope_test", "summary": private_review, "role_title": "Imported lead"}],
            apply=True,
        )
        job = session.exec(select(Job).where(Job.title == "Imported lead")).one()
        role_id = job.id
        assert job.summary is None
        # Reproduce the old importer so the guard also protects existing databases.
        job.summary = private_review
        session.add(job)
        session.commit()

    role = call(client, sign(scope=READ_SCOPE), "get_role", role_id=role_id)
    assert not role.get("isError")
    assert private_review not in json.dumps(role)
    denied = call(client, sign(scope=READ_SCOPE), "list_shortlist")
    assert denied["isError"]
    assert private_review not in json.dumps(denied)
    shortlist = call(client, sign(scope=f"{READ_SCOPE} {SHORTLIST_SCOPE}"), "list_shortlist")
    assert private_review in json.dumps(shortlist)


@pytest.mark.parametrize("method", ["get", "post", "delete"])
def test_unauthorized_requests_include_discovery(client, method):
    response = getattr(client, method)(PATH, headers=HEADERS)
    assert response.status_code == 401
    assert (
        'resource_metadata="https://jobbr.test/.well-known/oauth-protected-resource/jobbr/mcp"'
        in response.headers["www-authenticate"]
    )
    assert f'scope="{READ_SCOPE}"' in response.headers["www-authenticate"]


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "https://wrong.test"},
        {"aud": "https://downstream.test"},
        {"aud": [RESOURCE, "https://downstream.test"]},
        {"sub": "another-user"},
        {"client_id": "another-client"},
        {"scope": [READ_SCOPE]},
        {"exp": 1},
        {"iat": 1},
        {"nbf": 9_999_999_999},
        {"gty": "client-credentials"},
        {"sub": ""},
        {"exp": "9999999999"},
    ],
)
def test_rejects_invalid_claims_before_tools(client, sign, claims):
    assert rpc(client, sign(**claims)).status_code == 401


@pytest.mark.parametrize("missing", ["iss", "aud", "exp", "iat", "sub", "client_id", "scope"])
def test_required_claims(client, sign, missing):
    assert rpc(client, sign(drop=[missing])).status_code == 401


def test_arbitrary_unsigned_wrong_signature_and_identity_tokens(client, sign):
    real = sign()
    head, body, _signature = real.split(".")
    values = [
        "arbitrary",
        f"{head}.{body}.AAAA",
        "x" * 20_000,
        sign(headers={"kid": "test", "typ": "JWT"}),
        sign(headers={"kid": "unknown", "typ": "at+jwt"}),
        jwt.encode({"sub": OWNER, "aud": RESOURCE}, key="", algorithm="none"),
    ]
    for token in values:
        assert rpc(client, token).status_code == 401


def test_scope_http_and_per_tool_challenges(client, sign):
    response = rpc(client, sign(scope=READ_SCOPE + "-similar"))
    assert response.status_code == 403
    assert "insufficient_scope" in response.headers["www-authenticate"]
    for tool, arguments, scope in [
        ("list_shortlist", {}, SHORTLIST_SCOPE),
        ("update_shortlist_notes", {"role_id": 1, "notes": "forbidden"}, WRITE_SCOPE),
    ]:
        result = call(client, sign(scope=READ_SCOPE), tool, **arguments)
        assert result["isError"]
        assert scope in result["_meta"]["mcp/www_authenticate"][0]
    with Session(db.get_engine()) as session:
        assert session.exec(select(Application)).one().notes == "Shortlist note"


def test_search_provenance_dates_and_refresh(client, sign):
    token = sign(scope=READ_SCOPE)
    page = call(client, token, "search_roles", query="python", limit=1)["structuredContent"]
    assert page["items"][0]["team"] == "Agent Infrastructure"
    assert page["items"][0]["posted_at"] != page["items"][0]["first_seen_at"]
    detail = call(client, token, "get_role", role_id=1)["structuredContent"]
    assert detail["freshness"]["latest_extraction_status"] == "failed"
    assert detail["freshness"]["stale"]
    assert detail["freshness"]["live_posting_verified"] is False
    assert detail["provenance"][1]["method"] == "jsonld"
    assert "PRIVATE" not in json.dumps(detail)
    unknown = call(client, token, "get_role", role_id=2)["structuredContent"]
    assert unknown["posted_at"] is None
    assert unknown["freshness"]["latest_extraction_status"] == "unknown"
    companies = call(client, token, "search_companies", query="Synthetic")["structuredContent"]
    assert companies["items"][0]["name"] == "Synthetic Systems"
    assert call(client, token, "get_refresh_status", role_id=1)["structuredContent"]["stale"]
    assert call(client, token, "get_role", role_id=999)["isError"]


def test_source_url_omits_userinfo_even_with_empty_username(client, sign):
    with Session(db.get_engine()) as session:
        job = session.get(Job, 1)
        job.url = "https://:synthetic-value@synthetic.example/roles/1"
        session.add(job)
        session.commit()
    result = call(client, sign(), "get_role", role_id=1)
    assert result["structuredContent"]["source_url"] is None
    assert "synthetic-value" not in json.dumps(result)


def test_bounds_pagination_and_literal_search(client, sign):
    token = sign()
    page = call(client, token, "search_roles", limit=1)["structuredContent"]
    assert page["next_after_id"] == 1
    next_page = call(client, token, "search_roles", after_id=1)["structuredContent"]
    assert next_page["items"][0]["id"] == 2
    assert next_page["next_after_id"] is None
    assert call(client, token, "search_roles", query="%")["structuredContent"]["items"] == []
    for arguments in [{"limit": 1000}, {"limit": 0}, {"query": "a" * 201}, {"after_id": -1}]:
        assert call(client, token, "search_roles", **arguments)["isError"]


def test_other_user_cannot_reuse_object_ids_or_session_headers(client, sign):
    assert not call(client, sign(), "get_role", role_id=1)["isError"]
    for tool, arguments in [
        ("search_companies", {}),
        ("search_roles", {}),
        ("get_role", {"role_id": 1}),
        ("list_shortlist", {}),
        ("update_shortlist_notes", {"role_id": 1, "notes": "intruder"}),
    ]:
        response = rpc(
            client,
            sign(sub="another-user"),
            "tools/call",
            {"name": tool, "arguments": arguments},
            **{"Mcp-Session-Id": "copied-id"},
        )
        assert response.status_code == 401
    assert "PRIVATE" not in rpc(client, sign(sub="another-user")).text


def test_shortlist_write_is_scoped_bounded_and_does_not_change_stage(client, sign):
    result = call(client, sign(), "update_shortlist_notes", role_id=1, notes="Review skills")
    assert result["structuredContent"]["notes"] == "Review skills"
    assert (
        call(client, sign(), "list_shortlist")["structuredContent"]["items"][0]["shortlist"][
            "notes"
        ]
        == "Review skills"
    )
    with Session(db.get_engine()) as session:
        application = session.exec(select(Application)).one()
        assert application.stage == Stage.saved
        application.stage = Stage.applied
        session.add(application)
        session.commit()
    assert call(client, sign(), "update_shortlist_notes", role_id=1, notes="do not reset")[
        "isError"
    ]
    assert call(client, sign(), "update_shortlist_notes", role_id=2, notes="no new application")[
        "isError"
    ]
    assert call(client, sign(), "update_shortlist_notes", role_id=1, notes="x" * 4001)["isError"]


def test_readonly_default_does_not_register_writes(client, settings, verifier, sign):
    settings.enable_shortlist_write = False
    with TestClient(
        build_app(settings, db.get_engine(), verifier), base_url="https://jobbr.test"
    ) as c:
        # HTTP authorization still applies even if caller knows a write tool's name.
        assert c.post(PATH, headers=HEADERS).status_code == 401
        tools = rpc(c, sign()).json()["result"]["tools"]
        assert "update_shortlist_notes" not in {tool["name"] for tool in tools}
        assert call(c, sign(), "update_shortlist_notes", role_id=1, notes="disabled")["isError"]
    assert not MCPSettings(_env_file=None).enable_shortlist_write


def test_no_cookie_query_or_legacy_token_fallback(client, sign):
    assert client.post(PATH + "?access_token=" + sign(), headers=HEADERS).status_code == 401
    assert client.post(PATH, headers={**HEADERS, "X-Jobbr-Token": "test"}).status_code == 401
    assert (
        client.post(PATH, headers={**HEADERS, "Cookie": "__Host-jobbr-session=test"}).status_code
        == 401
    )


def test_host_origin_and_body_limits(client, sign):
    assert rpc(client, sign(), **{"Host": "attacker.test"}).status_code == 421
    assert rpc(client, sign(), **{"Origin": "https://attacker.test"}).status_code == 403
    response = client.post(
        PATH,
        headers={
            **HEADERS,
            "Authorization": "Bearer " + sign(),
            "Content-Type": "application/json",
        },
        content="x" * 40_000,
    )
    assert response.status_code == 413


def test_missing_config_fails_closed(env):
    for field in MCPSettings.model_fields:
        env.delenv("JOBBR_MCP_" + field.upper(), raising=False)
    with pytest.raises(ValueError, match="HTTPS"):
        create_app()


def test_discovery_never_silently_normalizes_issuer(client, settings, verifier):
    settings.issuer = "https://ISSUER.test"
    with pytest.raises(ValueError, match="canonical"):
        build_app(settings, db.get_engine(), verifier)


@pytest.mark.parametrize(
    "changes",
    [
        {"issuer": "http://issuer.test"},
        {"issuer": "https://auth.openai.com"},
        {"owner_subject": ""},
        {"client_id": ""},
        {"resource_url": "https://jobbr.test/wrong"},
        {"jwks_url": "https://user:password@issuer.test/keys"},
    ],
)
def test_unsafe_config_rejected(settings, changes):
    settings = settings.model_copy(update=changes)
    with pytest.raises(ValueError, match=r"MCP|OpenAI"):
        settings.validate_configuration("/jobbr")


def test_jwks_failure_is_closed_and_bounded(settings, sign):
    def oversized(_request):
        return httpx.Response(200, content=b" " * 140_000)

    verifier = JWTVerifier(settings, httpx.MockTransport(oversized))
    assert asyncio.run(verifier.verify_token(sign())) is None


def test_database_errors_do_not_leak_queries_or_private_values(client, sign, monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise OperationalError("PRIVATE query", {"secret": "PRIVATE value"}, Exception("PRIVATE"))

    monkeypatch.setattr("jobbr.mcp_queries.repo.job_rows", unavailable)
    result = call(client, sign(), "search_roles")
    assert result["isError"]
    assert "PRIVATE" not in json.dumps(result)


def test_official_sdk_client_negotiates_and_calls_tools(env, settings, verifier, sign):
    db.init_db()
    seed_catalog()
    app = build_app(settings, db.get_engine(), verifier)

    async def exercise():
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app),
                headers={"Authorization": "Bearer " + sign()},
            ) as http,
            streamable_http_client(RESOURCE, http_client=http) as streams,
            ClientSession(*streams) as session,
        ):
            await session.initialize()
            tools = await session.list_tools()
            assert "search_roles" in {tool.name for tool in tools.tools}
            result = await session.call_tool("get_role", {"role_id": 1})
            assert not result.is_error
            assert result.structured_content["company"]["name"] == "Synthetic Systems"

    asyncio.run(asyncio.wait_for(exercise(), timeout=15))


@pytest.mark.parametrize("document", [{"keys": ["bad"]}, {"keys": []}, [], {"keys": [{}]}])
def test_malformed_jwks_is_closed(settings, sign, document):
    verifier = JWTVerifier(
        settings, httpx.MockTransport(lambda _: httpx.Response(200, json=document))
    )
    assert asyncio.run(verifier.verify_token(sign())) is None


def test_jwks_refresh_throttling_and_rotation(settings, signing_key, sign):
    first = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(signing_key.public_key()))
    first.update({"kid": "test", "alg": "RS256"})
    keys = [first]
    requests = []

    def provider(request):
        requests.append(request)
        return httpx.Response(200, json={"keys": keys})

    verifier = JWTVerifier(settings, httpx.MockTransport(provider))

    async def exercise():
        assert await verifier.verify_token(sign()) is not None
        unknown = sign(headers={"kid": "rotated", "typ": "at+jwt"})
        for _ in range(5):
            assert await verifier.verify_token(unknown) is None
        assert len(requests) == 1
        keys.append({**first, "kid": "rotated"})
        verifier.last_fetch -= 6
        assert await verifier.verify_token(unknown) is not None
        assert len(requests) == 2

    asyncio.run(exercise())


@pytest.mark.usefixtures("postgres")
def test_mcp_postgres_catalog_and_owner_boundary(settings, verifier, sign):
    db.init_db()
    seed_catalog()
    app = build_app(settings, db.get_engine(), verifier)
    with TestClient(app, base_url="https://jobbr.test") as client:
        result = call(client, sign(), "search_roles", query="SQL", limit=1)
        assert result["structuredContent"]["items"][0]["id"] == 1
        assert call(client, sign(), "get_role", role_id=1)["structuredContent"]["posted_at"]
        result = call(client, sign(), "update_shortlist_notes", role_id=1, notes="PG note")
        assert not result["isError"]
        assert rpc(client, sign(sub="second-owner")).status_code == 401
        listed = call(client, sign(), "list_shortlist")["structuredContent"]
        assert listed["items"][0]["shortlist"]["notes"] == "PG note"
