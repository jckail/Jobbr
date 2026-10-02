from fastapi.testclient import TestClient

from jobbr import extract as extract_mod
from jobbr.main import create_app
from jobbr.models import ExtractMethod
from jobbr.schemas import JobExtraction
from tests.conftest import API, reset_settings

POSTING = (
    "Platform Engineer\n- Run Kubernetes clusters\n- Terraform, AWS\n"
    "Remote. $150k - $190k. 5+ years."
)


def add(client: TestClient, **body) -> dict:
    r = client.post(f"{API}/jobs", json=body or {"url": "https://acme.test/jobs/1"})
    assert r.status_code == 201, r.text
    return r.json()


def test_pipeline_end_to_end(client):
    r = client.put(
        f"{API}/profile",
        json={
            "resume_text": "Python, SQL, Airflow",
            "seniority": "senior",
            "remote_pref": "remote",
        },
    )
    assert r.status_code == 200
    assert "airflow" in r.json()["skills"]

    job = add(client)
    assert job["company"]["name"] == "Acme"
    assert job["match"]["score"] > 50
    assert "kafka" in job["match"]["missing_skills"]

    add(client)  # same URL: deduped, not duplicated
    assert len(client.get(f"{API}/jobs").json()) == 1

    moved = client.put(f"{API}/jobs/{job['id']}/application", json={"stage": "applied"}).json()
    assert moved["application"]["stage"] == "applied"
    detail = client.get(f"{API}/jobs/{job['id']}").json()
    assert [e["to_stage"] for e in detail["events"]] == ["applied", "saved"]

    client.put(
        f"{API}/profile", json={"resume_text": "Python SQL Kafka Airflow", "seniority": "senior"}
    )
    assert client.get(f"{API}/jobs/{job['id']}").json()["match"]["missing_skills"] == []

    stats = client.get(f"{API}/stats").json()
    assert stats["totals"]["jobs"] == 1
    assert stats["stages"]["applied"] == 1

    assert client.delete(f"{API}/jobs/{job['id']}").status_code == 204
    assert client.get(f"{API}/jobs").json() == []
    assert client.get(f"{API}/jobs/{job['id']}").status_code == 404


def test_paste_text(client):
    job = add(client, text=POSTING, company="Foo")
    assert (job["comp_min"], job["comp_max"], job["years_experience_min"]) == (150_000, 190_000, 5)
    assert job["company"]["name"] == "Foo"


def test_requires_url_or_text(client):
    assert client.post(f"{API}/jobs", json={}).status_code == 422


def test_filters_and_sort(client):
    add(client, text=POSTING, company="Foo")
    add(client, url="https://acme.test/jobs/1")
    assert len(client.get(f"{API}/jobs", params={"q": "kubernetes"}).json()) == 1
    assert len(client.get(f"{API}/jobs", params={"remote": "remote"}).json()) == 2
    assert client.get(f"{API}/jobs", params={"stage": "offer"}).json() == []
    assert client.get(f"{API}/jobs", params={"sort": "nope"}).status_code == 422
    by_comp = client.get(f"{API}/jobs", params={"sort": "comp"}).json()
    assert by_comp[0]["comp_max"] >= by_comp[1]["comp_max"]


def test_patch_rescores(client):
    client.put(f"{API}/profile", json={"resume_text": "Python"})
    job = add(client, text=POSTING, company="Foo")
    before = job["match"]["score"]
    patched = client.patch(
        f"{API}/jobs/{job['id']}", json={"skills": ["python"], "company": "Bar"}
    ).json()
    assert patched["company"]["name"] == "Bar"
    assert patched["match"]["score"] > before


def test_reextract_logs_a_run(client):
    job = add(client, text=POSTING, company="Foo")
    client.post(f"{API}/jobs/{job['id']}/reextract")
    runs = client.get(f"{API}/jobs/{job['id']}").json()["extractions"]
    assert len(runs) == 2
    assert {r["method"] for r in runs} == {ExtractMethod.heuristic}


def test_token_protects_writes(client, env):
    env.setenv("JOBBR_API_TOKEN", "s3cret")
    reset_settings()
    assert client.post(f"{API}/jobs", json={"text": POSTING}).status_code == 401
    assert client.get(f"{API}/jobs").status_code == 200
    ok = client.post(f"{API}/jobs", json={"text": POSTING}, headers={"X-Jobbr-Token": "s3cret"})
    assert ok.status_code == 201


def test_llm_used_when_key_set_and_falls_back_on_error(client, env):
    env.setenv("JOBBR_OPENAI_API_KEY", "test-key")
    reset_settings()
    fake = JobExtraction(company="LLMCo", title="Wizard", skills=["python"])
    env.setattr(
        extract_mod, "llm_extract", lambda text, hint=None, *, settings=None: (fake, 1000, 200)
    )
    job = add(client, text=POSTING)
    assert job["company"]["name"] == "LLMCo"
    run = client.get(f"{API}/jobs/{job['id']}").json()["extractions"][0]
    assert run["method"] == "llm"
    assert run["input_tokens"] == 1000
    assert run["output_tokens"] == 200
    assert run["model"] == "gpt-4.1-mini"

    def boom(text, hint=None, *, settings=None):
        raise RuntimeError("api down")

    env.setattr(extract_mod, "llm_extract", boom)
    job2 = add(client, text=POSTING + "\nmore", company="Fallback")
    run2 = client.get(f"{API}/jobs/{job2['id']}").json()["extractions"][0]
    assert run2["method"] == "heuristic"
    assert "offline heuristics" in run2["error"]


def test_spa_serving_and_path_traversal(client, env, tmp_path):
    static = tmp_path / "dist"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>spa</html>")
    (tmp_path / "secret.txt").write_text("nope")
    env.setenv("JOBBR_STATIC_DIR", str(static))
    reset_settings()
    with TestClient(create_app()) as c:
        assert "spa" in c.get("/jobbr/jobs/1").text
        assert c.get("/jobbr/api/nope").status_code == 404
        assert "nope" not in c.get("/jobbr/..%2fsecret.txt").text
        assert c.get("/healthz").json() == {"ok": True}
