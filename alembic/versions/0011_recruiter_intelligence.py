"""0011_recruiter_intelligence: recruiter_intelligence_snapshots,
company_intelligence_snapshots, profiles.contributes_to_pooled_analytics.
See ai-job-hunter-recruiter-intelligence.md sections 2-3. Additive only.

Revision ID: 0011_recruiter_intelligence
Revises: 0010_career_transition_engine
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0011_recruiter_intelligence"
down_revision = "0010_career_transition_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("contributes_to_pooled_analytics", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )
    op.add_column("profiles", sa.Column("primary_source_domain", sa.String(30)))

    op.create_table(
        "recruiter_intelligence_snapshots",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("recruiter_id", pg.UUID(as_uuid=True), sa.ForeignKey("recruiters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("postings_count", sa.Integer, server_default="0"),
        sa.Column("contributing_user_count", sa.Integer, nullable=False),
        sa.Column("response_rate", sa.Numeric(5, 2)),
        sa.Column("avg_hours_to_first_response", sa.Numeric(8, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "recruiter_id", "period_start", "period_end", name="uq_recruiter_intel_recruiter_period"
        ),
    )

    op.create_table(
        "company_intelligence_snapshots",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("contributing_user_count", sa.Integer, nullable=False),
        sa.Column("avg_turnaround_days", sa.Numeric(6, 2)),
        sa.Column("interview_rate_overall", sa.Numeric(5, 2)),
        sa.Column("interview_rate_by_source_domain", pg.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "company_name", "period_start", "period_end", name="uq_company_intel_name_period"
        ),
    )
    op.create_index("idx_company_intelligence_name", "company_intelligence_snapshots", ["company_name", "period_start"])


def downgrade() -> None:
    op.drop_index("idx_company_intelligence_name", table_name="company_intelligence_snapshots")
    op.drop_table("company_intelligence_snapshots")
    op.drop_table("recruiter_intelligence_snapshots")
    op.drop_column("profiles", "primary_source_domain")
    op.drop_column("profiles", "contributes_to_pooled_analytics")
