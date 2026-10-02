"""Public-page fetching with DNS pinning, socket deadlines and bounded streaming."""

import ipaddress
import socket
import ssl
import time
from collections.abc import Iterable, Iterator
from typing import Any
from urllib.parse import urlsplit

import httpcore
import httpx

from .config import get_settings

UA = "Mozilla/5.0 (compatible; JobbrBot/2.0; +https://jckail.com/jobbr)"
MAX_BYTES = 3_000_000
MAX_URL_CHARS = 8192
MAX_REDIRECTS = 5


class FetchError(Exception):
    """Sanitized message safe to show to the caller."""


def _remaining(deadline: float, timeout: float | None = None) -> float:
    left = deadline - time.monotonic()
    if left <= 0:
        raise FetchError("Page fetch timed out.")
    return min(left, timeout) if timeout is not None else left


def _resolve_url(value: str) -> tuple[httpx.URL, str]:
    if len(value) > MAX_URL_CHARS or any(ord(char) < 33 for char in value):
        raise FetchError("Invalid page URL.")
    try:
        url = httpx.URL(value)
        if url.scheme not in ("http", "https") or not url.host:
            raise FetchError("Only http(s) URLs are supported.")
        if url.userinfo or "@" in urlsplit(value).netloc:
            raise FetchError("URLs containing credentials are not supported.")
        port = url.port if url.port is not None else (443 if url.scheme == "https" else 80)
        if not 1 <= port <= 65535:
            raise FetchError("Invalid page URL port.")
        if port not in (80, 443) and not get_settings().allow_private_fetch:
            raise FetchError("Only standard HTTP and HTTPS ports are supported.")
        host = url.raw_host.decode("ascii")
        if "%" in host:
            raise FetchError("Scoped addresses are not supported.")
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        addresses = [ipaddress.ip_address(info[4][0]) for info in infos]
    except (ValueError, UnicodeError, httpx.InvalidURL, OSError) as exc:
        raise FetchError("Invalid or unresolvable page URL.") from exc
    if not addresses:
        raise FetchError("Could not resolve the page host.")
    if not get_settings().allow_private_fetch and any(
        not address.is_global or address.is_multicast for address in addresses
    ):
        raise FetchError("That address is not publicly routable.")
    return url.copy_with(fragment=None), str(addresses[0])


def assert_public_url(url: str) -> None:
    _resolve_url(url)


class _DeadlineStream(httpcore.NetworkStream):
    def __init__(self, stream: httpcore.NetworkStream, deadline: float):
        self.stream = stream
        self.deadline = deadline

    def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        return self.stream.read(max_bytes, timeout=_remaining(self.deadline, timeout))

    def write(self, buffer: bytes, timeout: float | None = None) -> None:
        self.stream.write(buffer, timeout=_remaining(self.deadline, timeout))

    def close(self) -> None:
        self.stream.close()

    def start_tls(
        self,
        ssl_context: ssl.SSLContext,
        server_hostname: str | None = None,
        timeout: float | None = None,
    ) -> httpcore.NetworkStream:
        self.stream = self.stream.start_tls(
            ssl_context,
            server_hostname=server_hostname,
            timeout=_remaining(self.deadline, timeout),
        )
        return self

    def get_extra_info(self, info: str) -> Any:
        return self.stream.get_extra_info(info)


class _PinnedBackend(httpcore.NetworkBackend):
    def __init__(self, hostname: str, address: str, port: int, deadline: float):
        self.hostname, self.address, self.port, self.deadline = hostname, address, port, deadline
        self.backend = httpcore.SyncBackend()

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[
            tuple[int, int, int] | tuple[int, int, bytes | bytearray] | tuple[int, int, None, int]
        ]
        | None = None,
    ) -> httpcore.NetworkStream:
        if host != self.hostname or port != self.port:
            raise FetchError("Unexpected fetch destination.")
        stream = self.backend.connect_tcp(
            self.address,
            port,
            timeout=_remaining(self.deadline, timeout),
            local_address=local_address,
            socket_options=socket_options,
        )
        return _DeadlineStream(stream, self.deadline)


class _ResponseStream(httpx.SyncByteStream):
    def __init__(self, stream: Iterable[bytes]):
        self.stream = stream

    def __iter__(self) -> Iterator[bytes]:
        yield from self.stream

    def close(self) -> None:
        close = getattr(self.stream, "close", None)
        if close:
            close()


class _PinnedTransport(httpx.BaseTransport):
    def __init__(self, url: httpx.URL, address: str, deadline: float):
        self.pool = httpcore.ConnectionPool(
            ssl_context=ssl.create_default_context(),
            retries=0,
            max_connections=1,
            network_backend=_PinnedBackend(
                url.raw_host.decode("ascii"),
                address,
                url.port or (443 if url.scheme == "https" else 80),
                deadline,
            ),
        )

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self.pool.handle_request(
            httpcore.Request(
                method=request.method,
                url=httpcore.URL(
                    scheme=request.url.raw_scheme,
                    host=request.url.raw_host,
                    port=request.url.port,
                    target=request.url.raw_path,
                ),
                headers=request.headers.raw,
                content=request.stream,
                extensions=request.extensions,
            )
        )
        assert isinstance(response.stream, Iterable)
        return httpx.Response(
            response.status,
            headers=response.headers,
            stream=_ResponseStream(response.stream),
            extensions=response.extensions,
        )

    def close(self) -> None:
        self.pool.close()


def _read_page(response: httpx.Response, deadline: float) -> str:
    encoding = response.headers.get("content-encoding", "identity").lower().strip()
    if encoding not in ("", "identity"):
        raise FetchError("Compressed pages are not supported; paste the posting text instead.")
    size = response.headers.get("content-length")
    if size:
        try:
            if int(size) < 0 or int(size) > MAX_BYTES:
                raise FetchError("Page is too large.")
        except ValueError as exc:
            raise FetchError("Invalid page response.") from exc
    chunks = bytearray()
    for chunk in response.iter_raw():
        _remaining(deadline)
        if len(chunks) + len(chunk) > MAX_BYTES:
            raise FetchError("Page is too large.")
        chunks.extend(chunk)
    _remaining(deadline)
    try:
        return chunks.decode(response.encoding or "utf-8", errors="replace")
    except LookupError:
        return chunks.decode("utf-8", errors="replace")


def fetch_html(url: str) -> tuple[str, str]:
    """Each redirect gets fresh validation and an isolated pinned connection."""
    settings = get_settings()
    deadline = time.monotonic() + settings.fetch_timeout_s
    current = url
    try:
        for _ in range(MAX_REDIRECTS + 1):
            parsed, address = _resolve_url(current)
            current = str(parsed)
            with (
                httpx.Client(
                    transport=_PinnedTransport(parsed, address, deadline),
                    trust_env=False,
                    timeout=_remaining(deadline),
                    follow_redirects=False,
                    headers={"User-Agent": UA, "Accept-Encoding": "identity"},
                ) as client,
                client.stream("GET", parsed) as response,
            ):
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise FetchError("Invalid page redirect.")
                    if len(location) > MAX_URL_CHARS:
                        raise FetchError("Invalid page redirect.")
                    current = str(parsed.join(location))
                    continue
                if response.status_code >= 400:
                    raise FetchError(f"The site returned HTTP {response.status_code}.")
                return current, _read_page(response, deadline)
    except (
        httpx.HTTPError,
        httpcore.NetworkError,
        httpcore.TimeoutException,
        httpcore.ProtocolError,
        ValueError,
        OSError,
    ) as exc:
        raise FetchError("Page request failed; paste the posting text instead.") from exc
    raise FetchError("Too many redirects.")
