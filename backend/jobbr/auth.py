"""Identity-only OpenAI OIDC with durable shared first-party sessions."""

import asyncio
import base64
import hashlib
import json
import secrets
import time
from typing import Any, Literal
from urllib.parse import quote_plus, urlencode, urlsplit

import httpx
import jwt
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine
from starlette.concurrency import run_in_threadpool

from .auth_store import (
    AuthStore,
    DatabaseAuthStore,
    SessionRecord,
    StoreFull,
    StoreUnavailable,
    Transaction,
    digest,
)

ISSUER = "https://auth.openai.com"
DISCOVERY = ISSUER + "/.well-known/openid-configuration"
SESSION_COOKIE = "__Host-jobbr-session"
TRANSACTION_COOKIE = "__Host-jobbr-login"
SAFE_ALGORITHMS = ("RS256", "PS256", "ES256")


def same_value(left: str, right: str) -> bool:
    return secrets.compare_digest(left.encode(), right.encode())


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JOBBR_OPENAI_", env_file=".env", extra="ignore")

    auth_enabled: bool = False
    client_id: str = ""
    client_secret: str = ""
    token_auth_method: Literal["none", "client_secret_basic"] = "none"  # noqa: S105 - OAuth method names are not passwords
    redirect_uri: str = ""
    allowed_subject: str = ""
    store_key: str = Field(default="", repr=False)

    def problem(self, base: str) -> str | None:  # noqa: PLR0911
        if not self.auth_enabled:
            return "Sign in with ChatGPT is not configured."
        if not self.client_id or self.client_id == "dynamic_agent_client":
            return "A registered website OAuth client ID is required."
        if not self.allowed_subject:
            return "An allowed OpenAI subject is required for this single-owner database."
        try:
            uri = urlsplit(self.redirect_uri)
        except ValueError:
            return "An exact registered HTTPS callback URL matching the mount path is required."
        if (
            uri.scheme != "https"
            or not uri.hostname
            or uri.username
            or uri.password
            or uri.query
            or uri.fragment
            or uri.path != base + "/auth/openai/callback"
        ):
            return "An exact registered HTTPS callback URL matching the mount path is required."
        if self.token_auth_method == "client_secret_basic" and not self.client_secret:  # noqa: S105 - OAuth method names are not passwords
            return "The registered confidential client requires a server-side client secret."
        if self.token_auth_method == "none" and self.client_secret:  # noqa: S105 - OAuth method names are not passwords
            return "Public clients must not configure a client secret."
        return None

    @property
    def origin(self) -> str:
        uri = urlsplit(self.redirect_uri)
        return f"{uri.scheme}://{uri.netloc}"


class AuthFailure(Exception):
    """A deliberately credential-free provider/validation error."""


class AuthService:
    """OIDC verification plus persistent transactions, sessions and shared revocation."""

    def __init__(
        self,
        settings: AuthSettings,
        base: str = "",
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        engine: Engine | None = None,
        store: AuthStore | None = None,
    ) -> None:
        self.settings = settings
        self.base = base
        self.transport = transport
        self.store = store
        self._store_problem: str | None = None
        if settings.auth_enabled and self.store is None:
            if not settings.store_key:
                self._store_problem = "A stable server-side auth store key is required."
            elif engine is None:
                self._store_problem = "A persistent auth database is required."
            else:
                try:
                    self.store = DatabaseAuthStore(engine, settings.store_key)
                except StoreUnavailable:
                    self._store_problem = "The auth store key or database configuration is invalid."
        configuration = json.dumps(
            [ISSUER, settings.client_id, settings.redirect_uri, settings.allowed_subject],
            separators=(",", ":"),
        )
        self.scope = self.store.scope(configuration) if self.store else ""
        self._metadata: dict[str, Any] | None = None
        self._metadata_until = 0.0
        self._keys: list[dict[str, Any]] = []
        self._keys_until = 0.0
        self._keys_last_fetch = 0.0

    def problem(self) -> str | None:
        problem = self.settings.problem(self.base)
        if problem:
            return problem
        if self._store_problem:
            return self._store_problem
        if self.store is None:
            return "A persistent auth database is required."
        try:
            self.store.check()
        except StoreUnavailable:
            return "The persistent auth store is temporarily unavailable."
        return None

    def ensure_ready(self) -> None:
        problem = self.problem()
        if problem:
            raise HTTPException(503, problem)

    def session(self, request: Request) -> SessionRecord | None:
        if self.store is None:
            raise HTTPException(503, "The persistent auth store is unavailable.")
        try:
            record = self.store.get_session(request.cookies.get(SESSION_COOKIE, ""), self.scope)
        except StoreUnavailable:
            raise HTTPException(
                503, "The persistent auth store is temporarily unavailable."
            ) from None
        if record and (
            record.issuer != ISSUER
            or record.client_id != self.settings.client_id
            or not same_value(record.subject, self.settings.allowed_subject)
        ):
            return None
        return record

    async def _json(
        self, client: httpx.AsyncClient, method: str, url: str, **kwargs: Any
    ) -> dict[str, Any]:
        try:
            async with client.stream(method, url, **kwargs) as response:
                response.raise_for_status()
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > 131_072:
                        raise AuthFailure("Provider response exceeded limit")

                payload = json.loads(content)
                if not isinstance(payload, dict):
                    raise AuthFailure("Invalid provider response")
                return payload
        except (httpx.HTTPError, ValueError) as exc:
            raise AuthFailure("Provider request failed") from exc

    @staticmethod
    def _provider_url(value: Any) -> str:
        if not isinstance(value, str):
            raise AuthFailure("Missing discovery endpoint")
        uri = urlsplit(value)
        if (
            uri.scheme != "https"
            or uri.netloc != "auth.openai.com"
            or uri.fragment
            or uri.username
            or uri.password
        ):
            raise AuthFailure("Untrusted discovery endpoint")
        return value

    async def metadata(self, client: httpx.AsyncClient) -> dict[str, Any]:
        if self._metadata is None or self._metadata_until <= time.time():
            data = await self._json(client, "GET", DISCOVERY)
            if data.get("issuer") != ISSUER:
                raise AuthFailure("Unexpected discovery issuer")
            for endpoint in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
                self._provider_url(data.get(endpoint))
            if self.settings.token_auth_method not in data.get(
                "token_endpoint_auth_methods_supported", []
            ):
                raise AuthFailure("Registered token authentication method unavailable")
            self._metadata = data
            self._metadata_until = time.time() + 3600
        return self._metadata

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(5.0),
            follow_redirects=False,
            transport=self.transport,
            trust_env=False,
        )

    async def start(self, request: Request) -> RedirectResponse:
        await run_in_threadpool(self.ensure_ready)
        try:
            async with asyncio.timeout(12), self.client() as client:
                metadata = await self.metadata(client)
        except (AuthFailure, TimeoutError):
            raise HTTPException(503, "OpenAI sign-in is temporarily unavailable.") from None
        browser_id = secrets.token_urlsafe(32)
        transaction = Transaction(
            secrets.token_urlsafe(32),
            secrets.token_urlsafe(64),
            secrets.token_urlsafe(32),
            time.time() + 600,
        )
        assert self.store is not None
        try:
            await run_in_threadpool(
                self.store.create_transaction,
                browser_id,
                request.cookies.get(TRANSACTION_COOKIE, ""),
                transaction,
                self.scope,
                self.settings.redirect_uri,
            )
        except (StoreUnavailable, StoreFull):
            raise HTTPException(
                503, "Sign-in storage is temporarily unavailable; try again later."
            ) from None
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(transaction.verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        query = urlencode(
            {
                "client_id": self.settings.client_id,
                "redirect_uri": self.settings.redirect_uri,
                "response_type": "code",
                "scope": "openid profile email",
                "state": transaction.state,
                "nonce": transaction.nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        response = RedirectResponse(metadata["authorization_endpoint"] + "?" + query, 302)
        response.set_cookie(
            TRANSACTION_COOKIE,
            browser_id,
            max_age=600,
            secure=True,
            httponly=True,
            samesite="lax",
            path="/",
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    async def verify(
        self, client: httpx.AsyncClient, metadata: dict[str, Any], token: str, nonce: str
    ) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("crit"):
                raise AuthFailure("Unsupported critical token headers")
            algorithm = header.get("alg")
            if algorithm not in SAFE_ALGORITHMS or algorithm not in metadata.get(
                "id_token_signing_alg_values_supported", []
            ):
                raise AuthFailure("Unsupported signing algorithm")
            kid = header.get("kid")
            if not isinstance(kid, str) or not kid:
                raise AuthFailure("Missing signing key identifier")
            matches = [key for key in self._keys if key.get("kid") == kid]
            now = time.time()
            if self._keys_until <= now or (not matches and now - self._keys_last_fetch >= 5):
                keys = (await self._json(client, "GET", metadata["jwks_uri"])).get("keys")
                if not isinstance(keys, list) or len(keys) > 100:
                    raise AuthFailure("Invalid signing keys")
                self._keys = [key for key in keys if isinstance(key, dict)]
                self._keys_until = now + 300
                self._keys_last_fetch = now
                matches = [key for key in self._keys if key.get("kid") == kid]
            if len(matches) != 1:
                raise AuthFailure("Unknown signing key")
            key = matches[0]
            if key.get("use", "sig") != "sig" or key.get("alg", algorithm) != algorithm:
                raise AuthFailure("Invalid signing key usage")
            claims: dict[str, Any] = jwt.decode(
                token,
                jwt.PyJWK.from_dict(key, algorithm=algorithm).key,
                algorithms=[algorithm],
                issuer=ISSUER,
                audience=self.settings.client_id,
                leeway=5,
                options={"require": ["iss", "aud", "sub", "exp", "iat", "nonce"]},
            )
            if (
                not isinstance(claims["nonce"], str)
                or not same_value(claims["nonce"], nonce)
                or not isinstance(claims["sub"], str)
                or not claims["sub"]
            ):
                raise AuthFailure("Invalid identity claims")
            audience = claims["aud"]
            if (
                isinstance(audience, list)
                and len(audience) > 1
                and claims.get("azp") != self.settings.client_id
            ):
                raise AuthFailure("Missing authorized party")
            if "azp" in claims and claims["azp"] != self.settings.client_id:
                raise AuthFailure("Wrong authorized party")
            return claims  # noqa: TRY300
        except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
            raise AuthFailure("Identity verification failed") from exc

    async def callback(self, request: Request) -> Response:
        response: Response
        try:
            await run_in_threadpool(self.ensure_ready)
            assert self.store is not None
            tx = await run_in_threadpool(
                self.store.consume_transaction,
                request.cookies.get(TRANSACTION_COOKIE, ""),
                self.scope,
                self.settings.redirect_uri,
            )
            query = request.query_params
            state = query.get("state", "")
            if (
                not tx
                or len(query.getlist("state")) != 1
                or len(state) != 43
                or not same_value(digest(state), tx.state)
                or "error" in query
                or len(query.getlist("code")) != 1
                or not query.get("code")
                or len(query["code"]) > 8192
            ):
                raise AuthFailure("Invalid authorization transaction")  # noqa: TRY301
            async with asyncio.timeout(12), self.client() as client:
                metadata = await self.metadata(client)
                headers = {"Accept": "application/json"}
                if self.settings.token_auth_method == "client_secret_basic":  # noqa: S105 - OAuth method names are not passwords
                    credential = (
                        quote_plus(self.settings.client_id)
                        + ":"
                        + quote_plus(self.settings.client_secret)
                    )
                    headers["Authorization"] = (
                        "Basic " + base64.b64encode(credential.encode()).decode()
                    )
                tokens = await self._json(
                    client,
                    "POST",
                    metadata["token_endpoint"],
                    headers=headers,
                    data={
                        "grant_type": "authorization_code",
                        "client_id": self.settings.client_id,
                        "redirect_uri": self.settings.redirect_uri,
                        "code": query["code"],
                        "code_verifier": tx.verifier,
                    },
                )
                token = tokens.get("id_token")
                if not isinstance(token, str) or len(token) > 32768:
                    raise AuthFailure("Missing identity token")  # noqa: TRY301
                claims = await self.verify(client, metadata, token, tx.nonce)
            if not same_value(claims["sub"], self.settings.allowed_subject):
                raise AuthFailure("Identity is not authorized")  # noqa: TRY301
            session_id = secrets.token_urlsafe(32)
            record = SessionRecord(
                ISSUER,
                self.settings.client_id,
                claims["sub"],
                claims["name"][:300] if isinstance(claims.get("name"), str) else None,
                claims["email"][:320] if isinstance(claims.get("email"), str) else None,
                self.store.csrf(session_id),
                time.time() + 28800,
            )
            await run_in_threadpool(
                self.store.rotate_session,
                request.cookies.get(SESSION_COOKIE, ""),
                session_id,
                record,
                self.scope,
            )
            response = RedirectResponse(self.base + "/", 303)
            response.set_cookie(
                SESSION_COOKIE,
                session_id,
                max_age=28800,
                secure=True,
                httponly=True,
                samesite="lax",
                path="/",
            )
        except HTTPException as exc:
            response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        except (StoreUnavailable, StoreFull):
            response = JSONResponse(
                {"detail": "Sign-in storage is temporarily unavailable. Please try again."},
                status_code=503,
            )
        except (AuthFailure, TimeoutError):
            response = JSONResponse(
                {"detail": "Sign-in could not be verified. Please try again."}, status_code=400
            )
        response.delete_cookie(TRANSACTION_COOKIE, secure=True, httponly=True, samesite="lax")
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


def require_session(request: Request) -> SessionRecord:
    service: AuthService = request.app.state.auth
    service.ensure_ready()
    record = service.session(request)
    if not record:
        raise HTTPException(401, "Sign in with ChatGPT to access Jobbr.")
    return record


def require_csrf(request: Request) -> SessionRecord:
    record = require_session(request)
    service: AuthService = request.app.state.auth
    token = request.headers.get("X-CSRF-Token", "")
    if request.headers.get("Origin") != service.settings.origin or not same_value(
        token, record.csrf_token
    ):
        raise HTTPException(403, "Invalid request origin or CSRF token.")
    return record


def build_auth_router(service: AuthService) -> APIRouter:
    router = APIRouter(tags=["auth"])

    @router.get("/api/auth/session")
    def status(request: Request) -> JSONResponse:
        problem = service.problem()
        record = service.session(request) if not problem else None
        return JSONResponse(
            {
                "enabled": service.settings.auth_enabled,
                "ready": problem is None,
                "reason": problem,
                "authenticated": record is not None,
                "user": record.user() if record else None,
                "csrf_token": record.csrf_token if record else None,
                "login_url": service.base + "/auth/openai" if not problem else None,
            },
            headers={"Cache-Control": "no-store"},
        )

    @router.get("/auth/openai")
    async def start(request: Request) -> Response:
        return await service.start(request)

    @router.get("/auth/openai/callback")
    async def callback(request: Request) -> Response:
        return await service.callback(request)

    @router.post("/api/auth/logout")
    def logout(request: Request) -> Response:
        require_csrf(request)
        assert service.store is not None
        try:
            service.store.revoke_session(request.cookies.get(SESSION_COOKIE, ""), service.scope)
        except StoreUnavailable:
            raise HTTPException(
                503, "Sign-out storage is temporarily unavailable. Please try again."
            ) from None
        response = Response(status_code=204, headers={"Cache-Control": "no-store"})
        response.delete_cookie(SESSION_COOKIE, secure=True, httponly=True, samesite="lax")
        return response

    return router
