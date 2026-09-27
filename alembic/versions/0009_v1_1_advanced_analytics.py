"""0009_v1_1_advanced_analytics: recruiter engagement, funnel, interview
conversion breakdown, source performance, and career progression tables.
See ai-job-hunter-advanced-analytics.md. Additive only.

Revision ID: 0009_v1_1_advanced_analytics
Revises: 0008_v1_1_job_discovery
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0009_v1_1_advanced_analytics"
down_revision = "0008_v1_1_job_discovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Section 2: funnel top-of-funnel events
    op.create_table(
        "job_engagement_events",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("profile_id", pg.UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", pg.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("event_type IN ('scored', 'viewed', 'saved')", name="ck_job_engagement_event_type"),
    )
    op.create_index(
        "idx_job_engagement_profile_type", "job_engagement_events", ["profile_id", "event_type", "occurred_at"]
    )

    # Section 1: recruiter engagement
    op.create_table(
        "recruiter_engagement_snapshots",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("profile_id", pg.UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("emails_sent", sa.Integer, server_default="0"),
        sa.Column("emails_opened", sa.Integer, server_default="0"),
        sa.Column("emails_clicked", sa.Integer, server_default="0"),
        sa.Column("emails_replied", sa.Integer, server_default="0"),
        sa.Column("interview_requests", sa.Integer, server_default="0"),
        sa.Column("avg_hours_to_first_response", sa.Numeric(8, 2)),
        sa.Column("breakdown_by_tone", pg.JSONB),
        sa.Column("top_engaged_companies", pg.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "profile_id", "period_start", "period_end", name="uq_recruiter_engagement_profile_period"
        ),
    )

    # Section 2: funnel snapshots
    op.create_table(
        "funnel_snapshots",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("profile_id", pg.UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("discovered_count", sa.Integer, server_default="0"),
        sa.Column("viewed_count", sa.Integer, server_default="0"),
        sa.Column("saved_count", sa.Integer, server_default="0"),
        sa.Column("applying_count", sa.Integer, server_default="0"),
        sa.Column("submitted_count", sa.Integer, server_default="0"),
        sa.Column("screening_count", sa.Integer, server_default="0"),
        sa.Column("interview_count", sa.Integer, server_default="0"),
        sa.Column("offer_count", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("profile_id", "period_start", "period_end", name="uq_funnel_snapshots_profile_period"),
    )

    # Section 3: interview conversion breakdown columns on the existing table
    op.add_column("analytics_snapshots", sa.Column("breakdown_by_cv_variant", pg.JSONB))
    op.add_column("analytics_snapshots", sa.Column("breakdown_by_match_score_band", pg.JSONB))
    op.add_column("analytics_snapshots", sa.Column("avg_days_in_screening", sa.Numeric(6, 2)))

    # Section 4: source performance
    op.create_table(
        "source_performance_snapshots",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("profile_id", pg.UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE")),
        sa.Column("source_id", pg.UUID(as_uuid=True), sa.ForeignKey("job_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("applications_submitted", sa.Integer, server_default="0"),
        sa.Column("interview_rate", sa.Numeric(5, 2)),
        sa.Column("avg_match_score", sa.Numeric(5, 2)),
        sa.Column("hidden_gem_ratio", sa.Numeric(5, 2)),
        sa.Column("avg_hours_to_response", sa.Numeric(8, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "profile_id", "source_id", "period_start", "period_end",
            name="uq_source_performance_profile_source_period",
        ),
    )

    # Section 5: career progression
    op.create_table(
        "career_progression_snapshots",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("profile_id", pg.UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("career_track_id", pg.UUID(as_uuid=True), sa.ForeignKey("career_tracks.id", ondelete="SET NULL")),
        sa.Column("period_month", sa.Date, nullable=False),
        sa.Column("avg_match_score", sa.Numeric(5, 2)),
        sa.Column("top_closing_skill_gaps", pg.JSONB),
        sa.Column("avg_salary_matched_min", sa.Integer),
        sa.Column("avg_salary_matched_max", sa.Integer),
        sa.Column("interview_rate", sa.Numeric(5, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "profile_id", "career_track_id", "period_month", name="uq_career_progression_profile_track_month"
        ),
    )


def downgrade() -> None:
    op.drop_table("career_progression_snapshots")
    op.drop_table("source_performance_snapshots")
    op.drop_column("analytics_snapshots", "avg_days_in_screening")
    op.drop_column("analytics_snapshots", "breakdown_by_match_score_band")
    op.drop_column("analytics_snapshots", "breakdown_by_cv_variant")
    op.drop_table("funnel_snapshots")
    op.drop_table("recruiter_engagement_snapshots")
    op.drop_index("idx_job_engagement_profile_type", table_name="job_engagement_events")
    op.drop_table("job_engagement_events")
