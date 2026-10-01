"""Realistic demo data so the hosted UI is alive on first load (JOBBR_SEED_DEMO=1)."""

from datetime import timedelta

from sqlmodel import Session

from .models import (Application, ApplicationEvent, Company, ExtractMethod, Extraction, Job,
                     RemotePolicy, Seniority, Stage, utcnow)
from .schemas import ProfileIn
from .services import rematch, save_profile

R, H, ONS = RemotePolicy.remote, RemotePolicy.hybrid, RemotePolicy.onsite
JOBS = [
    ("Anthropic", "AI", "Software Engineer, Inference", Seniority.senior, R, ["San Francisco, CA"], 320000, 485000,
     ["python", "kubernetes", "rust", "distributed systems", "linux"], ["pytorch", "gcp"], Stage.interview, 1),
    ("Stripe", "Fintech", "Staff Engineer, Data Platform", Seniority.staff, H, ["Seattle, WA", "New York, NY"], 290000, 420000,
     ["python", "spark", "kafka", "sql", "airflow", "data modeling"], ["scala", "aws"], Stage.applied, 2),
    ("Datadog", "Observability", "Senior Backend Engineer", Seniority.senior, H, ["New York, NY"], 190000, 260000,
     ["go", "kubernetes", "kafka", "postgres", "observability"], ["rust", "terraform"], Stage.saved, 2),
    ("Vercel", "Developer tools", "Senior Full-Stack Engineer", Seniority.senior, R, ["Remote, US"], 180000, 250000,
     ["typescript", "react", "next.js", "node.js", "graphql"], ["rust", "postgres"], Stage.screen, 3),
    ("Snowflake", "Data", "Senior Analytics Engineer", Seniority.senior, H, ["Bozeman, MT", "San Mateo, CA"], 175000, 245000,
     ["sql", "snowflake", "dbt", "python", "data modeling"], ["airflow", "looker"], Stage.saved, 4),
    ("Linear", "Productivity", "Product Engineer", Seniority.mid, R, ["Remote, EU/US"], 140000, 200000,
     ["typescript", "react", "graphql", "postgres"], ["node.js"], Stage.saved, 5),
    ("OpenAI", "AI", "Analytics Data Engineer, Applied", Seniority.senior, ONS, ["San Francisco, CA"], 245000, 385000,
     ["python", "scala", "java", "spark", "flink", "airflow", "s3"], ["hadoop"], Stage.rejected, 6),
    ("Cloudflare", "Infrastructure", "Systems Engineer, Edge", Seniority.senior, H, ["Austin, TX", "London, UK"], 170000, 230000,
     ["rust", "go", "linux", "distributed systems", "c++"], ["kubernetes"], Stage.saved, 7),
    ("Ramp", "Fintech", "Senior ML Engineer", Seniority.senior, H, ["New York, NY"], 210000, 290000,
     ["python", "machine learning", "pytorch", "sql", "mlops", "llm"], ["spark", "aws"], Stage.applied, 8),
    ("Notion", "Productivity", "Data Engineer", Seniority.mid, H, ["San Francisco, CA", "New York, NY"], 160000, 215000,
     ["python", "sql", "spark", "kafka", "airflow", "dbt"], ["snowflake"], Stage.offer, 10),
]

PROFILE = ProfileIn(
    name="Jordan", headline="Data & AI engineer",
    resume_text=("Senior data engineer. Python, SQL, Spark, Airflow, dbt, Snowflake, Kafka, FastAPI, Postgres, "
                 "Docker, Kubernetes, AWS, Terraform, LLM and RAG pipelines with LangChain, machine learning."),
    years_experience=8, seniority=Seniority.senior, target_titles=["Data Engineer", "ML Engineer"],
    locations=["Seattle, WA", "New York, NY"], remote_pref=H, min_comp=190000,
)


def seed(s: Session) -> None:
    save_profile(s, PROFILE)
    now = utcnow()
    for co, ind, title, sen, rp, locs, lo, hi, req, nice, stage, days in JOBS:
        c = s.query(Company).filter_by(name=co).first() or Company(name=co, industry=ind)
        s.add(c)
        s.flush()
        j = Job(company_id=c.id, title=title, seniority=sen, remote_policy=rp, locations=locs,
                comp_min=lo, comp_max=hi, skills=req, nice_to_have=nice, employment_type="Full-time",
                summary=f"{title} at {co}: own core systems end to end and ship with a small senior team.",
                responsibilities=["Design and operate production services", "Partner with product and research",
                                  "Raise the engineering bar through reviews and mentoring"],
                qualifications=[f"Strong {req[0]} fundamentals", "Track record shipping at scale"],
                ai_take="Good fit for a hands-on senior engineer who likes ambiguity.",
                first_seen_at=now - timedelta(days=days), last_seen_at=now - timedelta(days=days),
                url=f"https://example.com/jobs/{co.lower()}/{title.lower().replace(' ', '-').replace(',', '')}")
        s.add(j)
        s.flush()
        s.add(Extraction(job_id=j.id, url=j.url, method=ExtractMethod.jsonld, latency_ms=40))
        a = Application(job_id=j.id, stage=stage, applied_at=None if stage == Stage.saved else now - timedelta(days=days))
        s.add(a)
        s.flush()
        s.add(ApplicationEvent(application_id=a.id, to_stage=Stage.saved, at=now - timedelta(days=days)))
        if stage != Stage.saved:
            s.add(ApplicationEvent(application_id=a.id, from_stage=Stage.saved, to_stage=stage,
                                   at=now - timedelta(days=max(days - 1, 0))))
        rematch(s, j)
    s.commit()
