"""0012_interview_prep: interview_prep_sessions, interview_prep_answers.
Additive only.

Revision ID: 0012_interview_prep
Revises: 0011_recruiter_intelligence
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0012_interview_prep"
down_revision = "0011_recruiter_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_prep_sessions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("profile_id", pg.UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_domain", sa.String(30), nullable=False),
        sa.Column("target_domain", sa.String(30), nullable=False),
        sa.Column("readiness_score", sa.Integer),
        sa.Column("weak_competencies", pg.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_interview_prep_sessions_profile", "interview_prep_sessions", ["profile_id", "created_at"])

    op.create_table(
        "interview_prep_answers",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column(
            "session_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("interview_prep_sessions.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("question_type", sa.String(20), nullable=False),
        sa.Column("target_competency", sa.String(255)),
        sa.Column("answer_text", sa.Text),
        sa.Column("star_score", sa.Integer),
        sa.Column("technical_correct", sa.Boolean),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("question_type IN ('behavioral','technical')", name="ck_interview_prep_answers_type"),
    )
    op.create_index("idx_interview_prep_answers_session", "interview_prep_answers", ["session_id"])


def downgrade() -> None:
    op.drop_index("idx_interview_prep_answers_session", table_name="interview_prep_answers")
    op.drop_table("interview_prep_answers")
    op.drop_index("idx_interview_prep_sessions_profile", table_name="interview_prep_sessions")
    op.drop_table("interview_prep_sessions")
