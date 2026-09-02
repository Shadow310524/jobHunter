"""update applications table schema with hitl tracking fields

Revision ID: 004_applications_hitl
Revises: 003_job_enrichments
Create Date: 2026-09-02

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004_applications_hitl"
down_revision: str | None = "003_job_enrichments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "applications", sa.Column("interview_date", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("applications", sa.Column("human_feedback", sa.String(length=32), nullable=True))
    op.add_column("applications", sa.Column("events_log", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("applications", "events_log")
    op.drop_column("applications", "human_feedback")
    op.drop_column("applications", "interview_date")
