"""Use-cases. API handlers stay thin; everything transactional lives here."""

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from sqlmodel import Session, col, select

from . import matching
from .extract import Result, extract
from .models import (
    Application,
    ApplicationEvent,
    Company,
    Extraction,
    Job,
    Match,
    Profile,
    Stage,
    pk,
    utcnow,
)
from .parsing import html_to_text, parse_date
from .safefetch import FetchError, fetch_html
from .schemas import ApplicationIn, JobCreate, JobPatch, ProfileIn
from .skills import find_skills, normalize_skills

MIN_TEXT_CHARS = 80
RAW_TEXT_LIMIT = 20_000
LIST_LIMIT = 10


class UserError(Exception):
    """A problem the caller can fix; surfaced as HTTP 422."""


@dataclass(frozen=True)
class Page:
    url: str | None
    text: str
    html: str | None


# --- profile ----------------------------------------------------------------


def get_profile(s: Session) -> Profile:
    profile = s.exec(select(Profile)).first()
    if not profile:
        profile = Profile()
        s.add(profile)
        s.commit()
        s.refresh(profile)
    return profile


def save_profile(s: Session, body: ProfileIn) -> Profile:
    p = get_profile(s)
    data = body.model_dump()
    skills = data.pop("skills")
    for k, v in data.items():
        setattr(p, k, v)
    p.skills = normalize_skills(skills) if skills is not None else find_skills(p.resume_text)
    p.updated_at = utcnow()
    s.add(p)
    s.flush()
    for job in s.exec(select(Job)).all():
        rematch(s, job, p)
    s.commit()
    s.refresh(p)
    return p


# --- companies --------------------------------------------------------------


def get_or_create_company(
    s: Session, name: str, domain: str | None = None, industry: str | None = None
) -> Company:
    name = name.strip() or "Unknown"
    company = s.exec(select(Company).where(Company.name == name)).first()
    if not company:
        company = Company(name=name, domain=domain, industry=industry)
        s.add(company)
        s.flush()
    elif industry and not company.industry:
        company.industry = industry
    return company


def _company_name(extracted: str, url: str | None) -> str:
    """Fall back to the site's name when extraction found no company."""
    if extracted.strip() not in ("", "Unknown") or not url:
        return extracted
    host = urlparse(url).hostname or "unknown"
    return re.sub(r"^(www|jobs|careers|boards)\.", "", host).split(".")[0].title()


# --- jobs -------------------------------------------------------------------


def _load_page(body: JobCreate) -> Page:
    if body.text:
        return Page(body.url, body.text.strip(), None)
    if not body.url:
        raise UserError("Provide a URL or paste the posting text.")
    try:
        url, html = fetch_html(body.url.strip())
    except FetchError as e:
        raise UserError(
            f"{e} If the page needs JavaScript or a login, paste the text instead."
        ) from e
    text = html_to_text(html)
    if len(text) < MIN_TEXT_CHARS and "JobPosting" not in html:
        raise UserError(
            "That page has too little readable text (probably JS-rendered). "
            "Paste the posting text instead."
        )
    return Page(url, text, html)


def _apply_extraction(job: Job, result: Result, text: str) -> None:
    d = result.data
    job.title = d.title
    job.department = d.department
    job.seniority = d.seniority
    job.employment_type = d.employment_type
    job.remote_policy = d.remote_policy
    job.locations = d.locations
    job.comp_currency = d.comp_currency
    job.comp_min, job.comp_max = sorted_pair(d.comp_min, d.comp_max)
    job.years_experience_min = d.years_experience_min
    job.summary = d.summary
    job.responsibilities = d.responsibilities[:LIST_LIMIT]
    job.qualifications = d.qualifications[:LIST_LIMIT]
    job.skills = normalize_skills(d.skills)
    job.nice_to_have = normalize_skills(d.nice_to_have)
    job.benefits = d.benefits[:LIST_LIMIT]
    job.ai_take = d.ai_take
    job.posted_at = parse_date(d.posted_at)
    job.raw_text = text[:RAW_TEXT_LIMIT]
    job.content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
    job.last_seen_at = utcnow()


def sorted_pair(lo: int | None, hi: int | None) -> tuple[int | None, int | None]:
    return (hi, lo) if lo and hi and lo > hi else (lo, hi)


def _record_extraction(s: Session, job: Job, result: Result) -> None:
    s.add(
        Extraction(
            job_id=pk(job),
            url=job.url,
            method=result.method,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=result.cost_usd,
            latency_ms=result.latency_ms,
            error=result.error,
        )
    )


def _ensure_application(s: Session, job: Job) -> None:
    if s.exec(select(Application).where(Application.job_id == job.id)).first():
        return
    app = Application(job_id=pk(job))
    s.add(app)
    s.flush()
    s.add(ApplicationEvent(application_id=pk(app), to_stage=Stage.saved, note="Added"))


def ingest(s: Session, body: JobCreate) -> Job:
    page = _load_page(body)
    result = extract(page.text, page.html, body.title, body.company)
    host = urlparse(page.url).hostname if page.url else None
    company = get_or_create_company(s, _company_name(result.data.company, page.url), host)

    existing = s.exec(select(Job).where(Job.url == page.url)).first() if page.url else None
    job = existing or Job(company_id=pk(company), url=page.url, title=result.data.title)
    job.company_id = pk(company)
    _apply_extraction(job, result, page.text)
    s.add(job)
    s.flush()

    _record_extraction(s, job, result)
    _ensure_application(s, job)
    rematch(s, job)
    s.commit()
    s.refresh(job)
    return job


def reextract(s: Session, job: Job) -> Job:
    if not job.raw_text:
        raise UserError("No stored text for this job.")
    result = extract(job.raw_text)
    _apply_extraction(job, result, job.raw_text)
    s.add(job)
    _record_extraction(s, job, result)
    rematch(s, job)
    s.commit()
    s.refresh(job)
    return job


def patch_job(s: Session, job: Job, body: JobPatch) -> Job:
    data = body.model_dump(exclude_unset=True)
    if company := data.pop("company", None):
        job.company_id = pk(get_or_create_company(s, company))
    if data.get("skills") is not None:
        data["skills"] = normalize_skills(data["skills"])
    for k, v in data.items():
        setattr(job, k, v)
    s.add(job)
    rematch(s, job)
    s.commit()
    s.refresh(job)
    return job


def delete_job(s: Session, job: Job) -> None:
    """Delete a job and everything hanging off it (children first; no ORM cascades defined)."""
    job_id = pk(job)
    for app in s.exec(select(Application).where(Application.job_id == job_id)):
        for ev in s.exec(
            select(ApplicationEvent).where(ApplicationEvent.application_id == pk(app))
        ):
            s.delete(ev)
        s.flush()
        s.delete(app)
    for model in (Match, Extraction):
        for row in s.exec(select(model).where(col(model.job_id) == job_id)):
            s.delete(row)
    s.flush()
    s.delete(job)
    s.commit()


# --- matching & pipeline ----------------------------------------------------


def rematch(s: Session, job: Job, profile: Profile | None = None) -> Match:
    profile = profile or get_profile(s)
    fresh = matching.score(job, profile)
    match = s.exec(
        select(Match).where(Match.job_id == job.id, Match.profile_id == profile.id)
    ).first()
    if match:
        for f in ("score", "breakdown", "matched_skills", "missing_skills", "rationale"):
            setattr(match, f, getattr(fresh, f))
        match.created_at = utcnow()
    else:
        match = fresh
    s.add(match)
    return match


def set_application(s: Session, job_id: int, body: ApplicationIn) -> Application:
    app = s.exec(select(Application).where(Application.job_id == job_id)).first()
    if not app:
        app = Application(job_id=job_id)
        s.add(app)
        s.flush()
    if body.stage and body.stage != app.stage:
        s.add(
            ApplicationEvent(
                application_id=pk(app), from_stage=app.stage, to_stage=body.stage, note=body.note
            )
        )
        if body.stage == Stage.applied and not app.applied_at:
            app.applied_at = utcnow()
        app.stage = body.stage
    if body.notes is not None:
        app.notes = body.notes
    if "next_step_at" in body.model_fields_set:
        app.next_step_at = body.next_step_at
    app.updated_at = utcnow()
    s.add(app)
    s.commit()
    s.refresh(app)
    return app
