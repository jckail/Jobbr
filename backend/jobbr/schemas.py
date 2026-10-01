from typing import Any

from pydantic import BaseModel, Field, NaiveDatetime

from .models import RemotePolicy, Seniority, Stage


class JobExtraction(BaseModel):
    """What the extractor (LLM, JSON-LD or heuristic) returns for one posting."""

    company: str = Field(description="Hiring company name")
    title: str = Field(description="Job title without team name or location")
    department: str | None = Field(None, description="Team or department")
    seniority: Seniority = Seniority.unknown
    employment_type: str | None = Field(None, description="e.g. Full-time, Contract")
    remote_policy: RemotePolicy = RemotePolicy.unknown
    locations: list[str] = Field(default_factory=list, description="'City, State' strings")
    comp_min: int | None = Field(None, description="Annual minimum base pay in whole currency units")
    comp_max: int | None = Field(None, description="Annual maximum base pay in whole currency units")
    comp_currency: str = "USD"
    years_experience_min: int | None = None
    summary: str | None = Field(None, description="<=280 chars: what this role is")
    responsibilities: list[str] = Field(default_factory=list, description="<=8 short bullets")
    qualifications: list[str] = Field(default_factory=list, description="<=8 short bullets")
    skills: list[str] = Field(default_factory=list, description="Required technical skills, lowercase canonical names")
    nice_to_have: list[str] = Field(default_factory=list, description="Preferred skills")
    benefits: list[str] = Field(default_factory=list)
    ai_take: str | None = Field(None, description="<=160 chars: who would thrive, and any red flags")
    posted_at: str | None = Field(None, description="ISO date if stated")
    industry: str | None = None


class JobCreate(BaseModel):
    url: str | None = None
    text: str | None = Field(None, description="Pasted posting text (use when a page needs JS or login)")
    company: str | None = None
    title: str | None = None


class JobPatch(BaseModel):
    title: str | None = None
    company: str | None = None
    remote_policy: RemotePolicy | None = None
    comp_min: int | None = None
    comp_max: int | None = None
    skills: list[str] | None = None
    summary: str | None = None


class ProfileIn(BaseModel):
    name: str = "Me"
    headline: str | None = None
    resume_text: str = ""
    skills: list[str] | None = None  # None = derive from resume
    years_experience: int | None = None
    seniority: Seniority = Seniority.unknown
    target_titles: list[str] = []
    locations: list[str] = []
    remote_pref: RemotePolicy = RemotePolicy.unknown
    min_comp: int | None = None


class ApplicationIn(BaseModel):
    stage: Stage | None = None
    notes: str | None = None
    next_step_at: NaiveDatetime | None = None
    note: str | None = None  # attached to the stage-change event


class MatchOut(BaseModel):
    score: int
    breakdown: dict[str, Any]
    matched_skills: list[str]
    missing_skills: list[str]
    rationale: str | None
