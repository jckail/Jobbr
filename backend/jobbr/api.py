from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, select

from . import __version__, services
from .config import get_settings
from .db import get_session
from .models import (Application, ApplicationEvent, Company, Extraction, Job, Match, Stage, utcnow)
from .schemas import ApplicationIn, JobCreate, JobPatch, ProfileIn
from .skills import normalize_skills

router = APIRouter(prefix="/api")


def require_token(x_jobbr_token: str | None = Header(default=None)) -> None:
    tok = get_settings().api_token
    if tok and x_jobbr_token != tok:
        raise HTTPException(401, "This Jobbr instance is read-only without a valid token.")


write = [Depends(require_token)]


def _job_out(job: Job, company: Company, match: Match | None, app: Application | None, detail=False) -> dict:
    d = job.model_dump(exclude={"raw_text"} if not detail else set())
    d["company"] = {"id": company.id, "name": company.name, "domain": company.domain,
                    "industry": company.industry}
    d["match"] = match.model_dump(exclude={"id", "job_id", "profile_id"}) if match else None
    d["application"] = (
        app.model_dump(exclude={"id", "job_id"}) if app else {"stage": Stage.saved, "notes": ""}
    )
    return d


def _load(s: Session, job_id: int) -> tuple[Job, Company, Match | None, Application | None]:
    job = s.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    prof = services.get_profile(s)
    return (job, s.get(Company, job.company_id),
            s.exec(select(Match).where(Match.job_id == job_id, Match.profile_id == prof.id)).first(),
            s.exec(select(Application).where(Application.job_id == job_id)).first())


@router.get("/health")
def health():
    return {"ok": True, "version": __version__}


@router.get("/config")
def config():
    st = get_settings()
    return {"version": __version__, "llm_enabled": st.llm_enabled, "model": st.model if st.llm_enabled else None,
            "write_protected": bool(st.api_token)}


@router.get("/jobs")
def list_jobs(
    q: str | None = None,
    stage: Stage | None = None,
    remote: str | None = None,
    min_score: int = 0,
    sort: str = Query("score", pattern="^(score|recent|comp)$"),
    s: Session = Depends(get_session),
):
    prof = services.get_profile(s)
    rows = s.exec(
        select(Job, Company, Match, Application)
        .join(Company, Company.id == Job.company_id)
        .outerjoin(Match, (Match.job_id == Job.id) & (Match.profile_id == prof.id))
        .outerjoin(Application, Application.job_id == Job.id)
    ).all()
    out = []
    ql = q.lower() if q else None
    for job, c, m, a in rows:
        if ql and ql not in f"{job.title} {c.name} {' '.join(job.skills)}".lower():
            continue
        if stage and (a.stage if a else Stage.saved) != stage:
            continue
        if remote and job.remote_policy.value != remote:
            continue
        if (m.score if m else 0) < min_score:
            continue
        out.append(_job_out(job, c, m, a))
    key = {"score": lambda j: -(j["match"]["score"] if j["match"] else -1),
           "recent": lambda j: -j["first_seen_at"].timestamp(),
           "comp": lambda j: -(j["comp_max"] or 0)}[sort]
    return sorted(out, key=key)


@router.post("/jobs", status_code=201, dependencies=write)
def add_job(body: JobCreate, s: Session = Depends(get_session)):
    try:
        job = services.ingest(s, body)
    except services.UserError as e:
        raise HTTPException(422, str(e)) from e
    return _job_out(*_load(s, job.id), detail=True)


@router.get("/jobs/{job_id}")
def get_job(job_id: int, s: Session = Depends(get_session)):
    out = _job_out(*_load(s, job_id), detail=True)
    out["extractions"] = [e.model_dump() for e in s.exec(
        select(Extraction).where(Extraction.job_id == job_id).order_by(Extraction.id.desc()))]
    app = s.exec(select(Application).where(Application.job_id == job_id)).first()
    out["events"] = [e.model_dump() for e in s.exec(
        select(ApplicationEvent).where(ApplicationEvent.application_id == (app.id if app else -1))
        .order_by(ApplicationEvent.id.desc()))] if app else []
    return out


@router.patch("/jobs/{job_id}", dependencies=write)
def patch_job(job_id: int, body: JobPatch, s: Session = Depends(get_session)):
    job, c, *_ = _load(s, job_id)
    data = body.model_dump(exclude_unset=True)
    if "company" in data and data["company"]:
        job.company_id = services._company(s, data.pop("company")).id
    data.pop("company", None)
    if "skills" in data and data["skills"] is not None:
        data["skills"] = normalize_skills(data["skills"])
    for k, v in data.items():
        setattr(job, k, v)
    s.add(job)
    services.rematch(s, job)
    s.commit()
    return _job_out(*_load(s, job_id), detail=True)


@router.post("/jobs/{job_id}/reextract", dependencies=write)
def reextract(job_id: int, s: Session = Depends(get_session)):
    job = _load(s, job_id)[0]
    try:
        services.reextract(s, job)
    except services.UserError as e:
        raise HTTPException(422, str(e)) from e
    return _job_out(*_load(s, job_id), detail=True)


@router.delete("/jobs/{job_id}", status_code=204, dependencies=write)
def delete_job(job_id: int, s: Session = Depends(get_session)):
    job = _load(s, job_id)[0]
    app = s.exec(select(Application).where(Application.job_id == job_id)).first()
    if app:
        for e in s.exec(select(ApplicationEvent).where(ApplicationEvent.application_id == app.id)):
            s.delete(e)
        s.flush()
        s.delete(app)
    for model in (Match, Extraction):
        for r in s.exec(select(model).where(model.job_id == job_id)):
            s.delete(r)
    s.flush()
    s.delete(job)
    s.commit()


@router.put("/jobs/{job_id}/application", dependencies=write)
def put_application(job_id: int, body: ApplicationIn, s: Session = Depends(get_session)):
    _load(s, job_id)
    services.set_application(s, job_id, body)
    return _job_out(*_load(s, job_id), detail=False)


@router.get("/profile")
def get_profile(s: Session = Depends(get_session)):
    return services.get_profile(s)


@router.put("/profile", dependencies=write)
def put_profile(body: ProfileIn, s: Session = Depends(get_session)):
    return services.save_profile(s, body)


@router.get("/stats")
def stats(s: Session = Depends(get_session)):
    prof = services.get_profile(s)
    rows = s.exec(
        select(Job, Company, Match, Application)
        .join(Company, Company.id == Job.company_id)
        .outerjoin(Match, (Match.job_id == Job.id) & (Match.profile_id == prof.id))
        .outerjoin(Application, Application.job_id == Job.id)
    ).all()
    stages = Counter((a.stage.value if a else "saved") for *_, a in rows)
    demand: Counter = Counter()
    for job, *_ in rows:
        demand.update(job.skills)
    have = set(prof.skills)
    scores = [m.score for _, _, m, _ in rows if m]
    comps = [(j.comp_min + j.comp_max) // 2 for j, *_ in rows if j.comp_min and j.comp_max]
    since = utcnow() - timedelta(days=13)
    per_day = Counter(j.first_seen_at.date().isoformat() for j, *_ in rows if j.first_seen_at >= since)
    days = [(since + timedelta(days=i)).date().isoformat() for i in range(14)]
    cost = s.exec(select(func.coalesce(func.sum(Extraction.cost_usd), 0.0))).one()
    top = sorted(rows, key=lambda r: -(r[2].score if r[2] else -1))[:5]
    return {
        "totals": {"jobs": len(rows), "companies": len({c.id for _, c, _, _ in rows}),
                   "avg_score": round(sum(scores) / len(scores)) if scores else None,
                   "median_comp": sorted(comps)[len(comps) // 2] if comps else None,
                   "ai_cost_usd": round(float(cost), 4)},
        "stages": {st.value: stages.get(st.value, 0) for st in Stage},
        "skill_demand": [{"skill": k, "jobs": v, "have": k in have} for k, v in demand.most_common(12)],
        "added_per_day": [{"day": d, "count": per_day.get(d, 0)} for d in days],
        "score_buckets": [{"label": f"{lo}-{lo + 19}", "count": sum(lo <= x < lo + 20 or (lo == 80 and x == 100) for x in scores)}
                          for lo in range(0, 100, 20)],
        "top_matches": [{"id": j.id, "title": j.title, "company": c.name, "score": m.score if m else None}
                        for j, c, m, _ in top],
    }
