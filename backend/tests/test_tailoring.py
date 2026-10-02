import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from jobbr import config, db, services, tailoring
from jobbr.main import create_app
from jobbr.models import (
    Company,
    Job,
    ProfileRevision,
    SavedTailoringDraft,
    TailoringReceipt,
    utcnow,
)
from jobbr.schemas import ProfileIn
from tests.conftest import API, reset_settings
from tests.test_backup import backup, source_path

DRAFT = {
    "resume_text": "Python engineer building reliable pipelines.",
    "changes": [{"description": "Emphasized pipeline experience", "evidence_quotes": ["Python"]}],
    "gaps": ["No evidence of AWS certification"],
    "review_notes": ["Review every claim. Matching quotes do not certify all claims."],
}


def setup_tailoring(client, env, provider="openai"):
    env.setenv("JOBBR_API_TOKEN", "tailoring-test-token")
    env.setenv("JOBBR_AI_PROVIDER", provider)
    env.setenv("JOBBR_OPENAI_API_KEY", "offline-openai")
    env.setenv("JOBBR_ANTHROPIC_API_KEY", "offline-anthropic")
    config.get_settings.cache_clear()
    client.headers["X-Jobbr-Token"] = "tailoring-test-token"
    first = client.put(
        f"{API}/profile",
        json={
            "name": "Candidate",
            "resume_text": "Python pipelines",
            "headline": "Engineer",
            "target_titles": ["Engineer"],
        },
    ).json()
    with Session(db.get_engine()) as session:
        company = Company(name="Tailoring employer")
        session.add(company)
        session.flush()
        job = Job(
            company_id=company.id,
            title="Python Engineer",
            skills=["Python"],
            raw_text="Python engineering position",
        )
        session.add(job)
        session.commit()
        job_id = job.id
    calls = []

    async def structured(name, instructions, content, output_type, *, settings):
        calls.append((json.loads(content), settings.ai_provider, settings.ai_model))
        return output_type.model_validate(deepcopy(DRAFT)), 20, 30

    env.setattr(tailoring, "run_structured", structured)
    return first, job_id, calls


def generate(client, job_id, revision_id):
    response = client.post(
        f"{API}/jobs/{job_id}/tailoring", json={"source_revision_id": revision_id}
    )
    assert response.status_code == 200, response.text
    return response.json()


def save_generated(client, job_id, result, draft=None):
    response = client.post(
        f"{API}/jobs/{job_id}/tailoring/drafts",
        json={
            "receipt_id": result["receipt_id"],
            "draft": draft or result["draft"],
            "review_acknowledged": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_generated_a_saved_after_b_preserves_provenance_and_acceptance_is_separate(
    client, env, provider
):
    first, job_id, calls = setup_tailoring(client, env, provider)
    result = generate(client, job_id, first["active_revision_id"])
    assert calls[0][0]["profile"]["resume_text"] == "Python pipelines"
    assert calls[0][1] == provider
    assert result["provider"] == provider
    assert result["model"] == calls[0][2]
    assert client.get(f"{API}/jobs/{job_id}/tailoring/drafts").json() == []
    current = client.put(
        f"{API}/profile",
        json={
            "name": "Current owner",
            "resume_text": "SQL analytics",
            "headline": "Analyst",
            "years_experience": 9,
            "target_titles": ["Analyst"],
            "locations": ["Seattle"],
            "remote_pref": "remote",
            "min_comp": 150000,
            "expected_revision": first["revision_version"],
        },
    ).json()
    # Job edits/provider switches after generation cannot relabel the stored original inputs.
    with Session(db.get_engine()) as session:
        job = session.get(Job, job_id)
        job.title = "Changed role"
        session.add(job)
        session.commit()
    env.setenv("JOBBR_AI_PROVIDER", "anthropic" if provider == "openai" else "openai")
    config.get_settings.cache_clear()
    edited = deepcopy(result["draft"])
    edited["resume_text"] = "Reviewed Python engineer building reliable pipelines."
    saved = save_generated(client, job_id, result, edited)
    assert saved["source"] == result["source"]
    assert saved["provider"] == provider
    assert saved["model"] == result["model"]
    assert saved["generated_at"] == result["generated_at"]
    assert saved["input_tokens"] == 20
    assert saved["output_tokens"] == 30
    assert saved["user_edited"] is True
    assert saved["requires_review"] is True
    assert client.get(f"{API}/profile").json() == current
    stale = client.post(
        f"{API}/jobs/{job_id}/tailoring/drafts/{saved['id']}/accept",
        json={
            "expected_revision": first["revision_version"],
            "review_acknowledged": True,
        },
    )
    assert stale.status_code == 409
    assert client.get(f"{API}/profile").json() == current
    accepted = client.post(
        f"{API}/jobs/{job_id}/tailoring/drafts/{saved['id']}/accept",
        json={
            "expected_revision": current["revision_version"],
            "review_acknowledged": True,
        },
    )
    assert accepted.status_code == 200, accepted.text
    profile = accepted.json()
    assert profile["resume_text"] == edited["resume_text"]
    assert "python" in profile["skills"]
    assert profile["revision_version"] == current["revision_version"] + 1
    for field in (
        "id",
        "name",
        "headline",
        "years_experience",
        "target_titles",
        "locations",
        "remote_pref",
        "min_comp",
    ):
        assert profile[field] == current[field]
    assert client.get(f"{API}/jobs/{job_id}/tailoring/drafts/{saved['id']}").json() == saved


def source_capture_saved_during_active_change(env):
    env.setenv("JOBBR_OPENAI_API_KEY", "offline-key")
    config.get_settings.cache_clear()
    with Session(db.get_engine()) as session:
        owner = services.save_profile(session, ProfileIn(resume_text="Python original"))
        state = services.profile_output(session, owner)
        company = Company(name="Original employer")
        session.add(company)
        session.flush()
        job = Job(company_id=company.id, title="Original role")
        session.add(job)
        session.commit()
        job_id = job.id
        session.rollback()

        async def structured(name, instructions, content, output_type, *, settings):
            assert not session.in_transaction()
            payload = json.loads(content)
            assert payload["profile"]["resume_text"] == "Python original"
            assert settings.ai_provider == "openai"
            env.setenv("JOBBR_AI_PROVIDER", "anthropic")
            config.get_settings.cache_clear()
            with Session(db.get_engine()) as other:
                services.save_profile(
                    other,
                    ProfileIn(
                        resume_text="SQL replacement", expected_revision=state["revision_version"]
                    ),
                )
            return output_type.model_validate(DRAFT), 1, 2

        env.setattr(tailoring, "run_structured", structured)
        result = asyncio.run(
            services.generate_tailoring(session, job_id, state["active_revision_id"])
        )
        assert result.provider == "openai"
        assert services.get_profile(session).resume_text == "SQL replacement"
        current = services.profile_output(session, services.get_profile(session))
        saved = services.save_tailoring(
            session,
            job_id,
            tailoring.TailoringSave(
                receipt_id=result.receipt_id,
                draft=result.draft,
                review_acknowledged=True,
            ),
        )
        assert saved.provenance["source"] == result.source.model_dump()
        assert saved.provenance["provider"] == "openai"
        assert services.profile_output(session, services.get_profile(session)) == current

        saved_id = saved.id
        with pytest.raises(services.RevisionConflict):
            services.accept_tailoring(session, job_id, saved_id, state["revision_version"])
        session.rollback()
        assert services.profile_output(session, services.get_profile(session)) == current
        accepted = services.accept_tailoring(session, job_id, saved_id, current["revision_version"])
        assert accepted["resume_text"] == DRAFT["resume_text"]
        assert accepted["revision_version"] == current["revision_version"] + 1
        assert accepted["id"] == state["id"]
        return (
            state["id"],
            job_id,
            state["active_revision_id"],
            result.receipt_id,
            result.draft.model_dump(),
        )


def test_source_capture_releases_transaction_and_settings_are_fixed_across_await(env):
    db.init_db()
    source_capture_saved_during_active_change(env)


def test_receipts_contain_only_private_metadata_and_expiry_does_not_invalidate_saved_draft(
    client, env
):
    first, job_id, _ = setup_tailoring(client, env)
    result = generate(client, job_id, first["active_revision_id"])
    saved = save_generated(client, job_id, result)
    with Session(db.get_engine()) as session:
        receipt = session.exec(select(TailoringReceipt)).one()
        metadata = json.dumps(receipt.model_dump(mode="json"))
        assert "Python pipelines" not in metadata
        assert DRAFT["resume_text"] not in metadata
        assert "Python engineering position" not in metadata
        assert "offline-openai" not in metadata
        receipt.expires_at = utcnow() - timedelta(seconds=1)
        session.add(receipt)
        session.commit()
    expired = client.post(
        f"{API}/jobs/{job_id}/tailoring/drafts",
        json={
            "receipt_id": result["receipt_id"],
            "draft": result["draft"],
            "review_acknowledged": True,
        },
    )
    assert expired.status_code == 410
    assert client.get(f"{API}/jobs/{job_id}/tailoring/drafts/{saved['id']}").json() == saved
    response = client.post(
        f"{API}/jobs/{job_id}/tailoring/drafts/{saved['id']}/accept",
        json={
            "expected_revision": first["revision_version"],
            "review_acknowledged": True,
        },
    )
    assert response.status_code == 200


def test_source_deletion_before_save_invalidates_receipt_and_saved_reference_blocks_deletion(
    client, env
):
    first, job_id, _ = setup_tailoring(client, env)
    result = generate(client, job_id, first["active_revision_id"])
    current = client.put(f"{API}/profile", json={"resume_text": "SQL current"}).json()
    saved = save_generated(client, job_id, result)
    path = f"{API}/profile/revisions/{first['active_revision_id']}"
    assert (
        client.delete(path, params={"expected_revision": current["revision_version"]}).status_code
        == 409
    )
    assert client.delete(f"{API}/jobs/{job_id}/tailoring/drafts/{saved['id']}").status_code == 204
    assert (
        client.delete(path, params={"expected_revision": current["revision_version"]}).status_code
        == 204
    )
    rejected = client.post(
        f"{API}/jobs/{job_id}/tailoring/drafts",
        json={
            "receipt_id": result["receipt_id"],
            "draft": result["draft"],
            "review_acknowledged": True,
        },
    )
    assert rejected.status_code == 409


def test_source_deleted_during_generation_returns_conflict_and_cleans_pending_metadata(client, env):
    first, job_id, _ = setup_tailoring(client, env)
    current = client.put(f"{API}/profile", json={"resume_text": "SQL current"}).json()

    async def delete_source(name, instructions, content, output_type, *, settings):
        with Session(db.get_engine()) as other:
            services.delete_revision(
                other,
                services.get_profile(other),
                first["active_revision_id"],
                current["revision_version"],
            )
        return output_type.model_validate(DRAFT), 1, 2

    env.setattr(tailoring, "run_structured", delete_source)
    response = client.post(
        f"{API}/jobs/{job_id}/tailoring",
        json={
            "source_revision_id": first["active_revision_id"],
        },
    )
    assert response.status_code == 409
    with Session(db.get_engine()) as session:
        assert session.exec(select(TailoringReceipt)).all() == []
        assert session.exec(select(SavedTailoringDraft)).all() == []


@pytest.mark.parametrize(
    "failure", ["cancel", "timeout", "private_exception", "fabricated_quote", "bad_usage"]
)
def test_failed_or_cancelled_generation_never_persists_prose_or_receipts(client, env, failure):
    first, job_id, _ = setup_tailoring(client, env)

    async def fail(name, instructions, content, output_type, *, settings):
        if failure == "cancel":
            raise asyncio.CancelledError
        if failure == "timeout":
            raise TimeoutError
        if failure == "private_exception":
            raise RuntimeError("private resume and provider secret must never appear")
        result = deepcopy(DRAFT)
        if failure == "fabricated_quote":
            result["changes"][0]["evidence_quotes"] = ["AWS certification"]
        return output_type.model_validate(result), True if failure == "bad_usage" else 1, 2

    env.setattr(tailoring, "run_structured", fail)
    if failure == "cancel":
        with Session(db.get_engine()) as session, pytest.raises(asyncio.CancelledError):
            asyncio.run(services.generate_tailoring(session, job_id, first["active_revision_id"]))
    else:
        response = client.post(
            f"{API}/jobs/{job_id}/tailoring",
            json={"source_revision_id": first["active_revision_id"]},
        )
        assert response.status_code == 502
        assert "private resume" not in response.text
        assert "provider secret" not in response.text
    with Session(db.get_engine()) as session:
        assert session.exec(select(TailoringReceipt)).all() == []
        assert session.exec(select(SavedTailoringDraft)).all() == []
    assert client.get(f"{API}/profile").json() == first


def test_private_gate_selection_pin_payload_and_job_receipt_scope(client, env):
    first, job_id, calls = setup_tailoring(client, env)
    client.headers["X-Jobbr-Token"] = "wrong"
    assert (
        client.post(
            f"{API}/jobs/{job_id}/tailoring",
            json={"source_revision_id": first["active_revision_id"]},
        ).status_code
        == 401
    )
    assert client.get(f"{API}/jobs/{job_id}/tailoring/drafts").status_code == 401
    client.headers["X-Jobbr-Token"] = "tailoring-test-token"
    assert (
        client.post(
            f"{API}/jobs/{job_id}/tailoring",
            json={"source_revision_id": first["active_revision_id"]},
            headers={
                "X-Jobbr-AI-Provider": "anthropic",
                "X-Jobbr-AI-Model": "wrong",
                "X-Jobbr-AI-Enabled": "true",
            },
        ).status_code
        == 409
    )
    assert calls == []
    result = generate(client, job_id, first["active_revision_id"])
    body = {
        "receipt_id": result["receipt_id"],
        "draft": result["draft"],
        "review_acknowledged": True,
    }
    forged = {**body, "source": result["source"], "provider": "anthropic"}
    assert client.post(f"{API}/jobs/{job_id}/tailoring/drafts", json=forged).status_code == 422
    assert (
        client.post(
            f"{API}/jobs/{job_id}/tailoring/drafts", json={**body, "review_acknowledged": False}
        ).status_code
        == 422
    )
    assert client.post(f"{API}/jobs/{job_id + 1}/tailoring/drafts", json=body).status_code == 410
    unsupported = deepcopy(body)
    unsupported["draft"]["changes"][0]["evidence_quotes"] = ["Invented qualification"]
    assert client.post(f"{API}/jobs/{job_id}/tailoring/drafts", json=unsupported).status_code == 422
    huge = deepcopy(body)
    huge["draft"]["resume_text"] = "x" * 60_001
    assert client.post(f"{API}/jobs/{job_id}/tailoring/drafts", json=huge).status_code == 422
    assert client.get(f"{API}/profile").json() == first


def test_receipt_capacity_is_checked_before_call_and_only_expired_metadata_is_purged(client, env):
    first, job_id, calls = setup_tailoring(client, env)
    with Session(db.get_engine()) as session:
        for index in range(100):
            session.add(
                TailoringReceipt(
                    id=f"pending-{index}",
                    profile_id=first["id"],
                    job_id=job_id,
                    source_revision_id=first["active_revision_id"],
                    provenance={"index": index},
                    expires_at=utcnow() + timedelta(days=1),
                )
            )
        session.commit()
    blocked = client.post(
        f"{API}/jobs/{job_id}/tailoring", json={"source_revision_id": first["active_revision_id"]}
    )
    assert blocked.status_code == 409
    assert calls == []
    with Session(db.get_engine()) as session:
        expired = session.get(TailoringReceipt, "pending-0")
        expired.expires_at = utcnow() - timedelta(seconds=1)
        session.add(expired)
        session.commit()
    generate(client, job_id, first["active_revision_id"])
    with Session(db.get_engine()) as session:
        assert len(session.exec(select(TailoringReceipt)).all()) == 100
        assert session.get(TailoringReceipt, "pending-0") is None
        assert session.get(TailoringReceipt, "pending-1") is not None


def test_complete_input_budget_rejects_without_silent_resume_truncation_or_provider_call(
    client, env
):
    _first, job_id, calls = setup_tailoring(client, env)
    longer = client.put(f"{API}/profile", json={"resume_text": "Python " * 8571}).json()
    blocked = client.post(
        f"{API}/jobs/{job_id}/tailoring", json={"source_revision_id": longer["active_revision_id"]}
    )
    assert blocked.status_code == 422
    assert calls == []
    with Session(db.get_engine()) as session:
        assert session.exec(select(TailoringReceipt)).all() == []
        assert len(session.exec(select(ProfileRevision)).all()) == 3


def test_explicit_job_delete_removes_only_its_tailoring_and_releases_source_reference(client, env):
    first, job_id, _ = setup_tailoring(client, env)
    result = generate(client, job_id, first["active_revision_id"])
    save_generated(client, job_id, result)
    with Session(db.get_engine()) as session:
        first_job = session.get(Job, job_id)
        other = Job(company_id=first_job.company_id, title="Other job")
        session.add(other)
        session.commit()
        other_id = other.id
    other_result = generate(client, other_id, first["active_revision_id"])
    other_saved = save_generated(client, other_id, other_result)
    assert client.delete(f"{API}/jobs/{job_id}").status_code == 204
    assert (
        client.get(f"{API}/jobs/{other_id}/tailoring/drafts/{other_saved['id']}").status_code == 200
    )
    with Session(db.get_engine()) as session:
        assert [row.job_id for row in session.exec(select(TailoringReceipt)).all()] == [other_id]
        assert [row.job_id for row in session.exec(select(SavedTailoringDraft)).all()] == [other_id]
        assert session.get(ProfileRevision, first["active_revision_id"]) is not None


def test_tailoring_backup_preserves_receipt_draft_and_immutable_source(client, env, tmp_path):
    first, job_id, _ = setup_tailoring(client, env)
    result = generate(client, job_id, first["active_revision_id"])
    saved = save_generated(client, job_id, result)
    history = client.get(f"{API}/profile/revisions").json()
    output = tmp_path / "tailoring-backup.db"
    restored = tmp_path / "tailoring-restored.db"
    backup.snapshot(source_path(), output)
    backup.snapshot(output, restored)
    env.setenv("JOBBR_DATABASE_URL", f"sqlite:///{restored}")
    reset_settings()
    with TestClient(create_app()) as reopened:
        reopened.headers["X-Jobbr-Token"] = "tailoring-test-token"
        assert reopened.get(f"{API}/jobs/{job_id}/tailoring/drafts/{saved['id']}").json() == saved
        assert reopened.get(f"{API}/profile/revisions").json() == history
        response = reopened.post(
            f"{API}/jobs/{job_id}/tailoring/drafts/{saved['id']}/accept",
            json={
                "expected_revision": first["revision_version"],
                "review_acknowledged": True,
            },
        )
        assert response.status_code == 200
        assert response.json()["resume_text"] == DRAFT["resume_text"]
        # Receipt still enables another explicit reviewed save after restart.
        assert save_generated(reopened, job_id, result)["source"] == saved["source"]


def concurrent_tailoring_saves(profile_id, job_id, source_revision_id, receipt_id, draft):
    body = tailoring.TailoringSave(receipt_id=receipt_id, draft=draft, review_acknowledged=True)
    with Session(db.get_engine()) as session:
        original = session.exec(select(SavedTailoringDraft)).one()
        for _ in range(48):
            session.add(
                SavedTailoringDraft(
                    profile_id=profile_id,
                    job_id=job_id,
                    source_revision_id=source_revision_id,
                    receipt_id=receipt_id,
                    provenance=original.provenance,
                    draft=original.draft,
                )
            )
        session.commit()
    barrier = Barrier(2)

    def save():
        with Session(db.get_engine()) as session:
            services.get_profile(session)
            barrier.wait(timeout=3)
            try:
                services.save_tailoring(session, job_id, body)
            except tailoring.TailoringConflict:
                return "full"
            return "saved"

    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(lambda _: save(), range(2)))
    assert sorted(outcomes) == ["full", "saved"]
    with Session(db.get_engine()) as session:
        assert len(session.exec(select(SavedTailoringDraft)).all()) == 50


def test_concurrent_near_capacity_saves_never_exceed_retention(client, env):
    first, job_id, _ = setup_tailoring(client, env)
    result = generate(client, job_id, first["active_revision_id"])
    save_generated(client, job_id, result)
    concurrent_tailoring_saves(
        first["id"], job_id, first["active_revision_id"], result["receipt_id"], result["draft"]
    )
