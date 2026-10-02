"""0015_job_industry: plain-language industry on each job, for the Job
Search filter. Filled at ingestion; existing rows are backfilled by the
job poller. Additive only.

Revision ID: 0015_job_industry
Revises: 0014_document_storage
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_job_industry"
down_revision = "0014_document_storage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("industry", sa.String(80), nullable=True))
    op.create_index(
        "idx_jobs_industry_active", "jobs", ["industry"], postgresql_where=sa.text("is_active = true")
    )


def downgrade() -> None:
    op.drop_index("idx_jobs_industry_active", table_name="jobs")
    op.drop_column("jobs", "industry")
