"""add job enrichments table

Revision ID: 003_job_enrichments
Revises: 002_embeddings
Create Date: 2026-09-02

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_job_enrichments"
down_revision: str | None = "002_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_enrichments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("canonical_id", sa.String(length=64), nullable=False),
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("enrichment_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["canonical_id"], ["canonical_jobs.canonical_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["candidate_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "canonical_id",
            "profile_id",
            "model_name",
            "prompt_version",
            name="uq_job_enrichments_lookup",
        ),
    )
    op.create_index(
        "ix_job_enrichments_canonical_id", "job_enrichments", ["canonical_id"], unique=False
    )
    op.create_index(
        "ix_job_enrichments_profile_id", "job_enrichments", ["profile_id"], unique=False
    )
    op.create_index(
        "ix_job_enrichments_model_name", "job_enrichments", ["model_name"], unique=False
    )
    op.create_index(
        "ix_job_enrichments_prompt_version", "job_enrichments", ["prompt_version"], unique=False
    )
    op.create_index(
        "ix_job_enrichments_content_hash", "job_enrichments", ["content_hash"], unique=False
    )
    op.create_index(
        "ix_job_enrichments_lookup",
        "job_enrichments",
        ["canonical_id", "profile_id", "model_name", "prompt_version"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("job_enrichments")
