"""Initial Jobbr v2 schema, with verified adoption of unversioned v2 databases."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from jobbr.schema import verify_schema
from migrations.baseline import metadata

revision = "0001_v2"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if not op.get_context().as_sql:
        existing = set(sa.inspect(connection).get_table_names()) - {"alembic_version"}
        if existing:
            verify_schema(connection, metadata)
            return
    if connection.dialect.name == "postgresql":
        enum_types = {
            column.type.name: column.type
            for table in metadata.tables.values()
            for column in table.columns
            if isinstance(column.type, sa.Enum)
        }
        for enum_type in enum_types.values():
            enum_type.create(connection, checkfirst=not op.get_context().as_sql)

    op.create_table(
        "company",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("domain", sa.String(), nullable=True),
        sa.Column("industry", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_company_name"), "company", ["name"], unique=True)
    op.create_table(
        "profile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("headline", sa.String(), nullable=True),
        sa.Column("resume_text", sa.String(), nullable=False),
        sa.Column("skills", sa.JSON(), nullable=True),
        sa.Column("years_experience", sa.Integer(), nullable=True),
        sa.Column(
            "seniority",
            postgresql.ENUM(
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
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("target_titles", sa.JSON(), nullable=True),
        sa.Column("locations", sa.JSON(), nullable=True),
        sa.Column(
            "remote_pref",
            postgresql.ENUM(
                "remote", "hybrid", "onsite", "unknown", name="remotepolicy", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("min_comp", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "job",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("active", "closed", "unknown", name="jobstatus", create_type=False),
            nullable=False,
        ),
        sa.Column("department", sa.String(), nullable=True),
        sa.Column(
            "seniority",
            postgresql.ENUM(
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
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("employment_type", sa.String(), nullable=True),
        sa.Column(
            "remote_policy",
            postgresql.ENUM(
                "remote", "hybrid", "onsite", "unknown", name="remotepolicy", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("locations", sa.JSON(), nullable=True),
        sa.Column("comp_min", sa.Integer(), nullable=True),
        sa.Column("comp_max", sa.Integer(), nullable=True),
        sa.Column("comp_currency", sa.String(), nullable=False),
        sa.Column("years_experience_min", sa.Integer(), nullable=True),
        sa.Column("summary", sa.String(), nullable=True),
        sa.Column("responsibilities", sa.JSON(), nullable=True),
        sa.Column("qualifications", sa.JSON(), nullable=True),
        sa.Column("skills", sa.JSON(), nullable=True),
        sa.Column("nice_to_have", sa.JSON(), nullable=True),
        sa.Column("benefits", sa.JSON(), nullable=True),
        sa.Column("ai_take", sa.String(), nullable=True),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("content_hash", sa.String(), nullable=True),
        sa.Column("raw_text", sa.String(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["company.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_company_id"), "job", ["company_id"], unique=False)
    op.create_index(op.f("ix_job_url"), "job", ["url"], unique=False)
    op.create_table(
        "application",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column(
            "stage",
            postgresql.ENUM(
                "saved",
                "applied",
                "screen",
                "interview",
                "offer",
                "rejected",
                "withdrawn",
                name="stage",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.String(), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("next_step_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["job.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_application_job_id"), "application", ["job_id"], unique=True)
    op.create_table(
        "extraction",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column(
            "method",
            postgresql.ENUM("llm", "jsonld", "heuristic", name="extractmethod", create_type=False),
            nullable=False,
        ),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["job.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_extraction_job_id"), "extraction", ["job_id"], unique=False)
    op.create_table(
        "match",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("breakdown", sa.JSON(), nullable=True),
        sa.Column("matched_skills", sa.JSON(), nullable=True),
        sa.Column("missing_skills", sa.JSON(), nullable=True),
        sa.Column("rationale", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["job.id"],
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profile.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "profile_id"),
    )
    op.create_index(op.f("ix_match_job_id"), "match", ["job_id"], unique=False)
    op.create_index(op.f("ix_match_profile_id"), "match", ["profile_id"], unique=False)
    op.create_table(
        "applicationevent",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column(
            "from_stage",
            postgresql.ENUM(
                "saved",
                "applied",
                "screen",
                "interview",
                "offer",
                "rejected",
                "withdrawn",
                name="stage",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "to_stage",
            postgresql.ENUM(
                "saved",
                "applied",
                "screen",
                "interview",
                "offer",
                "rejected",
                "withdrawn",
                name="stage",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_applicationevent_application_id"),
        "applicationevent",
        ["application_id"],
        unique=False,
    )


def downgrade() -> None:
    raise RuntimeError("Initial migration downgrade is disabled to preserve job data.")
