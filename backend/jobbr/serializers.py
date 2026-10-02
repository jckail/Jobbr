"""Row → JSON-ready dicts for the API."""

from typing import Any

from .models import Profile, ProfileRevision, ProfileRevisionHead, SavedTailoringDraft, Stage, pk
from .repo import JobRow

Json = dict[str, Any]


def job_out(row: JobRow, detail: bool = False) -> Json:
    d = row.job.model_dump(exclude=None if detail else {"raw_text"})
    d["external_identity"] = (
        {
            "provider": row.identity.provider,
            "board": row.identity.board,
            "posting_id": row.identity.posting_id,
        }
        if row.identity
        else None
    )
    d["company"] = row.company.model_dump(include={"id", "name", "domain", "industry"})
    d["match"] = row.match.model_dump(exclude={"id", "job_id", "profile_id"}) if row.match else None
    d["application"] = (
        row.application.model_dump(exclude={"id", "job_id"})
        if row.application
        else {"stage": Stage.saved, "notes": ""}
    )
    return d


def profile_out(profile: Profile, head: ProfileRevisionHead) -> Json:
    return {
        **profile.model_dump(mode="json"),
        "active_revision_id": head.active_revision_id,
        "revision_version": head.version,
    }


def profile_revision_out(row: ProfileRevision, active_id: int, detail: bool = False) -> Json:
    result: Json = {
        "id": pk(row),
        "saved_at": row.saved_at.isoformat(),
        "source": row.source,
        "active": pk(row) == active_id,
    }
    if detail:
        result["snapshot"] = row.snapshot
    return result


def tailoring_draft_out(row: SavedTailoringDraft) -> Json:
    return {
        "id": pk(row),
        "created_at": row.created_at.isoformat(),
        "receipt_id": row.receipt_id,
        "kind": "resume_tailoring",
        "requires_review": True,
        "user_edited": row.user_edited,
        "draft": row.draft,
        **{key: value for key, value in row.provenance.items() if key != "prompt_version"},
    }
