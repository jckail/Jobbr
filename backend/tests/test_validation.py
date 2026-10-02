import json

import pytest
from pydantic import ValidationError

from jobbr import parsing, safefetch
from jobbr.models import ExtractMethod
from jobbr.schemas import JobCreate, JobExtraction, JobPatch, ProfileIn
from tests.conftest import API


@pytest.mark.parametrize("field", ["title", "skills", "remote_policy"])
def test_patch_rejects_null_required_fields(client, field):
    response = client.patch(f"{API}/jobs/1", json={field: None})
    assert response.status_code == 422


def test_patch_keeps_omission_and_nullable_clearing():
    assert JobPatch().model_dump(exclude_unset=True) == {}
    assert JobPatch(comp_min=None, comp_max=None, summary=None).model_dump(exclude_unset=True) == {
        "comp_min": None,
        "comp_max": None,
        "summary": None,
    }


@pytest.mark.parametrize(
    ("schema", "field", "maximum"),
    [
        (JobPatch, "comp_min", 1_000_000_000),
        (JobPatch, "comp_max", 1_000_000_000),
        (ProfileIn, "min_comp", 1_000_000_000),
        (ProfileIn, "years_experience", 100),
        (JobExtraction, "comp_min", 1_000_000_000),
        (JobExtraction, "comp_max", 1_000_000_000),
        (JobExtraction, "years_experience_min", 100),
    ],
)
def test_numeric_fields_reject_out_of_range_values(schema, field, maximum):
    defaults = {"title": "Engineer", "company": "Acme"} if schema is JobExtraction else {}
    for value in (-1, maximum + 1, 9223372036854775808):
        with pytest.raises(ValidationError):
            schema(**defaults, **{field: value})
    assert getattr(schema(**defaults, **{field: maximum}), field) == maximum
    assert getattr(schema(**defaults, **{field: 0}), field) == 0


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "file:///tmp/posting",
        "https://user:password@example.com/job",
        "https://user@example.com/job",
        "https://example.com:bad/job",
        "https://example.com:0/job",
        "https://example.com/job\n",
        "https://example.com/a b",
        "https://example.com\\@evil.example/job",
        "https:///job",
    ],
)
def test_pasted_posting_rejects_invalid_urls(client, url):
    response = client.post(f"{API}/jobs", json={"text": "Engineer Python", "url": url})
    assert response.status_code == 422


def test_pasted_public_url_does_not_resolve_dns(client, monkeypatch):
    def fail_dns(*args, **kwargs):
        pytest.fail("Pasted postings must not resolve DNS")

    monkeypatch.setattr(safefetch, "resolve_addresses", fail_dns)
    response = client.post(
        f"{API}/jobs",
        json={"text": "Engineer Python", "url": "https://example.invalid/job", "company": "Acme"},
    )
    assert response.status_code == 201
    assert response.json()["url"] == "https://example.invalid/job"


@pytest.mark.parametrize(
    "metadata",
    [
        {"@graph": None},
        {"@type": "JobPosting", "description": {"invalid": True}},
        {"@type": "JobPosting", "description": ["not", "a", "string"]},
        {"@type": "JobPosting", "baseSalary": {"value": {"minValue": "Competitive"}}},
        {"@type": "JobPosting", "baseSalary": {"value": {"minValue": "Infinity"}}},
        {"@type": "JobPosting", "baseSalary": {"value": {"minValue": 1e100}}},
    ],
)
def test_malformed_jsonld_falls_back_to_posting_text(client, monkeypatch, metadata):
    html = (
        '<script type="application/ld+json">'
        + json.dumps(metadata)
        + "</script><main>Platform Engineer. Remote role requiring Python and SQL. "
        + "Build reliable services and collaborate with our engineering team.</main>"
    )
    monkeypatch.setattr("jobbr.services.fetch_html", lambda url: (url, html))
    response = client.post(f"{API}/jobs", json={"url": "https://example.com/job"})
    assert response.status_code == 201
    detail = client.get(f"{API}/jobs/{response.json()['id']}").json()
    assert detail["extractions"][0]["method"] == ExtractMethod.heuristic
    assert "python" in detail["skills"]


def test_malformed_jsonld_block_does_not_hide_valid_block():
    data = [
        {"@type": "JobPosting", "title": "Engineer", "hiringOrganization": {"name": "Acme"}},
        {"@type": "JobPosting", "baseSalary": {"value": {"minValue": "Competitive"}}},
    ]
    result = parsing.jsonld_job(
        '<script type="application/ld+json">' + json.dumps(data) + "</script>"
    )
    assert result is not None
    assert result.title == "Engineer"


def test_deep_jsonld_is_ignored():
    html = '<script type="application/ld+json">' + "[" * 1500 + "0" + "]" * 1500 + "</script>"
    assert parsing.jsonld_job(html) is None


def test_zero_salary_preserved():
    data = {"@type": "JobPosting", "baseSalary": {"value": {"minValue": 0, "maxValue": 100}}}
    result = parsing.jsonld_job(
        '<script type="application/ld+json">' + json.dumps(data) + "</script>"
    )
    assert result is not None
    assert (result.comp_min, result.comp_max) == (0, 100)


def test_job_url_limits_length():
    with pytest.raises(ValidationError):
        JobCreate(url="https://example.com/" + "a" * 8192)
