"""Read-side queries. One place owns the Job⋈Company⟕Match⟕Application join."""

from dataclasses import dataclass

from sqlalchemy import and_
from sqlmodel import Session, col, select

from .models import (
    Application,
    ApplicationEvent,
    Company,
    Extraction,
    Job,
    Match,
    Stage,
)


@dataclass(frozen=True)
class JobRow:
    job: Job
    company: Company
    match: Match | None
    application: Application | None

    @property
    def stage(self) -> Stage:
        return self.application.stage if self.application else Stage.saved

    @property
    def score(self) -> int | None:
        return self.match.score if self.match else None


def job_rows(s: Session, profile_id: int | None, job_id: int | None = None) -> list[JobRow]:
    stmt = (
        select(Job, Company, Match, Application)
        .join(Company, col(Company.id) == col(Job.company_id))
        .outerjoin(
            Match, and_(col(Match.job_id) == col(Job.id), col(Match.profile_id) == profile_id)
        )
        .outerjoin(Application, col(Application.job_id) == col(Job.id))
    )
    if job_id is not None:
        stmt = stmt.where(col(Job.id) == job_id)
    return [JobRow(*r) for r in s.exec(stmt).all()]


def filter_rows(
    rows: list[JobRow],
    q: str | None = None,
    stage: Stage | None = None,
    remote: str | None = None,
    min_score: int = 0,
) -> list[JobRow]:
    needle = q.lower() if q else None
    out = []
    for r in rows:
        if (
            needle
            and needle not in f"{r.job.title} {r.company.name} {' '.join(r.job.skills)}".lower()
        ):
            continue
        if stage and r.stage != stage:
            continue
        if remote and r.job.remote_policy != remote:
            continue
        if (r.score or 0) < min_score:
            continue
        out.append(r)
    return out


SORTS = {
    "score": lambda r: -(r.score if r.score is not None else -1),
    "recent": lambda r: -r.job.first_seen_at.timestamp(),
    "comp": lambda r: -(r.job.comp_max or 0),
}


def extractions_for(s: Session, job_id: int) -> list[Extraction]:
    stmt = select(Extraction).where(Extraction.job_id == job_id).order_by(col(Extraction.id).desc())
    return list(s.exec(stmt))


def events_for(s: Session, application_id: int) -> list[ApplicationEvent]:
    stmt = (
        select(ApplicationEvent)
        .where(ApplicationEvent.application_id == application_id)
        .order_by(col(ApplicationEvent.id).desc())
    )
    return list(s.exec(stmt))
