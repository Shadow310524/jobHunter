"""add pgvector and embedding tables

Revision ID: 002_embeddings
Revises: 001_initial_schema
Create Date: 2026-09-02

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_embeddings"
down_revision: str | None = "001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Job Embeddings
    op.create_table(
        "job_embeddings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("canonical_id", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["canonical_id"], ["canonical_jobs.canonical_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "canonical_id",
            "model_name",
            "model_version",
            name="uq_job_embeddings_canonical_model_version",
        ),
    )
    op.create_index(
        "ix_job_embeddings_canonical_id", "job_embeddings", ["canonical_id"], unique=False
    )
    op.create_index("ix_job_embeddings_model_name", "job_embeddings", ["model_name"], unique=False)
    op.create_index(
        "ix_job_embeddings_content_hash", "job_embeddings", ["content_hash"], unique=False
    )
    op.create_index(
        "ix_job_embeddings_lookup",
        "job_embeddings",
        ["canonical_id", "model_name", "model_version"],
        unique=False,
    )

    # 2. Profile Embeddings
    op.create_table(
        "profile_embeddings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["candidate_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id", "model_name", "model_version", name="uq_profile_embeddings_model_version"
        ),
    )
    op.create_index(
        "ix_profile_embeddings_profile_id", "profile_embeddings", ["profile_id"], unique=False
    )
    op.create_index(
        "ix_profile_embeddings_model_name", "profile_embeddings", ["model_name"], unique=False
    )
    op.create_index(
        "ix_profile_embeddings_content_hash", "profile_embeddings", ["content_hash"], unique=False
    )

    # 3. Add hybrid score columns to job_match_scores
    op.add_column("job_match_scores", sa.Column("deterministic_score", sa.Float(), nullable=True))
    op.add_column("job_match_scores", sa.Column("semantic_score", sa.Float(), nullable=True))
    op.add_column("job_match_scores", sa.Column("semantic_similarity", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("job_match_scores", "semantic_similarity")
    op.drop_column("job_match_scores", "semantic_score")
    op.drop_column("job_match_scores", "deterministic_score")
    op.drop_table("profile_embeddings")
    op.drop_table("job_embeddings")
