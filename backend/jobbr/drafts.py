"""Explicitly saved, private career drafts; submitted claims remain unverified."""

import hashlib
import json
from datetime import datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, update
from sqlmodel import Session, col, select

from .career import CareerKind
from .models import Job, Profile, SavedCareerDraft, pk

MAX_SAVED_DRAFTS = 50
ShortText = Annotated[str, Field(max_length=2000)]
Evidence = Annotated[str, Field(max_length=1000)]


class SavedInterviewQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(max_length=2000)
    answer_outline: list[ShortText] = Field(max_length=12)
    evidence_quotes: list[Evidence] = Field(max_length=20)


class SavedContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cover_letter: str | None = Field(max_length=12_000)
    interview_questions: list[SavedInterviewQuestion] = Field(max_length=8)
    strengths: list[ShortText] = Field(max_length=20)
    gaps: list[ShortText] = Field(max_length=20)
    questions_to_ask: list[ShortText] = Field(max_length=20)
    evidence_quotes: list[Evidence] = Field(max_length=20)
    review_notes: list[ShortText] = Field(max_length=20)


class SavedResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: CareerKind
    model: str = Field(min_length=1, max_length=200)
    draft: SavedContent
    input_tokens: int = Field(default=0, ge=0, le=10_000_000)
    output_tokens: int = Field(default=0, ge=0, le=10_000_000)
    requires_review: Literal[True] = True
    generated_at: datetime | None = None


class DraftSave(BaseModel):
    model_config = ConfigDict(extra="forbid")
    result: SavedResult

    @model_validator(mode="after")
    def bounded_payload(self) -> Self:
        if len(self.model_dump_json().encode()) > 65_536:
            raise ValueError("Saved draft content must be 64 KiB or smaller.")
        if self.result.kind == "cover_letter":
            if not (self.result.draft.cover_letter or "").strip():
                raise ValueError("Provide a cover letter to save.")
            if self.result.draft.interview_questions:
                raise ValueError("Cover letters cannot contain interview questions.")
        elif (
            self.result.draft.cover_letter is not None or not self.result.draft.interview_questions
        ):
            raise ValueError("Provide interview questions without a cover letter.")
        return self


class DraftLimitError(ValueError):
    """The owner must choose which draft to delete before saving another."""


def fingerprint(job: Job, profile: Profile, company: str) -> str:
    source = {
        "job": job.model_dump(mode="json", exclude={"id", "first_seen_at", "last_seen_at"}),
        "company": company,
        "profile": profile.model_dump(
            mode="json",
            include={"name", "headline", "resume_text", "skills", "years_experience", "seniority"},
        ),
    }
    return hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()


def rows(s: Session, job_id: int, profile_id: int) -> list[SavedCareerDraft]:
    statement = (
        select(SavedCareerDraft)
        .where(SavedCareerDraft.job_id == job_id, SavedCareerDraft.profile_id == profile_id)
        .order_by(col(SavedCareerDraft.created_at).desc(), col(SavedCareerDraft.id).desc())
        .limit(MAX_SAVED_DRAFTS)
    )
    return list(s.exec(statement).all())


def find(s: Session, job_id: int, profile_id: int, draft_id: int) -> SavedCareerDraft | None:
    return s.exec(
        select(SavedCareerDraft).where(
            SavedCareerDraft.id == draft_id,
            SavedCareerDraft.job_id == job_id,
            SavedCareerDraft.profile_id == profile_id,
        )
    ).first()


def save(s: Session, job: Job, profile: Profile, company: str, body: DraftSave) -> SavedCareerDraft:
    # A no-op owner-row write serializes the capacity check on both SQLite and PostgreSQL.
    s.execute(
        update(Profile)
        .where(col(Profile.id) == pk(profile))
        .values(updated_at=col(Profile.updated_at))
    )
    count = s.exec(
        select(func.count())
        .select_from(SavedCareerDraft)
        .where(SavedCareerDraft.job_id == pk(job), SavedCareerDraft.profile_id == pk(profile))
    ).one()
    if count >= MAX_SAVED_DRAFTS:
        raise DraftLimitError("This job has 50 saved drafts. Delete a draft before saving another.")
    row = SavedCareerDraft(
        job_id=pk(job),
        profile_id=pk(profile),
        result=body.result.model_dump(mode="json"),
        source_fingerprint=fingerprint(job, profile, company),
    )
    s.add(row)
    s.commit()
    s.refresh(row)
    return row


def output(row: SavedCareerDraft) -> dict[str, Any]:
    return row.model_dump(exclude={"profile_id"})
