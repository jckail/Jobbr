"""Public readiness contract against disposable loopback HTTP fixtures."""

import contextlib
import io
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from mcp_readiness import MAX_RESPONSE_BYTES, main, probe

RESOURCE = "https://jobbr.test/jobbr/mcp"
ISSUER = "https://issuer.test"
METADATA = "https://jobbr.test/.well-known/oauth-protected-resource/jobbr/mcp"
DOCUMENT = {
    "resource": RESOURCE,
    "authorization_servers": [ISSUER],
    "scopes_supported": ["jobbr:read"],
}
CHALLENGE = f'Bearer resource_metadata="{METADATA}", scope="jobbr:read"'


@contextlib.contextmanager
def fixture(
    *,
    document=None,
    discovery_status=200,
    content_type="application/json",
    post_status=401,
    challenge=CHALLENGE,
    raw=None,
):
    observed = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            observed.append((self.path, dict(self.headers)))
            self.send_response(discovery_status)
            self.send_header("Content-Type", content_type)
            if discovery_status == 302:
                self.send_header("Location", "/redirected")
            self.end_headers()
            data = json.dumps(DOCUMENT if document is None else document).encode()
            self.wfile.write(raw if raw is not None else data)

        def do_POST(self):
            observed.append((self.path, dict(self.headers)))
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert payload["method"] == "initialize"
            self.send_response(post_status)
            if challenge is not None:
                self.send_header("WWW-Authenticate", challenge)
            self.end_headers()

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/jobbr/mcp", observed
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


class ReadinessTests(unittest.TestCase):
    def test_ready_public_contract_does_not_claim_authentication_or_send_credentials(self):
        with fixture() as (target, observed):
            result = probe(RESOURCE, ISSUER, target=target)
        self.assertEqual(
            result, {"routing_ready": True, "authenticated_flow_checked": False, "failures": []}
        )
        self.assertEqual(
            [path for path, _ in observed],
            ["/.well-known/oauth-protected-resource/jobbr/mcp", "/jobbr/mcp"],
        )
        for _, headers in observed:
            self.assertNotIn("Authorization", headers)
            self.assertNotIn("Cookie", headers)

    def test_spa_success_is_rejected(self):
        with fixture(
            content_type="text/html", raw=b"<html>SPA</html>", post_status=200, challenge=None
        ) as (target, _):
            result = probe(RESOURCE, ISSUER, target=target)
        self.assertFalse(result["routing_ready"])
        self.assertEqual(len(result["failures"]), 3)

    def test_wrong_metadata_identity_and_scopes(self):
        for document in (
            {**DOCUMENT, "resource": "https://another.test/jobbr/mcp"},
            {**DOCUMENT, "authorization_servers": ["https://another-issuer.test"]},
            {**DOCUMENT, "scopes_supported": ["jobbr:read-similar"]},
            [],
        ):
            with self.subTest(document=document), fixture(document=document) as (target, _):
                self.assertFalse(probe(RESOURCE, ISSUER, target=target)["routing_ready"])

    def test_wrong_challenges_are_rejected(self):
        for challenge in (
            None,
            'Bearer scope="jobbr:read"',
            f'Basic resource_metadata="{METADATA}", scope="jobbr:read"',
            f'Bearer resource_metadata="{METADATA}", scope="jobbr:read-similar"',
            'Bearer resource_metadata="https://another.test", scope="jobbr:read"',
            (
                'Bearer resource_metadata="https://wrong.test", '
                f'Basic resource_metadata="{METADATA}", scope="jobbr:read"'
            ),
            (
                'Bearer resource_metadata="https://wrong.test", '
                f'resource_metadata="{METADATA}", scope="jobbr:read"'
            ),
            (
                f'Bearer resource_metadata="{METADATA}", '
                'scope="jobbr:read-similar", scope="jobbr:read"'
            ),
        ):
            with self.subTest(challenge=challenge), fixture(challenge=challenge) as (target, _):
                self.assertFalse(probe(RESOURCE, ISSUER, target=target)["routing_ready"])

    def test_discovery_redirect_is_not_followed(self):
        with fixture(discovery_status=302) as (target, observed):
            self.assertFalse(probe(RESOURCE, ISSUER, target=target)["routing_ready"])
        self.assertEqual(len(observed), 2)

    def test_invalid_or_oversized_discovery_does_not_echo_body(self):
        for body in (b"PRIVATE_CANARY", b"x" * (MAX_RESPONSE_BYTES + 1)):
            with self.subTest(length=len(body)), fixture(raw=body) as (target, _):
                result = probe(RESOURCE, ISSUER, target=target)
            self.assertFalse(result["routing_ready"])
            self.assertNotIn("PRIVATE_CANARY", json.dumps(result))

    def test_bad_input_rejected_before_network(self):
        for resource, issuer, target in (
            ("http://jobbr.test/jobbr/mcp", ISSUER, None),
            ("https://name:secret@jobbr.test/jobbr/mcp", ISSUER, None),
            (RESOURCE + "?token=secret", ISSUER, None),
            (RESOURCE, "http://issuer.test", None),
            (RESOURCE, ISSUER, "http://remote.test/jobbr/mcp"),
            (RESOURCE, ISSUER, "http://127.0.0.1/other"),
            ("https://jobbr.test:bad/jobbr/mcp", ISSUER, None),
        ):
            with self.subTest(resource=resource), patch("urllib.request.build_opener") as opener:
                with self.assertRaises(ValueError):
                    probe(resource, issuer, target=target)
                opener.assert_not_called()

    def test_cli_json_and_exit_status(self):
        for status, expected in ((401, 0), (200, 1)):
            with (
                fixture(post_status=status) as (target, _),
                patch(
                    "sys.argv",
                    [
                        "mcp_readiness",
                        "--resource-url",
                        RESOURCE,
                        "--issuer",
                        ISSUER,
                        "--probe-url",
                        target,
                    ],
                ),
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                self.assertEqual(main(), expected)
                self.assertEqual(json.loads(output.getvalue())["routing_ready"], expected == 0)


if __name__ == "__main__":
    unittest.main()
