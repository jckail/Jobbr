import pytest

from jobbr import parsing, safefetch
from jobbr.skills import find_skills

LD = """<html><head><script type="application/ld+json">
{"@type":"JobPosting","title":"Senior Data Engineer","hiringOrganization":{"name":"Acme"},
 "description":"<p>Build pipelines</p><ul><li>Own Airflow DAGs</li></ul> You know Python, SQL and Kafka.",
 "jobLocationType":"TELECOMMUTE","baseSalary":{"currency":"USD","value":{"minValue":90,"maxValue":120,"unitText":"HOUR"}},
 "datePosted":"2026-09-01"}</script></head><body><main>Senior Data Engineer at Acme. Remote. Python SQL Kafka pipelines every day for our platform team.</main></body></html>"""


def test_skill_scan():
    assert {"python", "kubernetes", "react", "go"} <= set(find_skills("Python, Go, k8s and React.js"))
    assert "go" not in find_skills("we go further than anyone")


def test_jsonld_extraction_annualises_pay():
    j = parsing.jsonld_job(LD)
    assert j.company == "Acme" and j.remote_policy.value == "remote"
    assert (j.comp_min, j.comp_max) == (90 * 2080, 120 * 2080)
    assert "kafka" in j.skills


def test_ssrf_guard_blocks_private(monkeypatch):
    from jobbr import config
    monkeypatch.setenv("JOBBR_ALLOW_PRIVATE_FETCH", "0")
    config.get_settings.cache_clear()
    with pytest.raises(safefetch.FetchError):
        safefetch.assert_public_url("http://127.0.0.1:8000/x")
    with pytest.raises(safefetch.FetchError):
        safefetch.assert_public_url("file:///etc/passwd")
    config.get_settings.cache_clear()


def test_end_to_end_pipeline(client, monkeypatch):
    monkeypatch.setattr("jobbr.services.fetch_html", lambda url: (url, LD))
    r = client.put("/jobbr/api/profile", json={"resume_text": "Python, SQL, Airflow", "seniority": "senior",
                                                "remote_pref": "remote"})
    assert r.status_code == 200 and "airflow" in r.json()["skills"]
    r = client.post("/jobbr/api/jobs", json={"url": "https://acme.test/jobs/1"})
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["company"]["name"] == "Acme" and job["match"]["score"] > 50
    assert "kafka" in job["match"]["missing_skills"]
    # dedupe by URL
    client.post("/jobbr/api/jobs", json={"url": "https://acme.test/jobs/1"})
    assert len(client.get("/jobbr/api/jobs").json()) == 1
    # pipeline
    a = client.put(f"/jobbr/api/jobs/{job['id']}/application", json={"stage": "applied"}).json()
    assert a["application"]["stage"] == "applied"
    d = client.get(f"/jobbr/api/jobs/{job['id']}").json()
    assert [e["to_stage"] for e in d["events"]] == ["applied", "saved"]
    # profile change recomputes scores
    client.put("/jobbr/api/profile", json={"resume_text": "Python SQL Kafka Airflow", "seniority": "senior"})
    assert client.get(f"/jobbr/api/jobs/{job['id']}").json()["match"]["missing_skills"] == []
    s = client.get("/jobbr/api/stats").json()
    assert s["totals"]["jobs"] == 1 and s["stages"]["applied"] == 1
    assert client.delete(f"/jobbr/api/jobs/{job['id']}").status_code == 204
    assert client.get("/jobbr/api/jobs").json() == []


def test_paste_text_and_validation(client):
    r = client.post("/jobbr/api/jobs", json={"text": "Platform Engineer\n- Run Kubernetes clusters\n- Terraform, AWS\nRemote. $150k - $190k. 5+ years.",
                                              "company": "Foo"})
    assert r.status_code == 201
    j = r.json()
    assert (j["comp_min"], j["comp_max"], j["years_experience_min"]) == (150000, 190000, 5)
    assert client.post("/jobbr/api/jobs", json={}).status_code == 422


def test_token_protects_writes(client, monkeypatch):
    from jobbr import config
    monkeypatch.setenv("JOBBR_API_TOKEN", "s3cret")
    config.get_settings.cache_clear()
    assert client.post("/jobbr/api/jobs", json={"text": "x" * 100}).status_code == 401
    assert client.get("/jobbr/api/jobs").status_code == 200
    ok = client.post("/jobbr/api/jobs", json={"text": "Engineer\n" + "Python " * 30}, headers={"X-Jobbr-Token": "s3cret"})
    assert ok.status_code == 201
    config.get_settings.cache_clear()
