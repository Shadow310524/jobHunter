"""create initial postgres persistence schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-09-02

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Candidate Profiles
    op.create_table(
        "candidate_profiles",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("degree", sa.String(length=255), nullable=False),
        sa.Column("graduation_year", sa.Integer(), nullable=False),
        sa.Column("cgpa", sa.Float(), nullable=False),
        sa.Column("current_role", sa.String(length=255), nullable=False),
        sa.Column("company_internship", sa.String(length=255), nullable=False),
        sa.Column("internship_duration", sa.String(length=255), nullable=False),
        sa.Column("core_skills", sa.JSON(), nullable=False),
        sa.Column("secondary_skills", sa.JSON(), nullable=False),
        sa.Column("target_roles", sa.JSON(), nullable=False),
        sa.Column("primary_locations", sa.JSON(), nullable=False),
        sa.Column("secondary_locations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. Canonical Jobs
    op.create_table(
        "canonical_jobs",
        sa.Column("canonical_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("secondary_locations", sa.JSON(), nullable=False),
        sa.Column("work_mode", sa.String(length=32), nullable=False),
        sa.Column("is_remote", sa.Boolean(), nullable=False),
        sa.Column("employment_type", sa.String(length=64), nullable=True),
        sa.Column("department", sa.String(length=255), nullable=True),
        sa.Column("posted_date", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("salary", sa.JSON(), nullable=True),
        sa.Column("raw_experience_text", sa.Text(), nullable=True),
        sa.Column("inferred_experience_level", sa.String(length=128), nullable=True),
        sa.Column("inferred_skills", sa.JSON(), nullable=False),
        sa.Column("application_urls", sa.JSON(), nullable=False),
        sa.Column("duplicate_candidate_group", sa.String(length=512), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("canonical_id"),
    )
    op.create_index(
        "ix_canonical_jobs_canonical_id", "canonical_jobs", ["canonical_id"], unique=False
    )
    op.create_index("ix_canonical_jobs_title", "canonical_jobs", ["title"], unique=False)
    op.create_index("ix_canonical_jobs_company", "canonical_jobs", ["company"], unique=False)
    op.create_index("ix_canonical_jobs_location", "canonical_jobs", ["location"], unique=False)
    op.create_index("ix_canonical_jobs_work_mode", "canonical_jobs", ["work_mode"], unique=False)
    op.create_index("ix_canonical_jobs_is_remote", "canonical_jobs", ["is_remote"], unique=False)
    op.create_index(
        "ix_canonical_jobs_duplicate_candidate_group",
        "canonical_jobs",
        ["duplicate_candidate_group"],
        unique=False,
    )
    op.create_index(
        "ix_canonical_jobs_company_title", "canonical_jobs", ["company", "title"], unique=False
    )
    op.create_index(
        "ix_canonical_jobs_location_work_mode",
        "canonical_jobs",
        ["location", "work_mode"],
        unique=False,
    )

    # 3. Source Provenance
    op.create_table(
        "source_provenance",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("canonical_id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_job_id", sa.String(length=255), nullable=False),
        sa.Column("job_url", sa.Text(), nullable=False),
        sa.Column("official_application_url", sa.Text(), nullable=False),
        sa.Column("posted_date", sa.String(length=64), nullable=True),
        sa.Column("raw_metadata", sa.JSON(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["canonical_id"], ["canonical_jobs.canonical_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "canonical_id", "source", "source_job_id", name="uq_canonical_source_job_id"
        ),
    )
    op.create_index(
        "ix_source_provenance_canonical_id", "source_provenance", ["canonical_id"], unique=False
    )
    op.create_index("ix_source_provenance_source", "source_provenance", ["source"], unique=False)
    op.create_index(
        "ix_source_provenance_source_job_id", "source_provenance", ["source_job_id"], unique=False
    )
    op.create_index(
        "ix_source_provenance_lookup",
        "source_provenance",
        ["source", "source_job_id"],
        unique=False,
    )

    # 4. Job Match Scores
    op.create_table(
        "job_match_scores",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("canonical_id", sa.String(length=64), nullable=False),
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("recommendation", sa.String(length=16), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("role_score", sa.Float(), nullable=False),
        sa.Column("technical_score", sa.Float(), nullable=False),
        sa.Column("experience_score", sa.Float(), nullable=False),
        sa.Column("location_score", sa.Float(), nullable=False),
        sa.Column("matched_skills", sa.JSON(), nullable=False),
        sa.Column("missing_skills", sa.JSON(), nullable=False),
        sa.Column("matched_role_keywords", sa.JSON(), nullable=False),
        sa.Column("experience_eligible", sa.Boolean(), nullable=False),
        sa.Column("location_eligible", sa.Boolean(), nullable=False),
        sa.Column("score_reasons", sa.JSON(), nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["canonical_id"], ["canonical_jobs.canonical_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["candidate_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_id", "profile_id", name="uq_canonical_job_match_profile"),
    )
    op.create_index(
        "ix_job_match_scores_canonical_id", "job_match_scores", ["canonical_id"], unique=False
    )
    op.create_index(
        "ix_job_match_scores_profile_id", "job_match_scores", ["profile_id"], unique=False
    )
    op.create_index(
        "ix_job_match_scores_recommendation", "job_match_scores", ["recommendation"], unique=False
    )
    op.create_index(
        "ix_job_match_scores_overall_score", "job_match_scores", ["overall_score"], unique=False
    )
    op.create_index(
        "ix_job_match_scores_recommendation_score",
        "job_match_scores",
        ["recommendation", "overall_score"],
        unique=False,
    )

    # 5. Applications
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("canonical_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["canonical_id"], ["canonical_jobs.canonical_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_id"),
    )
    op.create_index("ix_applications_status", "applications", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("applications")
    op.drop_table("job_match_scores")
    op.drop_table("source_provenance")
    op.drop_table("canonical_jobs")
    op.drop_table("candidate_profiles")
