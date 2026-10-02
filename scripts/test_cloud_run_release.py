"""Offline release regression checks; subprocesses are mocked, never authenticated."""

import ast
import contextlib
import copy
import io
import json
import os
import subprocess
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github/workflows/deploy-cloud-run.yml"
)
ACCOUNT = "jobbr-runtime@portfolio-383615.iam.gserviceaccount.com"
CONNECTION = "portfolio-383615:us-central1:jobbr-pg"
IMAGE = "us-central1-docker.pkg.dev/portfolio-383615/jobbr/jobbr@sha256:" + "a" * 64
REVISION = "jobbr-release-123-1"
ENV = {
    "GCP_PROJECT": "portfolio-383615",
    "GCP_REGION": "us-central1",
    "JOBBR_RUNTIME_SERVICE_ACCOUNT": ACCOUNT,
    "JOBBR_DATABASE_SECRET_REF": "jobbr-database-url:1",
    "JOBBR_API_TOKEN_SECRET_REF": "jobbr-instance-token:2",
    "JOBBR_AUTH_STORE_SECRET_REF": "jobbr-auth-store-key:3",
    "GITHUB_RUN_ID": "123",
    "GITHUB_RUN_ATTEMPT": "1",
    "DEPLOY_IMAGE": IMAGE,
}


def embedded(name):
    step = WORKFLOW.read_text().split("      - name: " + name + "\n", 1)[1]
    source = step.split("          python - <<'PY'\n", 1)[1].split("\n          PY", 1)[
        0
    ]
    return compile(textwrap.dedent(source), str(WORKFLOW) + ":" + name, "exec")


def container():
    entries = [
        {"name": "JOBBR_PRIVATE_INSTANCE", "value": "true"},
        {"name": "JOBBR_SEED_DEMO", "value": "false"},
        {"name": "JOBBR_OPENAI_AUTH_ENABLED", "value": "false"},
    ]
    for variable, reference in (
        ("JOBBR_DATABASE_URL", ENV["JOBBR_DATABASE_SECRET_REF"]),
        ("JOBBR_API_TOKEN", ENV["JOBBR_API_TOKEN_SECRET_REF"]),
        ("JOBBR_OPENAI_STORE_KEY", ENV["JOBBR_AUTH_STORE_SECRET_REF"]),
    ):
        name, version = reference.split(":")
        entries.append(
            {
                "name": variable,
                "valueFrom": {"secretKeyRef": {"name": name, "key": version}},
            }
        )
    return {
        "image": IMAGE,
        "env": entries,
        "startupProbe": {"httpGet": {"path": "/healthz", "port": 8000}},
    }


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.service = {"spec": {"template": {"spec": {"containers": [container()]}}}}
        self.revision = {
            "metadata": {
                "name": REVISION,
                "annotations": {"run.googleapis.com/cloudsql-instances": CONNECTION},
            },
            "spec": {"serviceAccountName": ACCOUNT, "containers": [container()]},
            "status": {"conditions": [{"type": "Ready", "status": "True"}]},
        }
        self.returned_revision = REVISION

    def command(self, args, **_kwargs):
        self.calls.append(args)
        operation = args[1:4]
        if operation == ["run", "services", "describe"]:
            value = json.dumps(self.service)
        elif operation == ["run", "services", "update"]:
            self.assertIn("--revision-suffix=release-123-1", args)
            self.assertIn("--no-traffic", args)
            self.assertIn("--deploy-health-check", args)
            value = self.returned_revision
        elif operation == ["run", "revisions", "describe"]:
            self.assertEqual(args[4], REVISION)
            value = json.dumps(self.revision)
        elif operation == ["run", "services", "update-traffic"]:
            self.assertIn("--to-revisions=" + REVISION + "=100", args)
            value = ""
        elif args[1:3] == ["iam", "service-accounts"]:
            value = ACCOUNT
        elif args[1:3] == ["sql", "instances"]:
            value = json.dumps({"state": "RUNNABLE", "connectionName": CONNECTION})
        elif args[1:3] == ["artifacts", "repositories"]:
            value = json.dumps({"format": "DOCKER", "mode": "STANDARD_REPOSITORY"})
        elif args[1:3] == ["secrets", "versions"]:
            self.assertIn("describe", args)
            value = "ENABLED"
        else:
            self.fail("Unexpected subprocess attempted: " + repr(args[:4]))
        return subprocess.CompletedProcess(args, 0, value, "")

    def execute(self, name, extra_env=None):
        with (
            patch.dict(os.environ, ENV | (extra_env or {}), clear=True),
            patch("subprocess.run", side_effect=self.command),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            # Execute the reviewed local workflow with every subprocess mocked.
            exec(embedded(name), {})  # noqa: S102

    def assert_no_promotion(self):
        self.assertFalse(
            any(
                args[1:4] == ["run", "services", "update-traffic"]
                for args in self.calls
            )
        )

    def test_expected_existing_service_passes(self):
        self.execute(
            "Verify existing dedicated resources and enabled pinned secret versions"
        )
        self.assertEqual(len(self.calls), 7)
        self.assert_no_promotion()

    def test_existing_authentication_and_probe_changes_are_rejected(self):
        original = copy.deepcopy(self.service)
        cases = [
            "oauth",
            "public",
            "demo",
            "missing-auth",
            "tcp-probe",
            "wrong-path",
            "duplicate",
        ]
        for case in cases:
            with self.subTest(case=case):
                self.service = copy.deepcopy(original)
                target = self.service["spec"]["template"]["spec"]["containers"][0]
                if case in ("oauth", "public", "demo"):
                    index = {"public": 0, "demo": 1, "oauth": 2}[case]
                    target["env"][index]["value"] = (
                        "false" if case == "public" else "true"
                    )
                elif case == "missing-auth":
                    del target["env"][2]
                elif case == "tcp-probe":
                    target["startupProbe"] = {"tcpSocket": {"port": 8000}}
                elif case == "wrong-path":
                    target["startupProbe"]["httpGet"]["path"] = "/"
                else:
                    target["env"].append(copy.deepcopy(target["env"][2]))
                self.calls.clear()
                with self.assertRaises(SystemExit):
                    self.execute(
                        "Verify existing dedicated resources and enabled pinned secret versions"
                    )
                self.assertEqual(len(self.calls), 1)
                self.assert_no_promotion()

    def test_exact_ready_revision_is_promoted(self):
        self.execute(
            "Update only the existing Jobbr service with pinned image and secret references"
        )
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(self.calls[-1][1:4], ["run", "services", "update-traffic"])

    def test_concurrent_wrong_revision_is_never_promoted(self):
        self.returned_revision = "jobbr-other-updater"
        with self.assertRaises(SystemExit):
            self.execute(
                "Update only the existing Jobbr service with pinned image and secret references"
            )
        self.assertEqual(len(self.calls), 1)
        self.assert_no_promotion()

    def test_revision_configuration_mismatches_are_never_promoted(self):
        original = copy.deepcopy(self.revision)
        cases = [
            "name",
            "not-ready",
            "image",
            "identity",
            "sql",
            "oauth",
            "secret-name",
            "secret-version",
            "plain-secret",
            "probe",
            "duplicate",
        ]
        for case in cases:
            with self.subTest(case=case):
                self.revision = copy.deepcopy(original)
                target = self.revision["spec"]["containers"][0]
                if case == "name":
                    self.revision["metadata"]["name"] = "jobbr-other-updater"
                elif case == "not-ready":
                    self.revision["status"]["conditions"][0]["status"] = "False"
                elif case == "image":
                    target["image"] = IMAGE.replace("a" * 64, "b" * 64)
                elif case == "identity":
                    self.revision["spec"]["serviceAccountName"] = "other@example.test"
                elif case == "sql":
                    self.revision["metadata"]["annotations"][
                        "run.googleapis.com/cloudsql-instances"
                    ] += ",other"
                elif case == "oauth":
                    target["env"][2]["value"] = "true"
                elif case.startswith("secret-"):
                    key = "name" if case == "secret-name" else "key"
                    target["env"][3]["valueFrom"]["secretKeyRef"][key] = (
                        "other" if key == "name" else "latest"
                    )
                elif case == "plain-secret":
                    target["env"][3] = {
                        "name": "JOBBR_DATABASE_URL",
                        "value": "not-a-real-credential",
                    }
                elif case == "probe":
                    target["startupProbe"] = {"tcpSocket": {"port": 8000}}
                else:
                    target["env"].append(copy.deepcopy(target["env"][0]))
                self.calls.clear()
                with self.assertRaises(SystemExit):
                    self.execute(
                        "Update only the existing Jobbr service with pinned image and secret references"
                    )
                self.assert_no_promotion()

    def test_invalid_revision_identity_does_not_update_service(self):
        with self.assertRaises(SystemExit):
            self.execute(
                "Update only the existing Jobbr service with pinned image and secret references",
                {"GITHUB_RUN_ID": "1;echo injected"},
            )
        self.assertEqual(self.calls, [])

    def test_all_embedded_python_compiles(self):
        for block in WORKFLOW.read_text().split("          python - <<'PY'\n")[1:]:
            ast.parse(textwrap.dedent(block.split("\n          PY", 1)[0]))


if __name__ == "__main__":
    unittest.main()
