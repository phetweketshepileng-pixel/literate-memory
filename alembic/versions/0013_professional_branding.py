"""0013_professional_branding: brand_profiles table. Additive only.

Revision ID: 0013_professional_branding
Revises: 0012_interview_prep
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0013_professional_branding"
down_revision = "0012_interview_prep"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "brand_profiles",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column(
            "profile_id", pg.UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False, unique=True,
        ),
        sa.Column("linkedin_headline", sa.String(220)),
        sa.Column("linkedin_summary", sa.Text),
        sa.Column("last_consistency_score", sa.Integer),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("brand_profiles")
