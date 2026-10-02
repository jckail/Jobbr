"""Read-side queries. One place owns the Job⋈Company⟕Match⟕Application join."""

from dataclasses import dataclass

from sqlalchemy import and_, func
from sqlmodel import Session, col, select

from .models import (
    Application,
    ApplicationEvent,
    Company,
    Extraction,
    Job,
    Match,
    ProfileRevision,
    ProfileRevisionHead,
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
            Match,
            and_(col(Match.job_id) == col(Job.id), col(Match.profile_id) == profile_id),
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


def profile_revision_head(s: Session, profile_id: int) -> ProfileRevisionHead | None:
    head = s.get(ProfileRevisionHead, profile_id)
    if head is not None:
        s.refresh(head)
    return head


def profile_revision(s: Session, profile_id: int, revision_id: int) -> ProfileRevision | None:
    return s.exec(
        select(ProfileRevision).where(
            ProfileRevision.profile_id == profile_id, ProfileRevision.id == revision_id
        )
    ).first()


def profile_revision_count(s: Session, profile_id: int) -> int:
    return s.exec(
        select(func.count())
        .select_from(ProfileRevision)
        .where(ProfileRevision.profile_id == profile_id)
    ).one()


def profile_revisions(s: Session, profile_id: int, limit: int) -> list[ProfileRevision]:
    return list(
        s.exec(
            select(ProfileRevision)
            .where(ProfileRevision.profile_id == profile_id)
            .order_by(col(ProfileRevision.saved_at).desc(), col(ProfileRevision.id).desc())
            .limit(limit)
        ).all()
    )
