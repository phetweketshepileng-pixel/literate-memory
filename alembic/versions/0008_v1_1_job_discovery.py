"""0008_v1_1_job_discovery: job_source_references table, supporting
cross-source deduplication in the Job Discovery Engine (see
job-discovery-architecture.md section 5.2). Additive only.

Revision ID: 0008_v1_1_job_discovery
Revises: 0007_v1_1_activity_partition
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0008_v1_1_job_discovery"
down_revision = "0007_v1_1_activity_partition"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "job_sources",
        sa.Column("config", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "job_sources", sa.Column("poll_frequency_minutes", sa.Integer, server_default="120")
    )

    op.create_table(
        "job_source_references",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("job_id", pg.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "source_id", pg.UUID(as_uuid=True), sa.ForeignKey("job_sources.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("external_id", sa.String(255)),
        sa.Column("apply_url", sa.String(1000)),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("job_id", "source_id", name="uq_job_source_references_job_source"),
    )
    op.create_index("idx_job_source_references_job", "job_source_references", ["job_id"])

    # pg_trgm already enabled in 0002; `similarity()` used by the
    # deduplication service's description-similarity check depends on it.


def downgrade() -> None:
    op.drop_index("idx_job_source_references_job", table_name="job_source_references")
    op.drop_table("job_source_references")
    op.drop_column("job_sources", "poll_frequency_minutes")
    op.drop_column("job_sources", "config")
