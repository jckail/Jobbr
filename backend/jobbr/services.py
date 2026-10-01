"""Use-cases. API handlers stay thin; everything transactional lives here."""

import hashlib
import re
from urllib.parse import urlparse

from sqlmodel import Session, select

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
    utcnow,
)
from .parsing import html_to_text, parse_date
from .safefetch import FetchError, fetch_html
from .schemas import ApplicationIn, JobCreate, ProfileIn
from .skills import find_skills, normalize_skills


class UserError(Exception):
    """Surface as HTTP 4xx."""


def get_profile(s: Session) -> Profile:
    p = s.exec(select(Profile)).first()
    if not p:
        p = Profile()
        s.add(p)
        s.commit()
        s.refresh(p)
    return p


def _company(s: Session, name: str, domain: str | None = None, industry: str | None = None) -> Company:
    name = name.strip() or "Unknown"
    c = s.exec(select(Company).where(Company.name == name)).first()
    if not c:
        c = Company(name=name, domain=domain, industry=industry)
        s.add(c)
        s.flush()
    elif industry and not c.industry:
        c.industry = industry
    return c


def _apply(job: Job, r: Result, text: str) -> None:
    d = r.data
    job.title = d.title
    job.department = d.department
    job.seniority = d.seniority
    job.employment_type = d.employment_type
    job.remote_policy = d.remote_policy
    job.locations = d.locations
    job.comp_min, job.comp_max, job.comp_currency = d.comp_min, d.comp_max, d.comp_currency
    if job.comp_min and job.comp_max and job.comp_min > job.comp_max:
        job.comp_min, job.comp_max = job.comp_max, job.comp_min
    job.years_experience_min = d.years_experience_min
    job.summary = d.summary
    job.responsibilities, job.qualifications = d.responsibilities[:10], d.qualifications[:10]
    job.skills, job.nice_to_have = normalize_skills(d.skills), normalize_skills(d.nice_to_have)
    job.benefits, job.ai_take = d.benefits[:10], d.ai_take
    job.posted_at = parse_date(d.posted_at)
    job.raw_text = text[:20000]
    job.content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
    job.last_seen_at = utcnow()


def rematch(s: Session, job: Job, profile: Profile | None = None) -> Match:
    profile = profile or get_profile(s)
    m = matching.score(job, profile)
    old = s.exec(select(Match).where(Match.job_id == job.id, Match.profile_id == profile.id)).first()
    if old:
        for f in ("score", "breakdown", "matched_skills", "missing_skills", "rationale"):
            setattr(old, f, getattr(m, f))
        old.created_at = utcnow()
        m = old
    s.add(m)
    return m


def ingest(s: Session, body: JobCreate) -> Job:
    if not body.url and not body.text:
        raise UserError("Provide a URL or paste the posting text.")
    html = None
    url = body.url.strip() if body.url else None
    try:
        if body.text:
            text = body.text.strip()
        else:
            url, html = fetch_html(url)
            text = html_to_text(html)
    except FetchError as e:
        raise UserError(f"{e} If the page needs JavaScript or a login, paste the text instead.") from e
    if len(text) < 80 and not (html and "JobPosting" in html):
        raise UserError("That page has too little readable text (probably JS-rendered). Paste the posting text instead.")

    existing = s.exec(select(Job).where(Job.url == url)).first() if url else None
    res = extract(text, html, body.title, body.company)
    if res.data.company in ("", "Unknown") and url:
        host = urlparse(url).hostname or "unknown"
        res.data.company = re.sub(r"^(www|jobs|careers|boards)\.", "", host).split(".")[0].title()
    comp = _company(s, res.data.company, urlparse(url).hostname if url else None)
    job = existing or Job(company_id=comp.id, url=url, title=res.data.title)
    job.company_id = comp.id
    _apply(job, res, text)
    s.add(job)
    s.flush()
    s.add(Extraction(job_id=job.id, url=url, method=res.method, model=res.model,
                     input_tokens=res.input_tokens, output_tokens=res.output_tokens,
                     cost_usd=res.cost_usd, latency_ms=res.latency_ms, ok=True, error=res.error))
    if not s.exec(select(Application).where(Application.job_id == job.id)).first():
        a = Application(job_id=job.id)
        s.add(a)
        s.flush()
        s.add(ApplicationEvent(application_id=a.id, to_stage=Stage.saved, note="Added"))
    rematch(s, job)
    s.commit()
    s.refresh(job)
    return job


def reextract(s: Session, job: Job) -> Job:
    if not job.raw_text:
        raise UserError("No stored text for this job.")
    res = extract(job.raw_text, None, None, None)
    keep_company = job.company_id
    _apply(job, res, job.raw_text)
    job.company_id = keep_company
    s.add(Extraction(job_id=job.id, url=job.url, method=res.method, model=res.model,
                     input_tokens=res.input_tokens, output_tokens=res.output_tokens,
                     cost_usd=res.cost_usd, latency_ms=res.latency_ms, error=res.error))
    rematch(s, job)
    s.commit()
    s.refresh(job)
    return job


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


def set_application(s: Session, job_id: int, body: ApplicationIn) -> Application:
    a = s.exec(select(Application).where(Application.job_id == job_id)).first()
    if not a:
        a = Application(job_id=job_id)
        s.add(a)
        s.flush()
    if body.stage and body.stage != a.stage:
        s.add(ApplicationEvent(application_id=a.id, from_stage=a.stage, to_stage=body.stage, note=body.note))
        if body.stage == Stage.applied and not a.applied_at:
            a.applied_at = utcnow()
        a.stage = body.stage
    if body.notes is not None:
        a.notes = body.notes
    if "next_step_at" in body.model_fields_set:
        a.next_step_at = body.next_step_at
    a.updated_at = utcnow()
    s.add(a)
    s.commit()
    s.refresh(a)
    return a
