"""Exercise a disposable Jobbr instance. Never point this at your real database."""

import json
import os
import time
import urllib.error
import urllib.request

BASE = os.environ.get("JOBBR_SMOKE_URL", "http://127.0.0.1:8000")


def request(path, method="GET", data=None):
    payload = json.dumps(data).encode() if data is not None else None
    headers = {"Content-Type": "application/json"}
    if token := os.environ.get("JOBBR_API_TOKEN"):
        headers["X-Jobbr-Token"] = token
    req = urllib.request.Request(BASE + path, data=payload, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as response:
        content = response.read()
        return response.status, json.loads(content) if content else None


for attempt in range(60):
    try:
        assert request("/healthz")[1] == {"ok": True}
        break
    except (OSError, urllib.error.URLError):
        time.sleep(1)
else:
    raise SystemExit("Jobbr did not become healthy")

with urllib.request.urlopen(BASE + "/jobbr/", timeout=10) as response:
    assert response.status == 200
    assert b'<div id="root">' in response.read()
    assert response.headers.get("X-Content-Type-Options") == "nosniff"

status, job = request("/jobbr/api/jobs", "POST", {
    "title": "Smoke test engineer", "company": "Smoke Test",
    "text": "Smoke test engineer. Python SQL Kubernetes. Remote. Build reliable data pipelines. $150k - $190k.",
})
assert status == 201
job_id = job["id"]
try:
    assert request(f"/jobbr/api/jobs/{job_id}")[1]["company"]["name"] == "Smoke Test"
    _, moved = request(f"/jobbr/api/jobs/{job_id}/application", "PUT", {"stage": "applied"})
    assert moved["application"]["stage"] == "applied"
    assert request("/jobbr/api/stats")[1]["stages"]["applied"] >= 1
    assert request("/jobbr/api/auth/session")[1]["authenticated"] is False
finally:
    assert request(f"/jobbr/api/jobs/{job_id}", "DELETE")[0] == 204
print("Jobbr smoke passed: UI, headers, extraction, application transition, stats, auth readiness.")
