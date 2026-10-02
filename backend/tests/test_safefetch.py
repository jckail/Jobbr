"""Exercise real HTTPX/httpcore parsing over mocked network streams, never the network."""

import ssl
import time

import httpcore
import pytest

from jobbr import safefetch
from jobbr.config import Settings

PUBLIC = "93.184.216.34"


@pytest.fixture
def public_env(monkeypatch):
    settings = Settings(allow_private_fetch=False, fetch_timeout_s=1, _env_file=None)
    monkeypatch.setattr(safefetch, "get_settings", lambda: settings)
    return settings


def answer(address=PUBLIC):
    return [address]


class RecordingStream(httpcore.MockStream):
    def __init__(self, data, calls):
        super().__init__(data)
        self.calls = calls
        self.closed = False

    def write(self, buffer, timeout=None):
        self.calls.append(("write", buffer, timeout))

    def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        self.calls.append(("tls", server_hostname, ssl_context, timeout))
        return self

    def close(self):
        self.closed = True
        super().close()


def install_network(monkeypatch, responses, dns=None):
    calls = []
    streams = []
    remaining = iter(responses)
    monkeypatch.setattr(safefetch, "resolve_addresses", dns or (lambda *args, **kwargs: answer()))

    def connect(self, host, port, **kwargs):
        calls.append(("connect", host, port, kwargs))
        stream = RecordingStream(next(remaining), calls)
        streams.append(stream)
        return stream

    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", connect)
    return calls, streams


def http_response(body=b"hello", extra=b""):
    return [
        b"HTTP/1.1 200 OK\r\nContent-Length: "
        + str(len(body)).encode()
        + b"\r\n"
        + extra
        + b"\r\n",
        body,
    ]


def test_dns_rebinding_is_pinned_tls_and_host_preserved(public_env, monkeypatch):
    dns_calls = []

    def dns(host, port, deadline):
        dns_calls.append(host)
        return answer(PUBLIC if len(dns_calls) == 1 else "127.0.0.1")

    calls, streams = install_network(monkeypatch, [http_response()], dns)
    final, html = safefetch.fetch_html("https://jobs.example/path?q=1")
    assert html == "hello"
    assert final == "https://jobs.example/path?q=1"
    assert dns_calls == ["jobs.example"]
    assert next(call for call in calls if call[0] == "connect")[1] == PUBLIC
    tls = next(call for call in calls if call[0] == "tls")
    assert tls[1] == "jobs.example"
    assert tls[2].check_hostname
    assert tls[2].verify_mode == ssl.CERT_REQUIRED
    writes = b"".join(call[1] for call in calls if call[0] == "write")
    assert b"Host: jobs.example\r\n" in writes
    assert b"Accept-Encoding: identity\r\n" in writes
    assert streams[0].closed


def test_private_redirect_never_connected(public_env, monkeypatch):
    def dns(host, port, deadline):
        return answer("127.0.0.1" if host == "internal.example" else PUBLIC)

    calls, streams = install_network(
        monkeypatch,
        [
            [
                b"HTTP/1.1 302 Found\r\nLocation: http://internal.example/secret\r\n"
                b"Content-Length: 0\r\n\r\n"
            ]
        ],
        dns,
    )
    with pytest.raises(safefetch.FetchError, match="publicly routable"):
        safefetch.fetch_html("https://jobs.example/")
    assert len([call for call in calls if call[0] == "connect"]) == 1
    assert streams[0].closed


@pytest.mark.parametrize(
    "value",
    [
        "http://user:password@example.com",
        "https://user@example.com",
        "http://example.com:bad",
        "http://example.com:65536",
        "http://example.com:0",
        "http://example.com:8080",
        "file:///etc/passwd",
        "http://[fe80::1%25eth0]/",
        "http://example.com/\nsecret",
        "http://example.com/ space",
    ],
)
def test_invalid_urls_do_not_resolve(public_env, monkeypatch, value):
    def dns(*args, **kwargs):
        pytest.fail("Invalid URL reached DNS")

    monkeypatch.setattr(safefetch, "resolve_addresses", dns)
    with pytest.raises(safefetch.FetchError):
        safefetch.fetch_html(value)


def test_unicode_host_is_idna_and_keeps_identity(public_env, monkeypatch):
    hosts = []

    def dns(host, port, deadline):
        hosts.append(host)
        return answer()

    calls, _ = install_network(monkeypatch, [http_response()], dns)
    safefetch.fetch_html("https://bücher.example/jobs")
    assert hosts == ["xn--bcher-kva.example"]
    assert next(call for call in calls if call[0] == "tls")[1] == hosts[0]


def test_mixed_dns_answers_rejected(public_env, monkeypatch):
    monkeypatch.setattr(
        safefetch, "resolve_addresses", lambda *a, **k: answer() + answer("10.0.0.1")
    )
    with pytest.raises(safefetch.FetchError, match="publicly routable"):
        safefetch.fetch_html("https://jobs.example")


def test_stream_limit_without_content_length(public_env, monkeypatch):
    monkeypatch.setattr(safefetch, "MAX_BYTES", 12)
    calls, streams = install_network(
        monkeypatch,
        [[b"HTTP/1.1 200 OK\r\nConnection: close\r\n\r\n", b"a" * 8, b"b" * 8, b"unread"]],
    )
    with pytest.raises(safefetch.FetchError, match="too large"):
        safefetch.fetch_html("https://jobs.example")
    assert streams[0].closed
    assert calls


def test_content_length_rejected_before_body(public_env, monkeypatch):
    monkeypatch.setattr(safefetch, "MAX_BYTES", 12)
    _, streams = install_network(
        monkeypatch, [[b"HTTP/1.1 200 OK\r\nContent-Length: 1000\r\n\r\n", b"unread"]]
    )
    with pytest.raises(safefetch.FetchError, match="too large"):
        safefetch.fetch_html("https://jobs.example")
    assert streams[0].closed


def test_compression_rejected_without_inflation(public_env, monkeypatch):
    install_network(monkeypatch, [http_response(b"invalid gzip", b"Content-Encoding: gzip\r\n")])
    with pytest.raises(safefetch.FetchError, match="Compressed"):
        safefetch.fetch_html("https://jobs.example")


def test_proxy_environment_is_ignored(public_env, monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://private-proxy.invalid:3128")
    monkeypatch.setenv("SSL_CERT_FILE", "/nonexistent/private-cert.pem")
    calls, _ = install_network(monkeypatch, [http_response()])
    assert safefetch.fetch_html("https://jobs.example")[1] == "hello"
    assert next(call for call in calls if call[0] == "connect")[1] == PUBLIC


def test_network_error_is_sanitized(public_env, monkeypatch):
    monkeypatch.setattr(safefetch, "resolve_addresses", lambda *a, **k: answer())

    def connect(*args, **kwargs):
        raise httpcore.ConnectError("private-secret upstream exception")

    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", connect)
    with pytest.raises(safefetch.FetchError) as error:
        safefetch.fetch_html("https://jobs.example/?token=private-secret")
    assert "private-secret" not in str(error.value)


def test_deadline_caps_socket_operations(public_env):
    calls = []
    stream = RecordingStream([b"data"], calls)
    bounded = safefetch._DeadlineStream(stream, time.monotonic() + 0.1)
    bounded.write(b"hello", timeout=30)
    assert 0 < calls[0][2] <= 0.1
    expired = safefetch._DeadlineStream(stream, time.monotonic() - 1)
    with pytest.raises(safefetch.FetchError, match="timed out"):
        expired.read(1, timeout=30)


def test_redirects_revalidate_same_host(public_env, monkeypatch):
    count = 0

    def dns(*args, **kwargs):
        nonlocal count
        count += 1
        return answer(PUBLIC if count == 1 else "10.0.0.2")

    calls, _ = install_network(
        monkeypatch, [[b"HTTP/1.1 302 Found\r\nLocation: /next\r\nContent-Length: 0\r\n\r\n"]], dns
    )
    with pytest.raises(safefetch.FetchError, match="publicly routable"):
        safefetch.fetch_html("https://jobs.example/")
    assert count == 2
    assert len([call for call in calls if call[0] == "connect"]) == 1


def test_redirect_budget_closes_all_streams(public_env, monkeypatch):
    redirect = [b"HTTP/1.1 302 Found\r\nLocation: /loop\r\nContent-Length: 0\r\n\r\n"]
    calls, streams = install_network(monkeypatch, [list(redirect) for _ in range(6)])
    with pytest.raises(safefetch.FetchError, match="Too many redirects"):
        safefetch.fetch_html("https://jobs.example/")
    assert len([call for call in calls if call[0] == "connect"]) == 6
    assert all(stream.closed for stream in streams)


def test_credentialed_redirect_rejected(public_env, monkeypatch):
    calls, _ = install_network(
        monkeypatch,
        [
            [
                b"HTTP/1.1 302 Found\r\nLocation: https://user:secret@jobs.example/\r\n"
                b"Content-Length: 0\r\n\r\n"
            ]
        ],
    )
    with pytest.raises(safefetch.FetchError, match="credentials"):
        safefetch.fetch_html("https://jobs.example/")
    assert len([call for call in calls if call[0] == "connect"]) == 1
