"""Fetching third-party pages from a public host: block SSRF into private networks."""

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

from .config import get_settings

UA = "Mozilla/5.0 (compatible; JobbrBot/2.0; +https://jckail.com/jobbr)"
MAX_BYTES = 3_000_000


class FetchError(Exception):
    pass


def assert_public_url(url: str) -> None:
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise FetchError("Only http(s) URLs are supported.")
    if get_settings().allow_private_fetch:
        return
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80))
    except socket.gaierror as e:
        raise FetchError(f"Could not resolve {p.hostname}.") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise FetchError("That address is not publicly routable.")


def fetch_html(url: str) -> tuple[str, str]:
    """Return (final_url, html). Follows redirects manually so each hop is re-validated."""
    s = get_settings()
    current = url
    with httpx.Client(timeout=s.fetch_timeout_s, headers={"User-Agent": UA}) as client:
        for _ in range(5):
            assert_public_url(current)
            try:
                r = client.get(current, follow_redirects=False)
            except httpx.HTTPError as e:
                raise FetchError(f"Request failed: {e}") from e
            if r.is_redirect and r.headers.get("location"):
                current = str(httpx.URL(current).join(r.headers["location"]))
                continue
            if r.status_code >= 400:
                raise FetchError(f"The site returned HTTP {r.status_code}.")
            if len(r.content) > MAX_BYTES:
                raise FetchError("Page is too large.")
            return current, r.text
    raise FetchError("Too many redirects.")
