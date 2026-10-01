"""Relational model.

Company 1─* Job 1─* Extraction      (how a job's data was produced: cost, latency, method)
Job 1─1 Application 1─* ApplicationEvent   (pipeline + audit trail)
Job *─1 Profile via Match           (fit score + breakdown, recomputable)
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import NaiveDatetime
from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class RemotePolicy(str, Enum):
    remote = "remote"
    hybrid = "hybrid"
    onsite = "onsite"
    unknown = "unknown"


class JobStatus(str, Enum):
    active = "active"
    closed = "closed"
    unknown = "unknown"


class Seniority(str, Enum):
    intern = "intern"
    junior = "junior"
    mid = "mid"
    senior = "senior"
    staff = "staff"
    principal = "principal"
    manager = "manager"
    director = "director"
    executive = "executive"
    unknown = "unknown"


class Stage(str, Enum):
    saved = "saved"
    applied = "applied"
    screen = "screen"
    interview = "interview"
    offer = "offer"
    rejected = "rejected"
    withdrawn = "withdrawn"


class ExtractMethod(str, Enum):
    llm = "llm"
    jsonld = "jsonld"  # schema.org/JobPosting found in the page
    heuristic = "heuristic"


class Company(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    domain: str | None = None
    industry: str | None = None
    created_at: NaiveDatetime = Field(default_factory=utcnow)


class Job(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id", index=True)
    url: str | None = Field(default=None, index=True)
    title: str
    status: JobStatus = JobStatus.active
    department: str | None = None
    seniority: Seniority = Seniority.unknown
    employment_type: str | None = None
    remote_policy: RemotePolicy = RemotePolicy.unknown
    locations: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    comp_min: int | None = None  # annualised, whole currency units
    comp_max: int | None = None
    comp_currency: str = "USD"
    years_experience_min: int | None = None
    summary: str | None = None
    responsibilities: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    qualifications: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    skills: list[str] = Field(default_factory=list, sa_column=Column(JSON))  # required
    nice_to_have: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    benefits: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    ai_take: str | None = None  # one-line "who thrives here / watch outs"
    posted_at: NaiveDatetime | None = None
    content_hash: str | None = None
    raw_text: str | None = None
    first_seen_at: NaiveDatetime = Field(default_factory=utcnow)
    last_seen_at: NaiveDatetime = Field(default_factory=utcnow)


class Extraction(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    job_id: int | None = Field(default=None, foreign_key="job.id", index=True)
    url: str | None = None
    method: ExtractMethod
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    ok: bool = True
    error: str | None = None
    created_at: NaiveDatetime = Field(default_factory=utcnow)


class Profile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = "Me"
    headline: str | None = None
    resume_text: str = ""
    skills: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    years_experience: int | None = None
    seniority: Seniority = Seniority.unknown
    target_titles: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    locations: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    remote_pref: RemotePolicy = RemotePolicy.unknown  # unknown = no preference
    min_comp: int | None = None
    updated_at: NaiveDatetime = Field(default_factory=utcnow)


class Match(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("job_id", "profile_id"),)
    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", index=True)
    profile_id: int = Field(foreign_key="profile.id", index=True)
    score: int  # 0..100
    breakdown: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    matched_skills: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    missing_skills: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    rationale: str | None = None
    created_at: NaiveDatetime = Field(default_factory=utcnow)


class Application(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", unique=True, index=True)
    stage: Stage = Stage.saved
    notes: str = ""
    applied_at: NaiveDatetime | None = None
    next_step_at: NaiveDatetime | None = None
    updated_at: NaiveDatetime = Field(default_factory=utcnow)


class ApplicationEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    application_id: int = Field(foreign_key="application.id", index=True)
    from_stage: Stage | None = None
    to_stage: Stage
    note: str | None = None
    at: NaiveDatetime = Field(default_factory=utcnow)
