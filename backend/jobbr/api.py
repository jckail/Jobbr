from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, select

from . import __version__, repo, serializers, services, stats
from .config import get_settings
from .db import get_session
from .models import Extraction, Profile, Stage, pk
from .schemas import ApplicationIn, JobCreate, JobPatch, ProfileIn
from .serializers import Json

router = APIRouter(prefix="/api")

SessionDep = Annotated[Session, Depends(get_session)]


def require_token(x_jobbr_token: Annotated[str | None, Header()] = None) -> None:
    token = get_settings().api_token
    if token and x_jobbr_token != token:
        raise HTTPException(401, "This Jobbr instance is read-only without a valid token.")


write = [Depends(require_token)]


def _profile(s: Session) -> Profile:
    return services.get_profile(s)


def _row(s: Session, job_id: int) -> repo.JobRow:
    rows = repo.job_rows(s, pk(_profile(s)), job_id)
    if not rows:
        raise HTTPException(404, "Job not found")
    return rows[0]


def _detail(s: Session, job_id: int) -> Json:
    return serializers.job_out(_row(s, job_id), detail=True)


def _user_error(e: services.UserError) -> HTTPException:
    return HTTPException(422, str(e))


@router.get("/health")
def health() -> Json:
    return {"ok": True, "version": __version__}


@router.get("/config")
def config() -> Json:
    st = get_settings()
    return {
        "version": __version__,
        "llm_enabled": st.llm_enabled,
        "model": st.model if st.llm_enabled else None,
        "write_protected": bool(st.api_token),
    }


# --- jobs -------------------------------------------------------------------


@router.get("/jobs")
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


@router.post("/jobs", status_code=201, dependencies=write)
def add_job(body: JobCreate, s: SessionDep) -> Json:
    try:
        job = services.ingest(s, body)
    except services.UserError as e:
        raise _user_error(e) from e
    return _detail(s, pk(job))


@router.get("/jobs/{job_id}")
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
    services.patch_job(s, _row(s, job_id).job, body)
    return _detail(s, job_id)


@router.post("/jobs/{job_id}/reextract", dependencies=write)
def reextract(job_id: int, s: SessionDep) -> Json:
    try:
        services.reextract(s, _row(s, job_id).job)
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


@router.get("/profile")
def get_profile(s: SessionDep) -> Profile:
    return _profile(s)


@router.put("/profile", dependencies=write)
def put_profile(body: ProfileIn, s: SessionDep) -> Profile:
    return services.save_profile(s, body)


@router.get("/stats")
def get_stats(s: SessionDep) -> Json:
    profile = _profile(s)
    cost = s.exec(select(func.coalesce(func.sum(Extraction.cost_usd), 0.0))).one()
    return stats.compute(repo.job_rows(s, pk(profile)), profile, float(cost))
