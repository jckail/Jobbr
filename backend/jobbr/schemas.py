from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, NaiveDatetime, field_validator

from .models import RemotePolicy, Seniority, Stage


class JobExtraction(BaseModel):
    """What the extractor (LLM, JSON-LD or heuristic) returns for one posting."""

    company: str = Field(description="Hiring company name")
    title: str = Field(description="Job title without team name or location")
    department: str | None = Field(default=None, description="Team or department")
    seniority: Seniority = Seniority.unknown
    employment_type: str | None = Field(default=None, description="e.g. Full-time, Contract")
    remote_policy: RemotePolicy = RemotePolicy.unknown
    locations: list[str] = Field(default_factory=list, description="'City, State' strings")
    comp_min: int | None = Field(
        default=None,
        ge=0,
        le=1_000_000_000,
        description="Annual minimum base pay in whole currency units",
    )
    comp_max: int | None = Field(
        default=None,
        ge=0,
        le=1_000_000_000,
        description="Annual maximum base pay in whole currency units",
    )
    comp_currency: str = "USD"
    years_experience_min: int | None = Field(default=None, ge=0, le=100)
    summary: str | None = Field(default=None, description="<=280 chars: what this role is")
    responsibilities: list[str] = Field(default_factory=list, description="<=8 short bullets")
    qualifications: list[str] = Field(default_factory=list, description="<=8 short bullets")
    skills: list[str] = Field(
        default_factory=list, description="Required technical skills, lowercase canonical names"
    )
    nice_to_have: list[str] = Field(default_factory=list, description="Preferred skills")
    benefits: list[str] = Field(default_factory=list)
    ai_take: str | None = Field(
        default=None, description="<=160 chars: who would thrive, and any red flags"
    )
    posted_at: str | None = Field(default=None, description="ISO date if stated")
    industry: str | None = None


class JobCreate(BaseModel):
    url: str | None = Field(default=None, max_length=8192)
    text: str | None = Field(
        default=None,
        max_length=60_000,
        description="Pasted posting text (use when a page needs JS or login)",
    )
    company: str | None = None
    title: str | None = None

    @field_validator("url")
    @classmethod
    def valid_posting_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Provide a valid HTTP or HTTPS posting URL.")
        value = value.strip()
        if not value or "\\" in value or " " in value:
            raise ValueError("Provide a valid HTTP or HTTPS posting URL.")
        try:
            parsed = urlsplit(value)
            invalid = (
                parsed.scheme not in ("http", "https")
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or "@" in parsed.netloc
                or (parsed.port is not None and not 1 <= parsed.port <= 65535)
            )
        except ValueError as exc:
            raise ValueError("Provide an HTTP or HTTPS URL without credentials.") from exc
        if invalid:
            raise ValueError("Provide an HTTP or HTTPS URL without credentials.")
        return value


class JobPatch(BaseModel):
    title: str | None = None
    company: str | None = None
    remote_policy: RemotePolicy | None = None
    comp_min: int | None = Field(default=None, ge=0, le=1_000_000_000)
    comp_max: int | None = Field(default=None, ge=0, le=1_000_000_000)
    skills: list[str] | None = None
    summary: str | None = None

    @field_validator("title", "skills", "remote_policy")
    @classmethod
    def required_when_present(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("This field cannot be null; omit it to leave it unchanged.")
        return value


class ProfileIn(BaseModel):
    name: str = Field(default="Me", max_length=200)
    headline: str | None = Field(default=None, max_length=300)
    resume_text: str = Field(default="", max_length=60_000)
    skills: list[str] | None = None  # None = derive from resume
    years_experience: int | None = Field(default=None, ge=0, le=100)
    seniority: Seniority = Seniority.unknown
    target_titles: list[str] = []
    locations: list[str] = []
    remote_pref: RemotePolicy = RemotePolicy.unknown
    min_comp: int | None = Field(default=None, ge=0, le=1_000_000_000)


class ApplicationIn(BaseModel):
    stage: Stage | None = None
    notes: str | None = Field(default=None, max_length=10_000)
    next_step_at: NaiveDatetime | None = None
    note: str | None = Field(default=None, max_length=2000)  # attached to the stage-change event


class MatchOut(BaseModel):
    score: int
    breakdown: dict[str, Any]
    matched_skills: list[str]
    missing_skills: list[str]
    rationale: str | None
