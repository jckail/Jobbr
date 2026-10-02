"""Regression tests for correctness findings from the independent review."""

from datetime import datetime, timedelta

from sqlmodel import Session, select

from jobbr import db, extract
from jobbr import matching as matching_mod
from jobbr.models import Job, RemotePolicy, utcnow
from jobbr.parsing import parse_date
from jobbr.schemas import JobExtraction
from tests.conftest import API, reset_settings
from tests.test_units import make_job, make_profile

POSTING = "Platform Engineer\n- Run Kubernetes clusters\nRemote. $100k - $120k. 5+ years."


def add_text_job(client, text=POSTING, **body):
    r = client.post(f"{API}/jobs", json={"text": text, "company": "Foo", **body})
    assert r.status_code == 201, r.text
    return r.json()


def test_stats_counts_jobs_from_earlier_on_the_first_day(client):
    job = add_text_job(client)
    first_day = (utcnow() - timedelta(days=13)).replace(hour=0, minute=0, second=1, microsecond=0)
    with Session(db.get_engine()) as s:
        row = s.exec(select(Job).where(Job.id == job["id"])).one()
        row.first_seen_at = first_day
        s.add(row)
        s.commit()
    days = client.get(f"{API}/stats").json()["added_per_day"]
    assert days[0] == {"day": first_day.date().isoformat(), "count": 1}


def test_parse_date_converts_offsets_to_utc():
    assert parse_date("2026-01-05T23:00:00-08:00") == datetime(2026, 1, 6, 7, 0)
    assert parse_date("2026-01-05T23:00:00Z") == datetime(2026, 1, 5, 23, 0)
    assert parse_date("2026-01-05") == datetime(2026, 1, 5)
    assert parse_date("not a date") is None


def test_blank_profile_locations_do_not_match_every_job():
    job = make_job(remote_policy=RemotePolicy.onsite, locations=["Austin, TX"])
    profile = make_profile(remote_pref=RemotePolicy.onsite, locations=["", " , x"])
    assert matching_mod.score(job, profile).breakdown["location"]["score"] == 70  # neutral


def test_non_usd_pay_is_not_compared_to_a_usd_floor():
    profile = make_profile(min_comp=200_000)
    usd = make_job(comp_min=80_000, comp_max=100_000, comp_currency="USD")
    eur = make_job(comp_min=80_000, comp_max=100_000, comp_currency="EUR")
    assert matching_mod.score(usd, profile).breakdown["comp"]["score"] < 50
    assert matching_mod.score(eur, profile).breakdown["comp"]["score"] == 50


def test_patch_rejects_inverted_pay_instead_of_rewriting_it(client):
    job = add_text_job(client)
    assert (job["comp_min"], job["comp_max"]) == (100_000, 120_000)
    response = client.patch(f"{API}/jobs/{job['id']}", json={"comp_min": 150_000})
    assert response.status_code == 422
    kept = client.get(f"{API}/jobs/{job['id']}").json()
    assert (kept["comp_min"], kept["comp_max"]) == (100_000, 120_000)
    ok = client.patch(f"{API}/jobs/{job['id']}", json={"comp_min": 90_000, "comp_max": 130_000})
    assert ok.status_code == 200
    assert (ok.json()["comp_min"], ok.json()["comp_max"]) == (90_000, 130_000)


def test_patch_rejects_blank_title(client):
    job = add_text_job(client)
    assert client.patch(f"{API}/jobs/{job['id']}", json={"title": ""}).status_code == 422
    assert client.get(f"{API}/jobs/{job['id']}").json()["title"] == job["title"]


def test_failed_ai_never_replaces_saved_details(client, env):
    env.setenv("JOBBR_OPENAI_API_KEY", "sk-test")
    reset_settings()
    good = JobExtraction(company="LLMCo", title="Good Title", skills=["python"])
    env.setattr(extract, "llm_extract", lambda text, hint=None: (good, 10, 5))
    job = add_text_job(client, url="https://example.com/jobs/1", company=None)
    assert job["title"] == "Good Title"

    def down(text, hint=None):
        raise RuntimeError("provider down")

    env.setattr(extract, "llm_extract", down)

    # Explicit re-extract: refuse and say so, keep the saved details.
    response = client.post(f"{API}/jobs/{job['id']}/reextract")
    assert response.status_code == 422
    assert "left unchanged" in response.json()["detail"]

    # Re-saving the same URL with changed text must not downgrade it either.
    again = add_text_job(client, text=POSTING + "\nmore", url="https://example.com/jobs/1")
    assert again["id"] == job["id"]
    assert again["title"] == "Good Title"

    detail = client.get(f"{API}/jobs/{job['id']}").json()
    assert detail["title"] == "Good Title"
    failed = [e for e in detail["extractions"] if e["error"]]
    assert len(failed) == 2
    assert all(e["ok"] is False for e in failed)
    assert detail["extractions"][-1]["ok"] is True  # the original successful extraction


def test_reextract_keeps_the_content_hash_of_the_full_text(client):
    job = add_text_job(
        client, text=POSTING + "\n" + "detail " * 5000
    )  # longer than the stored text
    before = client.get(f"{API}/jobs/{job['id']}").json()["content_hash"]
    assert client.post(f"{API}/jobs/{job['id']}/reextract").status_code == 200
    assert client.get(f"{API}/jobs/{job['id']}").json()["content_hash"] == before
