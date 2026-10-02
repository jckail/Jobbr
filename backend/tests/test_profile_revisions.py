from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier

from alembic import command
from alembic.config import Config
from sqlalchemy import select as sa_select
from sqlmodel import Session, select

from jobbr import config, db, services
from jobbr.models import Company, Job, Match, Profile, ProfileRevision, ProfileRevisionHead
from jobbr.schemas import ProfileIn
from migrations.store_baseline import metadata as store_schema
from tests.conftest import API


def private_history(client, env):
    env.setenv("JOBBR_API_TOKEN", "revision-test-token")
    config.get_settings.cache_clear()
    client.headers["X-Jobbr-Token"] = "revision-test-token"


def save(client, profile):
    response = client.put(f"{API}/profile", json=profile)
    assert response.status_code == 200, response.text
    return response.json()


def test_explicit_save_restore_preserves_ids_and_re_scores(client, env):
    private_history(client, env)
    first = save(client, {"resume_text": "Python", "target_titles": ["Engineer"]})
    with Session(db.get_engine()) as session:
        company = Company(name="Revision employer")
        session.add(company)
        session.flush()
        job = Job(company_id=company.id, title="Engineer", skills=["Python"])
        session.add(job)
        session.flush()
        match = services.rematch(session, job)
        session.commit()
        job_id, first_score = job.id, match.score
    second = save(
        client,
        {
            "resume_text": "Excel",
            "target_titles": ["Analyst"],
            "expected_revision": first["revision_version"],
        },
    )
    assert second["id"] == first["id"]
    listing = client.get(f"{API}/profile/revisions").json()
    assert len(listing) == 3  # Initial empty snapshot plus two accepted saves.
    detail = client.get(f"{API}/profile/revisions/{first['active_revision_id']}").json()
    assert detail["snapshot"]["resume_text"] == "Python"
    assert "expected_revision" not in detail["snapshot"]
    restored = client.post(
        f"{API}/profile/revisions/{first['active_revision_id']}/activate",
        json={"expected_revision": second["revision_version"]},
    )
    assert restored.status_code == 200, restored.text
    result = restored.json()
    assert result["id"] == first["id"]
    assert result["resume_text"] == "Python"
    assert result["target_titles"] == ["Engineer"]
    with Session(db.get_engine()) as session:
        match = session.exec(select(Match).where(Match.job_id == job_id)).one()
        assert match.score == first_score
    assert len(client.get(f"{API}/profile/revisions").json()) == 3


def test_stale_identical_save_aba_and_deletion_are_rejected(client, env):
    private_history(client, env)
    first = save(client, {"resume_text": "Python"})
    identical = save(
        client, {"resume_text": "Python", "expected_revision": first["revision_version"]}
    )
    assert identical == first
    second = save(client, {"resume_text": "SQL", "expected_revision": first["revision_version"]})
    activated = client.post(
        f"{API}/profile/revisions/{first['active_revision_id']}/activate",
        json={"expected_revision": second["revision_version"]},
    ).json()
    stale = client.put(
        f"{API}/profile",
        json={"resume_text": "Python", "expected_revision": first["revision_version"]},
    )
    assert stale.status_code == 409
    active_id = activated["active_revision_id"]
    assert (
        client.delete(
            f"{API}/profile/revisions/{active_id}",
            params={"expected_revision": activated["revision_version"]},
        ).status_code
        == 409
    )
    inactive_id = second["active_revision_id"]
    assert (
        client.delete(
            f"{API}/profile/revisions/{inactive_id}",
            params={"expected_revision": first["revision_version"]},
        ).status_code
        == 409
    )
    assert (
        client.delete(
            f"{API}/profile/revisions/{inactive_id}",
            params={"expected_revision": activated["revision_version"]},
        ).status_code
        == 204
    )
    assert client.get(f"{API}/profile/revisions/{inactive_id}").status_code == 404
    assert client.get(f"{API}/profile").json()["revision_version"] > activated["revision_version"]


def test_history_requires_private_access_even_on_public_demo(client, env):
    first = save(client, {"resume_text": "Private resume"})
    assert client.get(f"{API}/profile/revisions").status_code == 401
    assert client.get(f"{API}/profile/revisions/{first['active_revision_id']}").status_code == 401
    private_history(client, env)
    assert client.get(f"{API}/profile/revisions").status_code == 200
    client.headers["X-Jobbr-Token"] = "wrong"
    assert client.get(f"{API}/profile/revisions").status_code == 401


def test_revision_ownership_and_payload_bounds(client, env):
    private_history(client, env)
    first = save(client, {"resume_text": "Python"})
    with Session(db.get_engine()) as session:
        other = Profile(name="Other owner")
        session.add(other)
        session.flush()
        row = ProfileRevision(
            profile_id=other.id, snapshot={"resume_text": "Other secret"}, fingerprint="other"
        )
        session.add(row)
        session.commit()
        other_id = row.id
    assert client.get(f"{API}/profile/revisions/{other_id}").status_code == 404
    assert (
        client.post(
            f"{API}/profile/revisions/{other_id}/activate",
            json={"expected_revision": first["revision_version"]},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"{API}/profile/revisions/{other_id}",
            params={"expected_revision": first["revision_version"]},
        ).status_code
        == 404
    )
    assert client.put(f"{API}/profile", json={"skills": ["x"] * 101}).status_code == 422
    assert client.get(f"{API}/profile").json() == first


def concurrent_revision_saves():
    engine = db.get_engine()
    with Session(engine) as session:
        first = services.save_profile(session, ProfileIn(resume_text="Baseline"))
        token = services.profile_output(session, first)["revision_version"]
    barrier = Barrier(2)

    def write(text):
        with Session(engine) as session:
            services.get_profile(session)  # Both writers have observed the same active profile.
            barrier.wait(timeout=3)
            try:
                services.save_profile(session, ProfileIn(resume_text=text, expected_revision=token))
            except services.RevisionConflict:
                return "conflict"
            return "saved"

    with ThreadPoolExecutor(max_workers=2) as workers:
        result = list(workers.map(write, ("Python", "SQL")))
    assert sorted(result) == ["conflict", "saved"]
    with Session(engine) as session:
        assert len(session.exec(select(ProfileRevision)).all()) == 3
        assert session.exec(select(ProfileRevisionHead)).one().version == token + 1


def test_concurrent_revision_save_serializes_expected_check(env):
    db.init_db()
    concurrent_revision_saves()


def test_capacity_never_silently_evicts_and_identical_save_still_works(client, env):
    private_history(client, env)
    first = save(client, {"resume_text": "Python"})
    with Session(db.get_engine()) as session:
        for index in range(48):
            session.add(
                ProfileRevision(
                    profile_id=first["id"],
                    snapshot={"resume_text": str(index)},
                    fingerprint=f"unused-{index}",
                )
            )
        session.commit()
    assert save(client, {"resume_text": "Python"}) == first
    assert client.put(f"{API}/profile", json={"resume_text": "SQL"}).status_code == 422
    listing = client.get(f"{API}/profile/revisions").json()
    assert len(listing) == 50
    inactive = next(row for row in listing if not row["active"])
    assert (
        client.delete(
            f"{API}/profile/revisions/{inactive['id']}",
            params={"expected_revision": first["revision_version"]},
        ).status_code
        == 204
    )
    save(client, {"resume_text": "SQL"})
    assert len(client.get(f"{API}/profile/revisions").json()) == 50


def test_migration_backfills_honest_legacy_snapshot_without_changing_profile(env):
    configuration = Config()
    configuration.set_main_option("script_location", "migrations")
    with db.get_engine().begin() as connection:
        configuration.attributes["connection"] = connection
        command.upgrade(configuration, "0003_auth_store")
        profile = store_schema.tables["profile"]
        connection.execute(
            profile.insert().values(
                id=7,
                name="Existing",
                headline=None,
                resume_text="Python legacy",
                skills=["Python"],
                years_experience=8,
                seniority="senior",
                target_titles=["Engineer"],
                locations=["Seattle"],
                remote_pref="remote",
                min_comp=120000,
                updated_at=datetime(2020, 1, 1),
            )
        )
        original = dict(connection.execute(sa_select(profile)).mappings().one())
    db.init_db()
    with Session(db.get_engine()) as session:
        current = session.get(Profile, 7)
        assert current is not None
        row = session.exec(select(ProfileRevision)).one()
        head = session.exec(select(ProfileRevisionHead)).one()
        assert row.source == "legacy"
        assert row.saved_at > original["updated_at"]
        assert row.snapshot == {
            key: value for key, value in original.items() if key not in ("id", "updated_at")
        }
        assert current.updated_at == original["updated_at"]
        assert head.profile_id == 7
        assert head.active_revision_id == row.id
        assert head.version == 0
    db.init_db()
    with Session(db.get_engine()) as session:
        assert len(session.exec(select(ProfileRevision)).all()) == 1


def test_profile_response_refreshes_stale_identity_and_matching_revision(env):
    db.init_db()
    with Session(db.get_engine()) as first:
        owner = services.save_profile(first, ProfileIn(resume_text="Before"))
        before = services.profile_output(first, owner)
        # Populate the identity map before a different request changes both content and head.
        first.refresh(owner)
        first.get(ProfileRevisionHead, owner.id)
        with Session(db.get_engine()) as writer:
            changed = services.save_profile(
                writer, ProfileIn(resume_text="After", expected_revision=before["revision_version"])
            )
            after = services.profile_output(writer, changed)
        assert owner.resume_text == "Before"
        response = services.profile_output(first, owner)
        assert response == after
        assert response["resume_text"] == "After"
        assert response["revision_version"] == before["revision_version"] + 1


def test_full_length_multibyte_resume_remains_accepted(client, env):
    private_history(client, env)
    text = "界" * 60_000
    profile = save(client, {"resume_text": text})
    detail = client.get(f"{API}/profile/revisions/{profile['active_revision_id']}").json()
    assert detail["snapshot"]["resume_text"] == text


def test_snapshot_byte_budget_failure_is_actionable_and_preserves_profile(client, env):
    private_history(client, env)
    first = save(client, {"resume_text": "Python"})
    # Exercise the independent UTF8 budget; normal bounded inputs fit the configured1MiB.
    env.setattr(services, "MAX_PROFILE_SNAPSHOT_BYTES", 1024)
    response = client.put(f"{API}/profile", json={"resume_text": "界" * 1000})
    assert response.status_code == 422
    assert "snapshot exceeds" in response.json()["detail"]
    assert client.get(f"{API}/profile").json() == first


def test_deleted_newest_revision_id_is_never_reused(client, env):
    private_history(client, env)
    first = save(client, {"resume_text": "Python"})
    newest = save(client, {"resume_text": "SQL"})
    activated = client.post(
        f"{API}/profile/revisions/{first['active_revision_id']}/activate",
        json={"expected_revision": newest["revision_version"]},
    )
    assert activated.status_code == 200, activated.text
    deleted_id = newest["active_revision_id"]
    deleted = client.delete(
        f"{API}/profile/revisions/{deleted_id}",
        params={"expected_revision": activated.json()["revision_version"]},
    )
    assert deleted.status_code == 204
    replacement = save(client, {"resume_text": "Excel"})
    assert replacement["active_revision_id"] > deleted_id
    assert client.get(f"{API}/profile/revisions/{deleted_id}").status_code == 404
