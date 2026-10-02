"""Identity certainty, legacy ambiguity and metadata lease fencing."""

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from jobbr import canonical_repo as repo
from jobbr.canonical import Identity, identity_for_url, job_baseline, resource_key
from jobbr.canonical_models import CaptureLease, JobExternalIdentity
from jobbr.models import Company, Job, pk


@pytest.mark.parametrize(
    "url",
    [
        "http://boards.greenhouse.io/Acme/jobs/12",
        "https://boards.greenhouse.io.attacker.test/Acme/jobs/12",
        "https://owner@boards.greenhouse.io/Acme/jobs/12",
        "https://boards.greenhouse.io:8443/Acme/jobs/12",
        "https://boards.greenhouse.io/Acme%2Fother/jobs/12",
        "https://boards.greenhouse.io/Acme/jobs/12/",
        "https://boards.greenhouse.io/Acme/jobs/../12",
        "https://boards.greenhouse.io/Acme/jobs/12\n",
        "https://boards.greenhouse.io\\@evil.test/Acme/jobs/12",
        "https://jobs.lever.co/Acme/not-a-posting-id",
    ],
)
def test_untrusted_or_ambiguous_urls_do_not_assert_identity(url):
    assert identity_for_url(url) is None


def test_recognized_aliases_ignore_query_and_fragment_but_preserve_case():
    a = "https://boards.greenhouse.io/Acme/jobs/123?source=one#application"
    b = "https://job-boards.greenhouse.io/Acme/jobs/123?source=two"
    assert identity_for_url(a) == Identity("greenhouse", "Acme", "123")
    assert resource_key(a) == resource_key(b)
    assert resource_key(a) != resource_key(b.replace("Acme", "acme"))
    lever = "https://jobs.lever.co/Acme/ABCDEF12-1234-1234-1234-123456789abc"
    assert identity_for_url(lever).posting_id == "ABCDEF12-1234-1234-1234-123456789abc"
    assert resource_key("https://custom.test/job?x=1") != resource_key(
        "https://custom.test/job?x=2"
    )
    assert resource_key(None) is None


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        company = Company(name="Fixture")
        s.add(company)
        s.commit()
        yield s
    engine.dispose()


def add_job(s, url):
    job = Job(company_id=1, url=url, title="Engineer", raw_text="Posting")
    s.add(job)
    s.commit()
    return job


def test_lazy_adoption_preserves_urls_and_does_not_merge_duplicates(session):
    job = add_job(session, "https://boards.greenhouse.io/Acme/jobs/12?old=1")
    identity = Identity("greenhouse", "Acme", "12")
    assert repo.resolve_identity(session, identity).id == job.id
    session.commit()
    assert job.url.endswith("?old=1")
    assert len(session.exec(select(JobExternalIdentity)).all()) == 1
    duplicate = add_job(session, "https://job-boards.greenhouse.io/Other/jobs/99")
    add_job(session, "https://boards.greenhouse.io/Other/jobs/99?alias=1")
    with pytest.raises(repo.CanonicalConflict, match="Multiple saved jobs"):
        repo.resolve_identity(session, Identity("greenhouse", "Other", "99"))
    assert len(session.exec(select(Job)).all()) == 3
    assert duplicate.title == "Engineer"


def test_legacy_scan_overflow_and_mapping_conflict_are_explicit(session):
    job = add_job(session, "https://boards.greenhouse.io/Acme/jobs/12")
    other = add_job(session, "https://job-boards.greenhouse.io/Acme/jobs/12?variant=1")
    identity = Identity("greenhouse", "Acme", "12")
    with pytest.raises(repo.CanonicalConflict, match="too large"):
        repo.resolve_identity(session, identity, scan_limit=1)
    repo.attach_identity(session, identity, job)
    with pytest.raises(repo.CanonicalConflict, match="another saved job"):
        repo.attach_identity(session, identity, other)


def test_expiry_takeover_fences_old_worker_and_cleanup(session):
    key = "a" * 64
    first = repo.reserve(session, key, "first", 300, None, None, now=0)
    session.commit()
    assert first.nonce == "first"
    with pytest.raises(repo.CanonicalConflict) as error:
        repo.reserve(session, key, "second", 400, None, None, now=100)
    assert error.value.retry_after == 200
    session.rollback()
    repo.reserve(session, key, "second", 601, None, None, now=301)
    session.commit()
    assert repo.release(session, key, "first") is False
    with pytest.raises(repo.CanonicalConflict, match="expired or changed"):
        repo.check(session, key, "first", now=302)
    assert repo.check(session, key, "second", now=302).nonce == "second"
    assert repo.release(session, key, "second") is True


def test_modified_job_fences_completion_and_job_cleanup(session):
    job = add_job(session, "https://example.test/posting")
    repo.reserve(session, "a" * 64, "worker", 300, pk(job), job_baseline(job), now=0)
    repo.attach_identity(session, Identity("greenhouse", "Acme", "12"), job)
    session.commit()
    job.title = "Edited during capture"
    session.add(job)
    session.commit()
    with pytest.raises(repo.CanonicalConflict, match="changed during capture"):
        repo.check(session, "a" * 64, "worker", now=1)
    repo.delete_job_refs(session, pk(job))
    session.commit()
    assert session.exec(select(CaptureLease)).all() == []
    assert session.exec(select(JobExternalIdentity)).all() == []
    assert session.get(Job, pk(job)).title == "Edited during capture"


def test_lease_cap_has_no_silent_eviction(session, monkeypatch):
    monkeypatch.setattr(repo, "MAX_LEASES", 1)
    repo.reserve(session, "a" * 64, "one", 300, None, None, now=0)
    session.commit()
    with pytest.raises(repo.CanonicalConflict, match="temporarily full"):
        repo.reserve(session, "b" * 64, "two", 300, None, None, now=0)
    assert repo.lease(session, "a" * 64).nonce == "one"


@pytest.mark.parametrize("port", [":0443", ":00443", ":4430", ":", ":+443"])
def test_noncanonical_port_spelling_never_asserts_identity(port):
    assert identity_for_url(f"https://boards.greenhouse.io{port}/Acme/jobs/12") is None


def test_explicit_canonical_port_is_found_in_legacy_lookup(session):
    job = add_job(session, "https://BOARDS.GREENHOUSE.IO:443/Acme/jobs/12?source=old")
    assert repo.resolve_identity(session, Identity("greenhouse", "Acme", "12")).id == job.id


def test_unrelated_jobs_and_underscore_wildcards_do_not_consume_candidate_limit(session):
    # If '_' were a LIKE wildcard, these unrelated board URLs would overflow the lookup.
    session.add_all(
        [
            Job(
                company_id=1,
                url=f"https://boards.greenhouse.io/AxB/jobs/12?other={i}",
                title="Other board",
            )
            for i in range(1001)
        ]
    )
    session.add_all(
        [
            Job(
                company_id=1,
                url=f"https://boards.greenhouse.io/A_B/jobs/{i + 100}",
                title="Other posting",
            )
            for i in range(1001)
        ]
    )
    session.commit()
    job = add_job(session, "https://job-boards.greenhouse.io/A_B/jobs/12#application")
    assert repo.resolve_identity(session, Identity("greenhouse", "A_B", "12")).id == job.id
    assert repo.resolve_identity(session, Identity("greenhouse", "NewBoard", "1")) is None


@pytest.mark.parametrize(("board", "posting"), [("a" * 81, "12"), ("Acme", "1" * 33)])
def test_identity_components_are_bounded(board, posting):
    assert identity_for_url(f"https://boards.greenhouse.io/{board}/jobs/{posting}") is None
