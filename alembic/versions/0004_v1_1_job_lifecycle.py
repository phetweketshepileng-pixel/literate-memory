"""0004_v1_1_job_lifecycle: jobs.is_active / closed_at (V1.1 review,
scalability section — "no archival/retention policy on jobs"), plus the
partial indexes that make filtered search on active listings fast.

Revision ID: 0004_v1_1_job_lifecycle
Revises: 0003_v1_1_security
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_v1_1_job_lifecycle"
down_revision = "0003_v1_1_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs", sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true"))
    )
    op.add_column("jobs", sa.Column("closed_at", sa.DateTime(timezone=True)))

    op.create_index(
        "idx_jobs_active_filters", "jobs", ["is_remote", "location", "date_posted"],
        postgresql_where="is_active = true",
    )
    op.create_index(
        "idx_jobs_industry_date", "jobs", ["company", "date_posted"],
        postgresql_where="is_active = true",
    )
    op.create_index(
        "idx_jobs_hidden_gem", "jobs", ["is_hidden_gem"],
        postgresql_where="is_hidden_gem = true AND is_active = true",
    )


def downgrade() -> None:
    op.drop_index("idx_jobs_hidden_gem", table_name="jobs")
    op.drop_index("idx_jobs_industry_date", table_name="jobs")
    op.drop_index("idx_jobs_active_filters", table_name="jobs")
    op.drop_column("jobs", "closed_at")
    op.drop_column("jobs", "is_active")
