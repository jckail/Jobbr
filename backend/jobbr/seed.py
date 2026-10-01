"""Realistic demo data so the hosted UI is alive on first load (JOBBR_SEED_DEMO=1)."""

from datetime import timedelta
from typing import NamedTuple

from sqlmodel import Session, select

from .models import (
    Application,
    ApplicationEvent,
    Company,
    Extraction,
    ExtractMethod,
    Job,
    RemotePolicy,
    Seniority,
    Stage,
    pk,
    utcnow,
)
from .schemas import ProfileIn
from .services import rematch, save_profile

R, H, ONS = RemotePolicy.remote, RemotePolicy.hybrid, RemotePolicy.onsite


class Demo(NamedTuple):
    company: str
    industry: str
    title: str
    seniority: Seniority
    remote: RemotePolicy
    locations: list[str]
    comp_min: int
    comp_max: int
    skills: list[str]
    nice_to_have: list[str]
    stage: Stage
    days_ago: int


_RAW = [
    (
        "Anthropic",
        "AI",
        "Software Engineer, Inference",
        Seniority.senior,
        R,
        ["San Francisco, CA"],
        320000,
        485000,
        ["python", "kubernetes", "rust", "distributed systems", "linux"],
        ["pytorch", "gcp"],
        Stage.interview,
        1,
    ),
    (
        "Stripe",
        "Fintech",
        "Staff Engineer, Data Platform",
        Seniority.staff,
        H,
        ["Seattle, WA", "New York, NY"],
        290000,
        420000,
        ["python", "spark", "kafka", "sql", "airflow", "data modeling"],
        ["scala", "aws"],
        Stage.applied,
        2,
    ),
    (
        "Datadog",
        "Observability",
        "Senior Backend Engineer",
        Seniority.senior,
        H,
        ["New York, NY"],
        190000,
        260000,
        ["go", "kubernetes", "kafka", "postgres", "observability"],
        ["rust", "terraform"],
        Stage.saved,
        2,
    ),
    (
        "Vercel",
        "Developer tools",
        "Senior Full-Stack Engineer",
        Seniority.senior,
        R,
        ["Remote, US"],
        180000,
        250000,
        ["typescript", "react", "next.js", "node.js", "graphql"],
        ["rust", "postgres"],
        Stage.screen,
        3,
    ),
    (
        "Snowflake",
        "Data",
        "Senior Analytics Engineer",
        Seniority.senior,
        H,
        ["Bozeman, MT", "San Mateo, CA"],
        175000,
        245000,
        ["sql", "snowflake", "dbt", "python", "data modeling"],
        ["airflow", "looker"],
        Stage.saved,
        4,
    ),
    (
        "Linear",
        "Productivity",
        "Product Engineer",
        Seniority.mid,
        R,
        ["Remote, EU/US"],
        140000,
        200000,
        ["typescript", "react", "graphql", "postgres"],
        ["node.js"],
        Stage.saved,
        5,
    ),
    (
        "OpenAI",
        "AI",
        "Analytics Data Engineer, Applied",
        Seniority.senior,
        ONS,
        ["San Francisco, CA"],
        245000,
        385000,
        ["python", "scala", "java", "spark", "flink", "airflow", "s3"],
        ["hadoop"],
        Stage.rejected,
        6,
    ),
    (
        "Cloudflare",
        "Infrastructure",
        "Systems Engineer, Edge",
        Seniority.senior,
        H,
        ["Austin, TX", "London, UK"],
        170000,
        230000,
        ["rust", "go", "linux", "distributed systems", "c++"],
        ["kubernetes"],
        Stage.saved,
        7,
    ),
    (
        "Ramp",
        "Fintech",
        "Senior ML Engineer",
        Seniority.senior,
        H,
        ["New York, NY"],
        210000,
        290000,
        ["python", "machine learning", "pytorch", "sql", "mlops", "llm"],
        ["spark", "aws"],
        Stage.applied,
        8,
    ),
    (
        "Notion",
        "Productivity",
        "Data Engineer",
        Seniority.mid,
        H,
        ["San Francisco, CA", "New York, NY"],
        160000,
        215000,
        ["python", "sql", "spark", "kafka", "airflow", "dbt"],
        ["snowflake"],
        Stage.offer,
        10,
    ),
]

JOBS = [Demo(*row) for row in _RAW]

PROFILE = ProfileIn(
    name="Jordan",
    headline="Data & AI engineer",
    resume_text=(
        "Senior data engineer. Python, SQL, Spark, Airflow, dbt, Snowflake, Kafka, FastAPI, "
        "Postgres, Docker, Kubernetes, AWS, Terraform, LLM and RAG pipelines with LangChain, "
        "machine learning."
    ),
    years_experience=8,
    seniority=Seniority.senior,
    target_titles=["Data Engineer", "ML Engineer"],
    locations=["Seattle, WA", "New York, NY"],
    remote_pref=H,
    min_comp=190000,
)


def seed(s: Session) -> None:
    save_profile(s, PROFILE)
    now = utcnow()
    for d in JOBS:
        company = s.exec(select(Company).where(Company.name == d.company)).first() or Company(
            name=d.company, industry=d.industry
        )
        s.add(company)
        s.flush()
        seen = now - timedelta(days=d.days_ago)
        slug = d.title.lower().replace(" ", "-").replace(",", "")
        job = Job(
            company_id=pk(company),
            title=d.title,
            seniority=d.seniority,
            remote_policy=d.remote,
            locations=d.locations,
            comp_min=d.comp_min,
            comp_max=d.comp_max,
            skills=d.skills,
            nice_to_have=d.nice_to_have,
            employment_type="Full-time",
            summary=f"{d.title} at {d.company}: own core systems end to end with a small team.",
            responsibilities=[
                "Design and operate production services",
                "Partner with product and research",
                "Raise the engineering bar through reviews and mentoring",
            ],
            qualifications=[f"Strong {d.skills[0]} fundamentals", "Track record shipping at scale"],
            ai_take="Good fit for a hands-on senior engineer who likes ambiguity.",
            first_seen_at=seen,
            last_seen_at=seen,
            url=f"https://example.com/jobs/{d.company.lower()}/{slug}",
        )
        s.add(job)
        s.flush()
        s.add(Extraction(job_id=pk(job), url=job.url, method=ExtractMethod.jsonld, latency_ms=40))
        app = Application(
            job_id=pk(job), stage=d.stage, applied_at=None if d.stage == Stage.saved else seen
        )
        s.add(app)
        s.flush()
        s.add(ApplicationEvent(application_id=pk(app), to_stage=Stage.saved, at=seen))
        if d.stage != Stage.saved:
            moved = now - timedelta(days=max(d.days_ago - 1, 0))
            s.add(
                ApplicationEvent(
                    application_id=pk(app), from_stage=Stage.saved, to_stage=d.stage, at=moved
                )
            )
        rematch(s, job)
    s.commit()
