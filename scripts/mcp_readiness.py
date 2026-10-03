"""Check public MCP routing/discovery only; never authenticate or read owner data."""

from __future__ import annotations

import argparse
import http.client
import json
import re
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlsplit, urlunsplit

MAX_RESPONSE_BYTES = 65_536


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


def validate_url(value: str, *, allow_loopback: bool = False) -> None:
    parsed = urlsplit(value)
    loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if (
        parsed.scheme != "https" and not (allow_loopback and loopback and parsed.scheme == "http")
    ) or (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or any(character.isspace() or character in '\\"' for character in value)
    ):
        raise ValueError("Use an explicit HTTPS URL without credentials, query or fragment.")
    _port = parsed.port  # Validate a supplied port before sending any request.


def metadata_url(resource: str) -> str:
    parsed = urlsplit(resource)
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            "/.well-known/oauth-protected-resource" + parsed.path,
            "",
            "",
        )
    )


def valid_challenge(challenge: str, expected_metadata: str) -> bool:
    # Reject multiple schemes/duplicate parameters instead of combining their values.
    parameter = r'[A-Za-z_][A-Za-z_0-9]*="[^"\\]*"'
    if not re.fullmatch(
        r"Bearer\s+" + parameter + r"(?:\s*,\s*" + parameter + r")*", challenge, flags=re.IGNORECASE
    ):
        return False
    pairs = re.findall(r'([A-Za-z_][A-Za-z_0-9]*)="([^"\\]*)"', challenge)
    values = {name.lower(): value for name, value in pairs}
    return (
        len(values) == len(pairs)
        and values.get("resource_metadata") == expected_metadata
        and "jobbr:read" in values.get("scope", "").split()
    )


def probe(resource: str, issuer: str, *, target: str | None = None) -> dict[str, Any]:
    validate_url(resource)
    validate_url(issuer)
    target = target or resource
    validate_url(target, allow_loopback=True)
    if urlsplit(target).path != urlsplit(resource).path:
        raise ValueError("Probe and canonical resource paths must match exactly.")
    expected_metadata = metadata_url(resource)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    failures: list[str] = []

    def request(url: str, *, data: bytes | None = None) -> tuple[int, Any, bytes]:
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Accept": "application/json, text/event-stream",
                **({"Content-Type": "application/json"} if data is not None else {}),
            },
        )
        try:
            response = opener.open(req, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise ValueError("Response exceeded the diagnostic size limit.")
            return response.status, response.headers, body

    try:
        status, headers, body = request(metadata_url(target))
        if status != 200 or headers.get_content_type() != "application/json":
            failures.append("Discovery must return HTTP 200 with application/json.")
        else:
            document = json.loads(body)
            if not isinstance(document, dict) or document.get("resource") != resource:
                failures.append("Discovery resource does not match the canonical URL.")
            if not isinstance(document, dict) or document.get("authorization_servers") != [issuer]:
                failures.append(
                    "Discovery authorization server does not match the expected issuer."
                )
            scopes = document.get("scopes_supported") if isinstance(document, dict) else None
            if not isinstance(scopes, list) or "jobbr:read" not in scopes:
                failures.append("Discovery must advertise jobbr:read.")
    except (OSError, ValueError, RecursionError, http.client.HTTPException):
        failures.append("Discovery request failed or returned invalid/bounded data.")

    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "jobbr-readiness", "version": "1"},
            },
        }
    ).encode()
    try:
        status, headers, _body = request(target, data=payload)
        challenge = headers.get("WWW-Authenticate", "")
        if status != 401:
            failures.append("Unauthenticated MCP initialize must return HTTP 401.")
        if not valid_challenge(challenge, expected_metadata):
            failures.append(
                "MCP Bearer challenge must identify the expected metadata and jobbr:read."
            )
    except (OSError, ValueError, http.client.HTTPException):
        failures.append("Unauthenticated MCP probe failed or exceeded the diagnostic size limit.")
    return {
        "routing_ready": not failures,
        "authenticated_flow_checked": False,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resource-url", required=True, help="Exact configured HTTPS MCP audience."
    )
    parser.add_argument("--issuer", required=True, help="Expected external authorization issuer.")
    parser.add_argument(
        "--probe-url", help="Optional matching-path endpoint; HTTP allowed on loopback."
    )
    args = parser.parse_args()
    try:
        result = probe(args.resource_url, args.issuer, target=args.probe_url)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result))
    return 0 if result["routing_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
