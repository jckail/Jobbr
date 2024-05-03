"""initial migration

Revision ID: 526e61e998b6
Revises: 
Create Date: 2024-05-03 17:03:46.433714

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "526e61e998b6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "app_ai",
        sa.Column(
            "model", sa.Enum("GPT3", "GPT4", "CLAUD3_OPUS", name="llm"), nullable=False
        ),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("user_id", sqlmodel.sql.sqltypes.GUID(), nullable=True),
        sa.Column("ai_context_id", sqlmodel.sql.sqltypes.GUID(), nullable=True),
        sa.Column("id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at_utc", sa.Integer(), nullable=False),
        sa.Column("updated_at_utc", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "app_ai_event",
        sa.Column("id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column("app_ai_id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column(
            "model", sa.Enum("GPT3", "GPT4", "CLAUD3_OPUS", name="llm"), nullable=False
        ),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("event_utc", sa.Integer(), nullable=False),
        sa.Column("estimated_tokens", sa.Integer(), nullable=True),
        sa.Column("file_source", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("messages", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("user_id", sqlmodel.sql.sqltypes.GUID(), nullable=True),
        sa.Column("user_event_id", sqlmodel.sql.sqltypes.GUID(), nullable=True),
        sa.Column("function_start_utc", sa.Integer(), nullable=True),
        sa.Column("response_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("stop_reason", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("stop_sequence", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("parsing_error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at_utc", sa.Integer(), nullable=False),
        sa.Column("updated_at_utc", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column(
        "stg_role",
        sa.Column("ai_event_id", sqlmodel.sql.sqltypes.GUID(), nullable=True),
    )
    op.add_column(
        "stg_role",
        sa.Column("specified_context", postgresql.ARRAY(sa.String()), nullable=True),
    )
    op.add_column(
        "stg_role", sa.Column("context_id", sqlmodel.sql.sqltypes.GUID(), nullable=True)
    )
    op.drop_column("stg_role", "file_source")
    op.drop_column("stg_role", "AIFunctionRun_id")
    op.drop_column("stg_role", "url")
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "stg_role", sa.Column("url", sa.VARCHAR(), autoincrement=False, nullable=True)
    )
    op.add_column(
        "stg_role",
        sa.Column("AIFunctionRun_id", sa.UUID(), autoincrement=False, nullable=False),
    )
    op.add_column(
        "stg_role",
        sa.Column("file_source", sa.VARCHAR(), autoincrement=False, nullable=True),
    )
    op.drop_column("stg_role", "context_id")
    op.drop_column("stg_role", "specified_context")
    op.drop_column("stg_role", "ai_event_id")
    op.drop_table("app_ai_event")
    op.drop_table("app_ai")
    # ### end Alembic commands ###
