"""0006_v1_1_engagement: saved_searches + notifications (V1.1 review,
missing-features section — "no way to save a search and get notified"),
and career_tracks (multi-track profile support for users transitioning
across several target roles simultaneously).

Revision ID: 0006_v1_1_engagement
Revises: 0005_v1_1_governance
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0006_v1_1_engagement"
down_revision = "0005_v1_1_governance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_searches",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("profile_id", pg.UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255)),
        sa.Column("filters", pg.JSONB, nullable=False),
        sa.Column("alert_frequency", sa.String(20), server_default="daily"),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "alert_frequency IN ('instant','daily','weekly','off')", name="ck_saved_searches_frequency"
        ),
    )
    op.create_index("idx_saved_searches_profile", "saved_searches", ["profile_id"])
    op.create_index(
        "idx_saved_searches_due", "saved_searches", ["alert_frequency", "last_run_at"],
        postgresql_where="alert_frequency != 'off'",
    )

    op.create_table(
        "notifications",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("profile_id", pg.UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("payload", pg.JSONB),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "idx_notifications_profile_unread", "notifications", ["profile_id"],
        postgresql_where="read_at IS NULL",
    )

    op.create_table(
        "career_tracks",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("profile_id", pg.UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("track_name", sa.String(255), nullable=False),
        sa.Column("master_cv_document_id", pg.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="SET NULL")),
        sa.Column("priority", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("profile_id", "track_name", name="uq_career_tracks_profile_name"),
    )
    op.create_index("idx_career_tracks_profile", "career_tracks", ["profile_id"])

    # applications dashboard composite index, called out in the V1.1 review's
    # database-bottlenecks section
    op.create_index(
        "idx_applications_dashboard", "applications", ["profile_id", "stage", "applied_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_applications_dashboard", table_name="applications")
    op.drop_index("idx_career_tracks_profile", table_name="career_tracks")
    op.drop_table("career_tracks")
    op.drop_index("idx_notifications_profile_unread", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("idx_saved_searches_due", table_name="saved_searches")
    op.drop_index("idx_saved_searches_profile", table_name="saved_searches")
    op.drop_table("saved_searches")
