"""Use-cases. API handlers stay thin; everything transactional lives here."""

import hashlib
import json
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from pydantic import ValidationError
from sqlalchemy import update
from sqlmodel import Session, col, select

from . import matching, repo, serializers, tailoring
from .auth_models import AuthStoreGuard
from .career import AIUnavailable
from .config import Settings, get_settings
from .extract import Result, extract
from .models import (
    Application,
    ApplicationEvent,
    Company,
    Extraction,
    Job,
    Match,
    Profile,
    ProfileRevision,
    ProfileRevisionHead,
    SavedCareerDraft,
    SavedTailoringDraft,
    Stage,
    TailoringReceipt,
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
    if profile:
        return profile
    # The migrated singleton guard serializes first-owner creation across instances.
    s.execute(update(AuthStoreGuard).where(col(AuthStoreGuard.id) == 1).values(id=1))
    if s.get(AuthStoreGuard, 1) is None:
        raise RuntimeError("Owner initialization requires the auth-store migration.")
    profile = s.exec(select(Profile)).first()
    if not profile:
        profile = Profile()
        s.add(profile)
    s.commit()
    s.refresh(profile)
    return profile


MAX_PROFILE_REVISIONS = 50
MAX_PROFILE_SNAPSHOT_BYTES = 1024 * 1024


class RevisionConflict(UserError):
    """Stale editor or an active revision deletion; HTTP 409."""


class RevisionMissing(UserError):
    """Revision is not owned by the current profile; HTTP 404."""


def _snapshot(p: Profile) -> dict[str, Any]:
    return p.model_dump(mode="json", exclude={"id", "updated_at"})


def _revision_fingerprint(snapshot: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


def _profile_lock(s: Session, p: Profile) -> None:
    # Reserve the existing owner row before reading head/count on SQLite and PostgreSQL.
    s.execute(
        update(Profile).where(col(Profile.id) == pk(p)).values(updated_at=col(Profile.updated_at))
    )
    s.refresh(p)


def _revision_head(s: Session, p: Profile) -> ProfileRevisionHead:
    head = repo.profile_revision_head(s, pk(p))
    if head is not None:
        return head
    # Caller owns the profile write lock. Also covers profiles created after migration.
    snapshot = _snapshot(p)
    row = ProfileRevision(
        profile_id=pk(p),
        snapshot=snapshot,
        fingerprint=_revision_fingerprint(snapshot),
        source="saved",
    )
    s.add(row)
    s.flush()
    head = ProfileRevisionHead(profile_id=pk(p), active_revision_id=pk(row), version=0)
    s.add(head)
    s.flush()
    return head


def profile_output(s: Session, p: Profile) -> dict[str, Any]:
    # Return content and token under the same lock: an old Profile identity-map value
    # paired with a newer head would let an editor overwrite unseen changes.
    _profile_lock(s, p)
    head = _revision_head(s, p)
    result = serializers.profile_out(p, head)
    s.commit()
    return result


def _expected(head: ProfileRevisionHead, expected: int | None) -> None:
    if expected is not None and head.version != expected:
        raise RevisionConflict("Your profile history changed. Refresh and review before saving.")


def save_profile(s: Session, body: ProfileIn) -> Profile:
    p = get_profile(s)
    _profile_lock(s, p)
    head = _revision_head(s, p)
    _expected(head, body.expected_revision)
    data = body.model_dump(exclude={"expected_revision"})
    skills = data.pop("skills")
    data["skills"] = (
        normalize_skills(skills) if skills is not None else find_skills(data["resume_text"])
    )
    snapshot = ProfileIn.model_validate(data).model_dump(mode="json", exclude={"expected_revision"})
    if len(json.dumps(snapshot, ensure_ascii=False).encode()) > MAX_PROFILE_SNAPSHOT_BYTES:
        raise UserError("Profile snapshot exceeds 1 MiB. Shorten the resume or profile lists.")
    fingerprint = _revision_fingerprint(snapshot)
    active = repo.profile_revision(s, pk(p), head.active_revision_id)
    if active is None or active.profile_id != pk(p):
        raise RuntimeError("Profile history head is invalid.")
    if active.fingerprint == fingerprint:
        s.commit()
        return p
    count = repo.profile_revision_count(s, pk(p))
    if count >= MAX_PROFILE_REVISIONS:
        raise UserError(
            "This profile has 50 revisions. Delete an inactive revision before saving another."
        )
    row = ProfileRevision(profile_id=pk(p), snapshot=snapshot, fingerprint=fingerprint)
    s.add(row)
    s.flush()
    head.active_revision_id = pk(row)
    head.version += 1
    s.add(head)
    _apply_profile_snapshot(s, p, snapshot)
    s.commit()
    s.refresh(p)
    return p


def _apply_profile_snapshot(s: Session, p: Profile, snapshot: dict[str, Any]) -> None:
    for key, value in snapshot.items():
        setattr(p, key, value)
    p.updated_at = utcnow()
    s.add(p)
    s.flush()
    for job in s.exec(select(Job)).all():
        rematch(s, job, p)


def revision_rows(s: Session, p: Profile) -> list[ProfileRevision]:
    return repo.profile_revisions(s, pk(p), MAX_PROFILE_REVISIONS)


def revision_find(s: Session, p: Profile, revision_id: int) -> ProfileRevision:
    row = repo.profile_revision(s, pk(p), revision_id)
    if row is None:
        raise RevisionMissing("Profile revision not found.")
    return row


def activate_revision(s: Session, p: Profile, revision_id: int, expected: int) -> Profile:
    _profile_lock(s, p)
    head = _revision_head(s, p)
    _expected(head, expected)
    row = revision_find(s, p, revision_id)
    if head.active_revision_id != revision_id:
        _apply_profile_snapshot(s, p, row.snapshot)
        head.active_revision_id = revision_id
        head.version += 1
        s.add(head)
    s.commit()
    s.refresh(p)
    return p


def delete_revision(s: Session, p: Profile, revision_id: int, expected: int) -> None:
    _profile_lock(s, p)
    head = _revision_head(s, p)
    _expected(head, expected)
    row = revision_find(s, p, revision_id)
    if head.active_revision_id == revision_id:
        raise RevisionConflict("Activate another revision before deleting this one.")
    if repo.tailoring_reference_count(s, pk(p), revision_id):
        raise RevisionConflict(
            "Delete saved tailoring drafts referring to this revision before deleting it."
        )
    s.delete(row)
    head.version += 1
    s.add(head)
    s.commit()


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


def _apply_extraction(job: Job, result: Result, text: str, *, rehash: bool = True) -> None:
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
    if rehash:  # re-extraction sees only the stored, truncated text; keep the original hash
        job.content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
    job.last_seen_at = utcnow()


def sorted_pair(lo: int | None, hi: int | None) -> tuple[int | None, int | None]:
    return (hi, lo) if lo is not None and hi is not None and lo > hi else (lo, hi)


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
            ok=result.error is None,
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


def ingest(s: Session, body: JobCreate, *, settings: Settings | None = None) -> Job:
    page = _load_page(body)
    existing = s.exec(select(Job).where(Job.url == page.url)).first() if page.url else None
    if (
        existing
        and page.html is None  # Fetched JSON-LD can change without changing visible posting text.
        and existing.raw_text == page.text
        and existing.content_hash == hashlib.sha256(page.text.encode()).hexdigest()[:16]
        and (body.title is None or body.title == existing.title)
    ):
        company = s.get(Company, existing.company_id)
        if company and (body.company is None or body.company.strip() == company.name):
            return existing
    result = (
        extract(page.text, page.html, body.title, body.company, settings=settings)
        if settings is not None
        else extract(page.text, page.html, body.title, body.company)
    )
    if existing and result.error:
        # AI failed and only the offline fallback ran: never replace saved details with weaker
        # data. Log the attempt and return the job as it was.
        _record_extraction(s, existing, result)
        s.commit()
        s.refresh(existing)
        return existing
    host = urlparse(page.url).hostname if page.url else None
    company = get_or_create_company(s, _company_name(result.data.company, page.url), host)

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
    _record_extraction(s, job, result)
    if result.error:
        # The AI call failed and only the weaker offline fallback ran. Keep the saved details
        # rather than overwrite them, but keep the failed attempt in the extraction log.
        s.commit()
        raise UserError(
            "AI extraction failed, so your saved details were left unchanged. Try again."
        )
    _apply_extraction(job, result, job.raw_text, rehash=False)
    s.add(job)
    rematch(s, job)
    s.commit()
    s.refresh(job)
    return job


def patch_job(s: Session, job: Job, body: JobPatch) -> Job:
    data = body.model_dump(exclude_unset=True)
    low, high = data.get("comp_min", job.comp_min), data.get("comp_max", job.comp_max)
    if low is not None and high is not None and low > high:
        raise UserError("Minimum pay cannot be higher than maximum pay.")
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
    _profile_lock(s, get_profile(s))
    for receipt in s.exec(select(TailoringReceipt).where(TailoringReceipt.job_id == job_id)):
        s.delete(receipt)
    for app in s.exec(select(Application).where(Application.job_id == job_id)):
        for ev in s.exec(
            select(ApplicationEvent).where(ApplicationEvent.application_id == pk(app))
        ):
            s.delete(ev)
        s.flush()
        s.delete(app)
    for model in (Match, Extraction, SavedCareerDraft, SavedTailoringDraft):
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


# --- resume tailoring: transactions and source ownership --------------------


def _tailoring_role(job: Job, company: str) -> dict[str, Any]:
    return {
        "company": company,
        "title": job.title,
        "summary": job.summary,
        "skills": job.skills,
        "nice_to_have": job.nice_to_have,
        "responsibilities": job.responsibilities,
        "qualifications": job.qualifications,
        "posting": job.raw_text or "",
    }


def _reserve_tailoring(
    s: Session, job_id: int, revision_id: int, settings: Settings
) -> tuple[str, int, str, list[str]]:
    profile = get_profile(s)
    _profile_lock(s, profile)
    revision = revision_find(s, profile, revision_id)
    row = repo.tailoring_job(s, job_id)
    if row is None:
        raise RevisionMissing("Job not found.")
    job, company = row
    candidate = tailoring._candidate(revision.snapshot)
    role = _tailoring_role(job, company.name)
    payload = {
        "kind": "resume_tailoring",
        "prompt_version": tailoring.PROMPT_VERSION,
        "profile": candidate,
        "job": role,
    }
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(content) > settings.max_input_chars:
        raise tailoring.TailoringInputError(
            "The complete resume and job exceed the configured AI input limit. Choose a "
            "shorter revision."
        )
    now = utcnow()
    repo.purge_expired_tailoring_receipts(s, pk(profile), now)
    if repo.tailoring_receipt_count(s, pk(profile)) >= tailoring.MAX_RECEIPTS:
        raise tailoring.TailoringConflict(
            "This profile has 100 recent generation receipts. Wait for their expiry "
            "before generating again."
        )
    source = tailoring.TailoringSource(
        revision_id=pk(revision),
        revision_fingerprint=revision.fingerprint,
        job_id=job_id,
        job_fingerprint=tailoring._hash(role),
        input_fingerprint=tailoring._hash(payload),
    )
    receipt = TailoringReceipt(
        id=secrets.token_urlsafe(32),
        profile_id=pk(profile),
        job_id=job_id,
        source_revision_id=revision_id,
        expires_at=now + tailoring.RECEIPT_TTL,
        provenance={
            "source": source.model_dump(),
            "provider": settings.ai_provider,
            "model": settings.ai_model,
            "prompt_version": tailoring.PROMPT_VERSION,
        },
    )
    s.add(receipt)
    captured = (receipt.id, pk(profile), content, tailoring._evidence(candidate))
    # No transaction/owner lock or expired ORM attribute access before the provider await.
    s.commit()
    return captured


def _cleanup_tailoring(s: Session, profile_id: int, receipt_id: str) -> None:
    s.rollback()
    profile = s.get(Profile, profile_id)
    if profile is not None:
        _profile_lock(s, profile)
        repo.delete_tailoring_receipt(s, profile_id, receipt_id)
        s.commit()


def _complete_tailoring(
    s: Session,
    profile_id: int,
    job_id: int,
    receipt_id: str,
    draft: tailoring.TailoringContent,
    input_tokens: int,
    output_tokens: int,
) -> tailoring.TailoringResult:
    s.rollback()
    profile = s.get(Profile, profile_id)
    if profile is None:
        raise tailoring.TailoringConflict("The source profile was deleted during generation.")
    _profile_lock(s, profile)
    receipt = repo.tailoring_receipt(s, profile_id, job_id, receipt_id)
    if receipt is None or receipt.expires_at <= utcnow():
        raise tailoring.ReceiptGone("Generation receipt expired; generate again before saving.")
    try:
        revision_find(s, profile, receipt.source_revision_id)
    except RevisionMissing as exc:
        raise tailoring.TailoringConflict(
            "The source revision was deleted during generation; no draft was saved."
        ) from exc
    if repo.tailoring_job(s, job_id) is None:
        raise tailoring.TailoringConflict(
            "The job was deleted during generation; no draft was saved."
        )
    generated_at = datetime.now(UTC)
    provenance = {
        **receipt.provenance,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
    }
    receipt.provenance = provenance
    receipt.original_hash = tailoring._hash(draft.model_dump(mode="json"))
    s.add(receipt)
    s.commit()
    return tailoring.TailoringResult(
        receipt_id=receipt_id,
        draft=draft,
        **{key: value for key, value in provenance.items() if key != "prompt_version"},
    )


async def generate_tailoring(
    s: Session, job_id: int, revision_id: int
) -> tailoring.TailoringResult:
    settings = get_settings().model_copy(deep=True)
    if not settings.llm_enabled:
        raise AIUnavailable(f"Configure the selected {settings.ai_provider} key on the server.")
    if not settings.ai_model.strip() or len(settings.ai_model) > 200:
        raise tailoring.TailoringInputError(
            "Configure a selected model name of 1 to 200 characters."
        )
    receipt_id, profile_id, content, evidence = _reserve_tailoring(s, job_id, revision_id, settings)
    try:
        draft, input_tokens, output_tokens = await tailoring.generate_content(
            settings, content, evidence
        )
        return _complete_tailoring(
            s, profile_id, job_id, receipt_id, draft, input_tokens, output_tokens
        )
    except BaseException:
        # CancelledError inherits BaseException; cleanup never swallows cancellation.
        try:
            _cleanup_tailoring(s, profile_id, receipt_id)
        except Exception:
            s.rollback()  # Bounded orphan metadata expires in seven days if cleanup fails.
        raise


def save_tailoring(s: Session, job_id: int, body: tailoring.TailoringSave) -> SavedTailoringDraft:
    profile = get_profile(s)
    _profile_lock(s, profile)
    receipt = repo.tailoring_receipt(s, pk(profile), job_id, body.receipt_id)
    if receipt is None or receipt.expires_at <= utcnow() or receipt.original_hash is None:
        raise tailoring.ReceiptGone(
            "Generation receipt is unavailable or expired. Generate again before saving."
        )
    try:
        revision = revision_find(s, profile, receipt.source_revision_id)
    except RevisionMissing as exc:
        raise tailoring.TailoringConflict(
            "The source revision was deleted. Generate from an available revision."
        ) from exc
    if repo.tailoring_job(s, job_id) is None:
        raise RevisionMissing("Job not found.")
    tailoring.validate_quotes(
        body.draft, tailoring._evidence(tailoring._candidate(revision.snapshot))
    )
    if repo.tailoring_draft_count(s, pk(profile), job_id) >= tailoring.MAX_DRAFTS:
        raise tailoring.TailoringConflict(
            "This job has 50 saved tailoring drafts. Delete one before saving another."
        )
    row = SavedTailoringDraft(
        profile_id=pk(profile),
        job_id=job_id,
        source_revision_id=receipt.source_revision_id,
        receipt_id=receipt.id,
        provenance=receipt.provenance,
        draft=body.draft.model_dump(mode="json"),
        user_edited=tailoring._hash(body.draft.model_dump(mode="json")) != receipt.original_hash,
    )
    s.add(row)
    s.commit()
    s.refresh(row)
    return row


def find_tailoring(s: Session, job_id: int, draft_id: int) -> SavedTailoringDraft:
    row = repo.tailoring_draft(s, pk(get_profile(s)), job_id, draft_id)
    if row is None:
        raise RevisionMissing("Saved tailoring draft not found.")
    return row


def delete_tailoring(s: Session, job_id: int, draft_id: int) -> None:
    profile = get_profile(s)
    _profile_lock(s, profile)
    row = find_tailoring(s, job_id, draft_id)
    s.delete(row)
    s.commit()


def accept_tailoring(
    s: Session, job_id: int, draft_id: int, expected_revision: int
) -> dict[str, Any]:
    profile = get_profile(s)
    _profile_lock(s, profile)
    row = find_tailoring(s, job_id, draft_id)
    content = tailoring.TailoringContent.model_validate(row.draft)
    # Deliberately preserve CURRENT identity, headline, experience and preferences.
    data = profile.model_dump(exclude={"id", "updated_at"})
    data.update(
        resume_text=content.resume_text,
        skills=find_skills(content.resume_text),
        expected_revision=expected_revision,
    )
    try:
        accepted = ProfileIn.model_validate(data)
    except ValidationError as exc:
        raise tailoring.TailoringInputError(
            "The current legacy profile exceeds current bounds. Save a bounded revision "
            "before accepting."
        ) from exc
    save_profile(s, accepted)
    return profile_output(s, profile)
