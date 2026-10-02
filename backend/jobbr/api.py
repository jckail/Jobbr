import secrets
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import func
from sqlmodel import Session, select

from . import __version__, canonical_repo, drafts, repo, serializers, services, stats, tailoring
from .auth import AuthService, require_csrf, require_session
from .career import (
    AIUnavailable,
    CareerGenerationError,
    CareerInputError,
    CareerResult,
    generate_career,
)
from .config import Settings, get_settings
from .db import get_session
from .models import Extraction, Profile, SavedCareerDraft, Stage, pk
from .schemas import ApplicationIn, JobCreate, JobPatch, ProfileIn, RevisionActivate
from .serializers import Json

router = APIRouter(prefix="/api")

SessionDep = Annotated[Session, Depends(get_session)]


def require_token(request: Request, x_jobbr_token: Annotated[str | None, Header()] = None) -> None:
    auth: AuthService = request.app.state.auth
    if auth.settings.auth_enabled:
        require_csrf(request)
        return
    token = get_settings().api_token
    if token and not secrets.compare_digest((x_jobbr_token or "").encode(), token.encode()):
        raise HTTPException(401, "This Jobbr instance is read-only without a valid token.")


write = [Depends(require_token)]


def require_ai_selection(
    x_jobbr_ai_provider: Annotated[str | None, Header(max_length=20)] = None,
    x_jobbr_ai_model: Annotated[str | None, Header(max_length=200)] = None,
    x_jobbr_ai_enabled: Annotated[str | None, Header(max_length=5)] = None,
) -> Settings:
    """Reject stale browser disclosures before any AI-capable action runs."""
    settings = get_settings().model_copy(deep=True)
    expected = (x_jobbr_ai_provider, x_jobbr_ai_model, x_jobbr_ai_enabled)
    if all(value is None for value in expected):
        return settings  # Programmatic clients use a captured server configuration.
    if any(value is None for value in expected):
        raise HTTPException(422, "Provide the complete AI settings selection.")
    actual = (
        settings.ai_provider,
        settings.ai_model,
        "true" if settings.llm_enabled else "false",
    )
    if expected != actual:
        raise HTTPException(409, "AI settings changed. Refresh and review the disclosure again.")

    return settings


ai_write = [*write, Depends(require_ai_selection)]
SettingsDep = Annotated[Settings, Depends(require_ai_selection)]


def require_access(request: Request, x_jobbr_token: Annotated[str | None, Header()] = None) -> None:
    auth: AuthService = request.app.state.auth
    if auth.settings.auth_enabled:
        require_session(request)
    elif get_settings().private_instance:
        token = get_settings().api_token
        if not token or not secrets.compare_digest((x_jobbr_token or "").encode(), token.encode()):
            raise HTTPException(
                401, "A valid access token is required to view this private instance."
            )


read = [Depends(require_access)]


def _profile(s: Session) -> Profile:
    return services.get_profile(s)


def _row(s: Session, job_id: int) -> repo.JobRow:
    rows = repo.job_rows(s, pk(_profile(s)), job_id)
    if not rows:
        raise HTTPException(404, "Job not found")
    return rows[0]


def _detail(s: Session, job_id: int) -> Json:
    return serializers.job_out(_row(s, job_id), detail=True)


def _capture_conflict(e: canonical_repo.CanonicalConflict) -> HTTPException:
    headers = (
        {"Retry-After": str(max(1, min(300, e.retry_after)))} if e.retry_after is not None else None
    )
    return HTTPException(409, str(e), headers=headers)


def _user_error(e: services.UserError) -> HTTPException:
    return HTTPException(422, str(e))


@router.get("/health")
def health() -> Json:
    return {"ok": True, "version": __version__}


@router.get("/config")
def config(request: Request) -> Json:
    st = get_settings()
    return {
        "version": __version__,
        "llm_enabled": st.llm_enabled,
        "model": st.ai_model if st.llm_enabled else None,
        "ai_provider": st.ai_provider,
        "ai_provider_label": "Claude" if st.ai_provider == "anthropic" else "OpenAI",
        "ai_model": st.ai_model,
        "available_ai_providers": {
            "openai": {"configured": bool((st.openai_api_key or "").strip()), "model": st.model},
            "anthropic": {
                "configured": bool((st.anthropic_api_key or "").strip()),
                "model": st.anthropic_model,
            },
        },
        "write_protected": bool(st.api_token),
        "private_instance": st.private_instance,
        "auth_enabled": request.app.state.auth.settings.auth_enabled,
        "seed_demo": st.seed_demo,
        "career_enabled": st.llm_enabled,
        "cost_estimates_available": False,
    }


# --- jobs -------------------------------------------------------------------


@router.get("/jobs", dependencies=read)
def list_jobs(
    s: SessionDep,
    q: str | None = None,
    stage: Stage | None = None,
    remote: str | None = None,
    min_score: int = 0,
    sort: Annotated[str, Query(pattern="^(score|recent|comp)$")] = "score",
) -> list[Json]:
    rows = repo.filter_rows(repo.job_rows(s, pk(_profile(s))), q, stage, remote, min_score)
    return [serializers.job_out(r) for r in sorted(rows, key=repo.SORTS[sort])]


@router.post("/jobs", status_code=201, dependencies=ai_write)
def add_job(body: JobCreate, s: SessionDep, settings: SettingsDep) -> Json:
    try:
        job = services.ingest(s, body, settings=settings)
    except canonical_repo.CanonicalConflict as e:
        raise _capture_conflict(e) from e
    except services.UserError as e:
        raise _user_error(e) from e
    return _detail(s, pk(job))


@router.get("/jobs/{job_id}", dependencies=read)
def get_job(job_id: int, s: SessionDep) -> Json:
    row = _row(s, job_id)
    out = serializers.job_out(row, detail=True)
    out["extractions"] = [e.model_dump() for e in repo.extractions_for(s, job_id)]
    out["events"] = (
        [e.model_dump() for e in repo.events_for(s, pk(row.application))] if row.application else []
    )
    return out


@router.patch("/jobs/{job_id}", dependencies=write)
def patch_job(job_id: int, body: JobPatch, s: SessionDep) -> Json:
    try:
        services.patch_job(s, _row(s, job_id).job, body)
    except services.UserError as e:
        raise _user_error(e) from e
    return _detail(s, job_id)


def require_availability_authority(request: Request) -> None:
    if not request.app.state.auth.settings.auth_enabled and not get_settings().api_token:
        raise HTTPException(403, "Configure private owner access before checking availability.")


@router.post(
    "/jobs/{job_id}/availability",
    dependencies=[*read, *write, Depends(require_availability_authority)],
)
async def check_availability(job_id: int, s: SessionDep) -> Json:
    return await services.observe_job_availability(s, _row(s, job_id).job)


@router.post("/jobs/{job_id}/reextract", dependencies=ai_write)
def reextract(job_id: int, s: SessionDep, settings: SettingsDep) -> Json:
    try:
        services.reextract(s, _row(s, job_id).job, settings=settings)
    except canonical_repo.CanonicalConflict as e:
        raise _capture_conflict(e) from e
    except services.UserError as e:
        raise _user_error(e) from e
    return _detail(s, job_id)


@router.delete("/jobs/{job_id}", status_code=204, dependencies=write)
def delete_job(job_id: int, s: SessionDep) -> None:
    services.delete_job(s, _row(s, job_id).job)


@router.put("/jobs/{job_id}/application", dependencies=write)
def put_application(job_id: int, body: ApplicationIn, s: SessionDep) -> Json:
    _row(s, job_id)  # 404 if missing
    services.set_application(s, job_id, body)
    return serializers.job_out(_row(s, job_id))


# --- profile & stats --------------------------------------------------------


@router.get("/profile", dependencies=read)
def get_profile(s: SessionDep) -> Json:
    return services.profile_output(s, _profile(s))


@router.put("/profile", dependencies=write)
def put_profile(body: ProfileIn, s: SessionDep) -> Json:
    try:
        p = services.save_profile(s, body)
    except services.RevisionConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except services.UserError as exc:
        raise _user_error(exc) from exc
    return services.profile_output(s, p)


@router.get("/stats", dependencies=read)
def get_stats(s: SessionDep) -> Json:
    profile = _profile(s)
    cost = s.exec(select(func.coalesce(func.sum(Extraction.cost_usd), 0.0))).one()
    return stats.compute(repo.job_rows(s, pk(profile)), profile, float(cost))


def require_private_drafts(
    request: Request, x_jobbr_token: Annotated[str | None, Header()] = None
) -> None:
    auth: AuthService = request.app.state.auth
    if auth.settings.auth_enabled:
        require_session(request)
        return
    token = get_settings().api_token
    if not token or not secrets.compare_digest((x_jobbr_token or "").encode(), token.encode()):
        raise HTTPException(401, "Sign in or provide the instance token to access private drafts.")


draft_read = [Depends(require_private_drafts)]
draft_write = [Depends(require_private_drafts), Depends(require_token)]


def _revision_error(exc: services.UserError) -> HTTPException:
    return HTTPException(404 if isinstance(exc, services.RevisionMissing) else 409, str(exc))


@router.get("/profile/revisions", dependencies=draft_read)
def list_profile_revisions(s: SessionDep) -> list[Json]:
    p = _profile(s)
    active_id = services.profile_output(s, p)["active_revision_id"]
    return [
        serializers.profile_revision_out(row, active_id) for row in services.revision_rows(s, p)
    ]


@router.get("/profile/revisions/{revision_id}", dependencies=draft_read)
def get_profile_revision(revision_id: int, s: SessionDep) -> Json:
    p = _profile(s)
    active_id = services.profile_output(s, p)["active_revision_id"]
    try:
        return serializers.profile_revision_out(
            services.revision_find(s, p, revision_id), active_id, True
        )
    except services.RevisionMissing as exc:
        raise _revision_error(exc) from exc


@router.post("/profile/revisions/{revision_id}/activate", dependencies=draft_write)
def activate_profile_revision(revision_id: int, body: RevisionActivate, s: SessionDep) -> Json:
    try:
        p = services.activate_revision(s, _profile(s), revision_id, body.expected_revision)
    except (services.RevisionConflict, services.RevisionMissing) as exc:
        raise _revision_error(exc) from exc
    return services.profile_output(s, p)


@router.delete("/profile/revisions/{revision_id}", status_code=204, dependencies=draft_write)
def delete_profile_revision(
    revision_id: int, s: SessionDep, expected_revision: Annotated[int, Query(ge=0)]
) -> None:
    try:
        services.delete_revision(s, _profile(s), revision_id, expected_revision)
    except (services.RevisionConflict, services.RevisionMissing) as exc:
        raise _revision_error(exc) from exc


@router.get("/jobs/{job_id}/career/drafts", dependencies=draft_read)
def list_career_drafts(job_id: int, s: SessionDep) -> list[Json]:
    _row(s, job_id)
    return [drafts.output(row) for row in drafts.rows(s, job_id, pk(_profile(s)))]


@router.post("/jobs/{job_id}/career/drafts", status_code=201, dependencies=draft_write)
def save_career_draft(job_id: int, body: drafts.DraftSave, s: SessionDep) -> Json:
    row = _row(s, job_id)
    try:
        saved = drafts.save(s, row.job, _profile(s), row.company.name, body)
    except drafts.DraftLimitError as exc:
        raise HTTPException(409, str(exc)) from exc
    return drafts.output(saved)


def _saved_draft(s: Session, job_id: int, draft_id: int) -> SavedCareerDraft:
    _row(s, job_id)
    saved = drafts.find(s, job_id, pk(_profile(s)), draft_id)
    if not saved:
        raise HTTPException(404, "Saved draft not found")
    return saved


@router.get("/jobs/{job_id}/career/drafts/{draft_id}", dependencies=draft_read)
def get_career_draft(job_id: int, draft_id: int, s: SessionDep) -> Json:
    return drafts.output(_saved_draft(s, job_id, draft_id))


@router.delete("/jobs/{job_id}/career/drafts/{draft_id}", status_code=204, dependencies=draft_write)
def delete_career_draft(job_id: int, draft_id: int, s: SessionDep) -> None:
    s.delete(_saved_draft(s, job_id, draft_id))
    s.commit()


def _tailoring_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (tailoring.TailoringConflict, services.RevisionConflict)):
        status = 409
    elif isinstance(exc, services.RevisionMissing):
        status = 404
    elif isinstance(exc, tailoring.ReceiptGone):
        status = 410
    elif isinstance(exc, AIUnavailable):
        status = 503
    elif isinstance(exc, CareerGenerationError):
        status = 502
    else:
        status = 422
    return HTTPException(status, str(exc))


TailoringErrors = (
    tailoring.TailoringInputError,
    tailoring.TailoringConflict,
    tailoring.ReceiptGone,
    services.UserError,
    AIUnavailable,
    CareerGenerationError,
)


@router.post("/jobs/{job_id}/tailoring", dependencies=[*draft_write, Depends(require_ai_selection)])
async def generate_resume_tailoring(
    job_id: int, body: tailoring.TailoringRequest, s: SessionDep
) -> tailoring.TailoringResult:
    try:
        return await services.generate_tailoring(s, job_id, body.source_revision_id)
    except TailoringErrors as exc:
        raise _tailoring_error(exc) from exc


@router.get("/jobs/{job_id}/tailoring/drafts", dependencies=draft_read)
def list_tailoring_drafts(job_id: int, s: SessionDep) -> list[Json]:
    _row(s, job_id)
    return [
        serializers.tailoring_draft_out(row)
        for row in repo.tailoring_drafts(s, pk(_profile(s)), job_id, tailoring.MAX_DRAFTS)
    ]


@router.post("/jobs/{job_id}/tailoring/drafts", status_code=201, dependencies=draft_write)
def save_tailoring_draft(job_id: int, body: tailoring.TailoringSave, s: SessionDep) -> Json:
    try:
        return serializers.tailoring_draft_out(services.save_tailoring(s, job_id, body))
    except TailoringErrors as exc:
        raise _tailoring_error(exc) from exc


@router.get("/jobs/{job_id}/tailoring/drafts/{draft_id}", dependencies=draft_read)
def get_tailoring_draft(job_id: int, draft_id: int, s: SessionDep) -> Json:
    try:
        return serializers.tailoring_draft_out(services.find_tailoring(s, job_id, draft_id))
    except services.RevisionMissing as exc:
        raise _tailoring_error(exc) from exc


@router.delete(
    "/jobs/{job_id}/tailoring/drafts/{draft_id}", status_code=204, dependencies=draft_write
)
def delete_tailoring_draft(job_id: int, draft_id: int, s: SessionDep) -> None:
    try:
        services.delete_tailoring(s, job_id, draft_id)
    except services.RevisionMissing as exc:
        raise _tailoring_error(exc) from exc


@router.post("/jobs/{job_id}/tailoring/drafts/{draft_id}/accept", dependencies=draft_write)
def accept_tailoring_draft(
    job_id: int, draft_id: int, body: tailoring.TailoringAccept, s: SessionDep
) -> Json:
    try:
        return services.accept_tailoring(s, job_id, draft_id, body.expected_revision)
    except TailoringErrors as exc:
        raise _tailoring_error(exc) from exc


@router.post("/jobs/{job_id}/career/{kind}", dependencies=ai_write)
async def career_assistance(
    job_id: int, kind: Literal["cover_letter", "interview_prep"], s: SessionDep
) -> CareerResult:
    row = _row(s, job_id)
    try:
        return await generate_career(row.job, row.company.name, _profile(s), kind)
    except AIUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except CareerInputError as exc:
        raise HTTPException(422, str(exc)) from exc
    except CareerGenerationError as exc:
        raise HTTPException(502, str(exc)) from exc
