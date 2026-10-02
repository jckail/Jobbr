# Third-party posting fetches

`fetch_html(url)` still returns `(final_url, html)` and raises a sanitized
`FetchError` on failure. Paste text when a site needs login, JavaScript, nonstandard
ports, or unsupported compression.

The fetcher uses the documented HTTPX BaseTransport and httpcore ConnectionPool,
NetworkBackend and NetworkStream interfaces. It resolves each destination once,
rejects the whole DNS answer set if any address is not globally routable or is
multicast, and connects through the backend using only the chosen numeric IP.
The original hostname remains in the request, HTTP Host, TLS SNI and certificate
hostname check. The verified hostname is never resolved again for that connection.
Each redirect, including a redirect to the same hostname, is independently
resolved and validated using a new isolated connection pool. There is no connection
reuse across redirects and no automatic retries.

URLs must use HTTP/HTTPS with a hostname, no userinfo, no control characters or raw
spaces, at most 8192 characters, and only ports 80/443. IDNA Unicode hostnames are
supported; invalid ports, scoped IPv6 addresses and malformed URLs are rejected.
The test-only `JOBBR_ALLOW_PRIVATE_FETCH` switch permits private addresses and other
ports, but still applies syntax validation, DNS pinning and body/time bounds. Leave
that switch disabled in deployed environments.

`trust_env=False` disables proxy configuration from the environment. TLS certificate
verification remains enabled. Responses are streamed with a 3 MB body cap;
Content-Length is checked before reading, and the cumulative body is checked before
each chunk is appended. The client sends `Accept-Encoding: identity` and rejects
nonidentity Content-Encoding before reading the body. It does not decompress data,
which prevents compressed-response expansion bombs but rejects sites that ignore
the identity request. At most five redirects are followed, six requests total.

One monotonic deadline covers the redirect sequence and socket connection, TLS,
write and read operations. Each socket timeout is capped to the remaining budget;
slowly arriving chunks do not reset the budget. Blocking system DNS resolution
cannot be cancelled safely in the synchronous worker: a stuck OS resolver can
exceed the configured timeout before the request is rejected. Deployment DNS
settings and outbound network policy remain useful controls for that limitation.
The code guarantees bounded accumulated body memory, not a hard CPU bound against
all possible HTTP parser inputs. It relies on HTTPX/httpcore's parser limits for
response headers.

Public errors exclude exception strings and requested URLs so query secrets and
upstream details are not echoed. Streams and connection pools are closed on success,
redirect and failure. Tests exercise the real HTTPX/httpcore protocol parser over
mocked network streams: rebinding, private/mixed DNS answers, redirects, actual
connect destination, Host/TLS identity and verification, environment proxies,
streaming and declared-size limits, compression rejection, malformed and
credentialed URLs, Unicode hostname handling, sanitized errors and deadlines.

References: [HTTPX custom transports](https://www.python-httpx.org/advanced/transports/),
[httpcore public network interfaces](https://www.encode.io/httpcore/network-backends/),
and [httpcore extensions](https://www.encode.io/httpcore/extensions/).
