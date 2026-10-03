"""0017_entry_level_and_cv_builder: jobs.opportunity_type / jobs.entry_level
(learnerships, internships, "no experience needed" filter) and
profiles.cv_builder (the first-timer CV builder's saved answers). Additive.

Revision ID: 0017_entry_level_and_cv_builder
Revises: 0016_email_auth
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0017_entry_level_and_cv_builder"
down_revision = "0016_email_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("opportunity_type", sa.String(20), nullable=True))
    # NULL = not classified yet (the job poller fills these in)
    op.add_column("jobs", sa.Column("entry_level", sa.Boolean, nullable=True))
    op.create_index("idx_jobs_entry_level_active", "jobs", ["entry_level", "opportunity_type"],
                    postgresql_where=sa.text("is_active = true"))
    op.add_column("profiles", sa.Column("cv_builder", postgresql.JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("profiles", "cv_builder")
    op.drop_index("idx_jobs_entry_level_active", table_name="jobs")
    op.drop_column("jobs", "entry_level")
    op.drop_column("jobs", "opportunity_type")
