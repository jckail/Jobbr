"""Frozen schema expected by migration 0001_v2; do not edit with model changes."""

import sqlalchemy as sa

metadata = sa.MetaData()

company = sa.Table(
    "company",
    metadata,
    sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
    sa.Column("name", sa.String(), nullable=False, primary_key=False),
    sa.Column("domain", sa.String(), nullable=True, primary_key=False),
    sa.Column("industry", sa.String(), nullable=True, primary_key=False),
    sa.Column("created_at", sa.DateTime(), nullable=False, primary_key=False),
)
sa.Index("ix_company_name", company.c.name, unique=True)

profile = sa.Table(
    "profile",
    metadata,
    sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
    sa.Column("name", sa.String(), nullable=False, primary_key=False),
    sa.Column("headline", sa.String(), nullable=True, primary_key=False),
    sa.Column("resume_text", sa.String(), nullable=False, primary_key=False),
    sa.Column("skills", sa.JSON(), nullable=True, primary_key=False),
    sa.Column("years_experience", sa.Integer(), nullable=True, primary_key=False),
    sa.Column(
        "seniority",
        sa.Enum(
            "intern",
            "junior",
            "mid",
            "senior",
            "staff",
            "principal",
            "manager",
            "director",
            "executive",
            "unknown",
            name="seniority",
        ),
        nullable=False,
        primary_key=False,
    ),
    sa.Column("target_titles", sa.JSON(), nullable=True, primary_key=False),
    sa.Column("locations", sa.JSON(), nullable=True, primary_key=False),
    sa.Column(
        "remote_pref",
        sa.Enum("remote", "hybrid", "onsite", "unknown", name="remotepolicy"),
        nullable=False,
        primary_key=False,
    ),
    sa.Column("min_comp", sa.Integer(), nullable=True, primary_key=False),
    sa.Column("updated_at", sa.DateTime(), nullable=False, primary_key=False),
)

job = sa.Table(
    "job",
    metadata,
    sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
    sa.Column("company_id", sa.Integer(), nullable=False, primary_key=False),
    sa.Column("url", sa.String(), nullable=True, primary_key=False),
    sa.Column("title", sa.String(), nullable=False, primary_key=False),
    sa.Column(
        "status",
        sa.Enum("active", "closed", "unknown", name="jobstatus"),
        nullable=False,
        primary_key=False,
    ),
    sa.Column("department", sa.String(), nullable=True, primary_key=False),
    sa.Column(
        "seniority",
        sa.Enum(
            "intern",
            "junior",
            "mid",
            "senior",
            "staff",
            "principal",
            "manager",
            "director",
            "executive",
            "unknown",
            name="seniority",
        ),
        nullable=False,
        primary_key=False,
    ),
    sa.Column("employment_type", sa.String(), nullable=True, primary_key=False),
    sa.Column(
        "remote_policy",
        sa.Enum("remote", "hybrid", "onsite", "unknown", name="remotepolicy"),
        nullable=False,
        primary_key=False,
    ),
    sa.Column("locations", sa.JSON(), nullable=True, primary_key=False),
    sa.Column("comp_min", sa.Integer(), nullable=True, primary_key=False),
    sa.Column("comp_max", sa.Integer(), nullable=True, primary_key=False),
    sa.Column("comp_currency", sa.String(), nullable=False, primary_key=False),
    sa.Column("years_experience_min", sa.Integer(), nullable=True, primary_key=False),
    sa.Column("summary", sa.String(), nullable=True, primary_key=False),
    sa.Column("responsibilities", sa.JSON(), nullable=True, primary_key=False),
    sa.Column("qualifications", sa.JSON(), nullable=True, primary_key=False),
    sa.Column("skills", sa.JSON(), nullable=True, primary_key=False),
    sa.Column("nice_to_have", sa.JSON(), nullable=True, primary_key=False),
    sa.Column("benefits", sa.JSON(), nullable=True, primary_key=False),
    sa.Column("ai_take", sa.String(), nullable=True, primary_key=False),
    sa.Column("posted_at", sa.DateTime(), nullable=True, primary_key=False),
    sa.Column("content_hash", sa.String(), nullable=True, primary_key=False),
    sa.Column("raw_text", sa.String(), nullable=True, primary_key=False),
    sa.Column("first_seen_at", sa.DateTime(), nullable=False, primary_key=False),
    sa.Column("last_seen_at", sa.DateTime(), nullable=False, primary_key=False),
    sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
)
sa.Index("ix_job_company_id", job.c.company_id, unique=False)
sa.Index("ix_job_url", job.c.url, unique=False)

application = sa.Table(
    "application",
    metadata,
    sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
    sa.Column("job_id", sa.Integer(), nullable=False, primary_key=False),
    sa.Column(
        "stage",
        sa.Enum(
            "saved",
            "applied",
            "screen",
            "interview",
            "offer",
            "rejected",
            "withdrawn",
            name="stage",
        ),
        nullable=False,
        primary_key=False,
    ),
    sa.Column("notes", sa.String(), nullable=False, primary_key=False),
    sa.Column("applied_at", sa.DateTime(), nullable=True, primary_key=False),
    sa.Column("next_step_at", sa.DateTime(), nullable=True, primary_key=False),
    sa.Column("updated_at", sa.DateTime(), nullable=False, primary_key=False),
    sa.ForeignKeyConstraint(["job_id"], ["job.id"]),
)
sa.Index("ix_application_job_id", application.c.job_id, unique=True)

extraction = sa.Table(
    "extraction",
    metadata,
    sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
    sa.Column("job_id", sa.Integer(), nullable=True, primary_key=False),
    sa.Column("url", sa.String(), nullable=True, primary_key=False),
    sa.Column(
        "method",
        sa.Enum("llm", "jsonld", "heuristic", name="extractmethod"),
        nullable=False,
        primary_key=False,
    ),
    sa.Column("model", sa.String(), nullable=True, primary_key=False),
    sa.Column("input_tokens", sa.Integer(), nullable=False, primary_key=False),
    sa.Column("output_tokens", sa.Integer(), nullable=False, primary_key=False),
    sa.Column("cost_usd", sa.Float(), nullable=False, primary_key=False),
    sa.Column("latency_ms", sa.Integer(), nullable=False, primary_key=False),
    sa.Column("ok", sa.Boolean(), nullable=False, primary_key=False),
    sa.Column("error", sa.String(), nullable=True, primary_key=False),
    sa.Column("created_at", sa.DateTime(), nullable=False, primary_key=False),
    sa.ForeignKeyConstraint(["job_id"], ["job.id"]),
)
sa.Index("ix_extraction_job_id", extraction.c.job_id, unique=False)

match = sa.Table(
    "match",
    metadata,
    sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
    sa.Column("job_id", sa.Integer(), nullable=False, primary_key=False),
    sa.Column("profile_id", sa.Integer(), nullable=False, primary_key=False),
    sa.Column("score", sa.Integer(), nullable=False, primary_key=False),
    sa.Column("breakdown", sa.JSON(), nullable=True, primary_key=False),
    sa.Column("matched_skills", sa.JSON(), nullable=True, primary_key=False),
    sa.Column("missing_skills", sa.JSON(), nullable=True, primary_key=False),
    sa.Column("rationale", sa.String(), nullable=True, primary_key=False),
    sa.Column("created_at", sa.DateTime(), nullable=False, primary_key=False),
    sa.UniqueConstraint("job_id", "profile_id"),
    sa.ForeignKeyConstraint(["job_id"], ["job.id"]),
    sa.ForeignKeyConstraint(["profile_id"], ["profile.id"]),
)
sa.Index("ix_match_job_id", match.c.job_id, unique=False)
sa.Index("ix_match_profile_id", match.c.profile_id, unique=False)

applicationevent = sa.Table(
    "applicationevent",
    metadata,
    sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
    sa.Column("application_id", sa.Integer(), nullable=False, primary_key=False),
    sa.Column(
        "from_stage",
        sa.Enum(
            "saved",
            "applied",
            "screen",
            "interview",
            "offer",
            "rejected",
            "withdrawn",
            name="stage",
        ),
        nullable=True,
        primary_key=False,
    ),
    sa.Column(
        "to_stage",
        sa.Enum(
            "saved",
            "applied",
            "screen",
            "interview",
            "offer",
            "rejected",
            "withdrawn",
            name="stage",
        ),
        nullable=False,
        primary_key=False,
    ),
    sa.Column("note", sa.String(), nullable=True, primary_key=False),
    sa.Column("at", sa.DateTime(), nullable=False, primary_key=False),
    sa.ForeignKeyConstraint(["application_id"], ["application.id"]),
)
sa.Index("ix_applicationevent_application_id", applicationevent.c.application_id, unique=False)
