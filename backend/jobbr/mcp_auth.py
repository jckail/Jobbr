"""OAuth resource-server boundary. Website OIDC tokens are never MCP credentials."""

import asyncio
import json
import time
from typing import Any
from urllib.parse import urlsplit

import httpx
import jwt
from mcp.server.auth.provider import AccessToken
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

READ_SCOPE = "jobbr:read"
SHORTLIST_SCOPE = "jobbr:shortlist:read"
WRITE_SCOPE = "jobbr:shortlist:write"
SAFE_ALGORITHMS = ("RS256", "PS256", "ES256")
MAX_TOKEN_BYTES = 16_384
MAX_JWKS_BYTES = 131_072


class MCPSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JOBBR_MCP_", env_file=".env", extra="ignore")

    resource_url: str = ""
    issuer: str = ""
    jwks_url: str = ""
    client_id: str = ""
    owner_subject: str = Field(default="", repr=False)
    enable_shortlist_write: bool = False

    def validate_configuration(self, base: str) -> None:
        for value in (self.resource_url, self.issuer, self.jwks_url):
            uri = urlsplit(value)
            if (
                uri.scheme != "https"
                or not uri.hostname
                or uri.username
                or uri.password
                or uri.query
                or uri.fragment
            ):
                raise ValueError("MCP resource, issuer and JWKS URLs must be explicit HTTPS URLs.")
        if urlsplit(self.resource_url).path != base + "/mcp":
            raise ValueError("MCP resource URL must end at the configured base path plus /mcp.")
        if urlsplit(self.issuer).hostname == "auth.openai.com":
            raise ValueError("OpenAI website identity tokens are not Jobbr MCP access tokens.")
        if not self.client_id.strip() or not self.owner_subject.strip():
            raise ValueError("MCP requires an approved client ID and exact database-owner subject.")

    @property
    def metadata_url(self) -> str:
        uri = urlsplit(self.resource_url)
        return f"{uri.scheme}://{uri.netloc}/.well-known/oauth-protected-resource{uri.path}"

    def challenge(self, scopes: list[str]) -> str:
        return (
            f'Bearer resource_metadata="{self.metadata_url}", '
            f'error="insufficient_scope", scope="{" ".join(scopes)}"'
        )


class JWTVerifier:
    """Validate RFC 9068 user access tokens from one configured authorization server.

    Only public keys are cached. No JWT-supplied URL is fetched and no credentials
    are sent downstream. The transport injection is for synthetic provider tests.
    """

    def __init__(
        self, settings: MCPSettings, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.settings = settings
        self.transport = transport
        self.keys: list[dict[str, Any]] = []
        self.keys_until = 0.0
        self.last_fetch = float("-inf")
        self.lock = asyncio.Lock()

    async def _refresh(self) -> None:
        self.last_fetch = time.monotonic()
        async with (
            httpx.AsyncClient(
                transport=self.transport, timeout=5, follow_redirects=False, trust_env=False
            ) as client,
            client.stream("GET", self.settings.jwks_url) as response,
        ):
            response.raise_for_status()
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > MAX_JWKS_BYTES:
                    raise ValueError("JWKS response exceeded the size limit.")
        document = json.loads(data)
        keys = document.get("keys") if isinstance(document, dict) else None
        if (
            not isinstance(keys, list)
            or not keys
            or len(keys) > 100
            or not all(isinstance(key, dict) for key in keys)
        ):
            raise ValueError("Invalid JWKS.")
        self.keys = keys
        self.keys_until = time.monotonic() + 300

    async def _key(self, kid: str, algorithm: str) -> jwt.PyJWK:
        async with self.lock:
            now = time.monotonic()
            unknown = not any(key.get("kid") == kid for key in self.keys)
            if (now >= self.keys_until or unknown) and now - self.last_fetch >= 5:
                await self._refresh()
            if time.monotonic() >= self.keys_until:
                raise ValueError("Signing keys unavailable.")
            candidates = [key for key in self.keys if key.get("kid") == kid]
            if len(candidates) != 1:
                raise ValueError("Unknown or ambiguous signing key.")
            key = candidates[0]
            if key.get("use", "sig") != "sig" or key.get("alg", algorithm) != algorithm:
                raise ValueError("Signing key not valid for this algorithm.")
            if "key_ops" in key and "verify" not in key["key_ops"]:
                raise ValueError("Signing key does not permit verification.")
            return jwt.PyJWK.from_dict(key, algorithm=algorithm)

    def _claims(self, token: str, key: jwt.PyJWK) -> dict[str, Any]:
        claims: dict[str, Any] = jwt.decode(
            token,
            key,
            algorithms=list(SAFE_ALGORITHMS),
            issuer=self.settings.issuer,
            audience=self.settings.resource_url,
            options={
                "require": ["iss", "aud", "exp", "iat", "sub", "client_id", "scope"],
                "strict_aud": True,
            },
        )
        if (
            claims["sub"] != self.settings.owner_subject
            or claims["client_id"] != self.settings.client_id
            or not isinstance(claims["scope"], str)
            or type(claims["exp"]) is not int
            or type(claims["iat"]) is not int
            or not 0 < claims["exp"] - claims["iat"] <= 3600
            or claims.get("gty") in {"client-credentials", "client_credentials"}
        ):
            raise ValueError("Access token is not authorized for this owner.")
        return claims

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            async with asyncio.timeout(6):
                if len(token) > MAX_TOKEN_BYTES:
                    return None
                header = jwt.get_unverified_header(token)
                algorithm, kid = header.get("alg"), header.get("kid")
                if (
                    algorithm not in SAFE_ALGORITHMS
                    or header.get("typ") != "at+jwt"
                    or not isinstance(kid, str)
                    or not kid
                ):
                    return None
                claims = self._claims(token, await self._key(kid, algorithm))
                return AccessToken(
                    token=token,
                    client_id=claims["client_id"],
                    subject=claims["sub"],
                    claims={"iss": claims["iss"]},
                    scopes=claims["scope"].split(),
                    expires_at=claims["exp"],
                    resource=self.settings.resource_url,
                )
        except (jwt.PyJWTError, httpx.HTTPError, ValueError, TypeError, KeyError, TimeoutError):
            # Credential-free errors; never log token/provider payloads.
            return None
