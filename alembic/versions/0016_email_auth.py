"""0016_email_auth: email verification + emailed password-reset links.
Adds users.email_verified_at and the auth_email_tokens table. Additive only.

Revision ID: 0016_email_auth
Revises: 0015_job_industry
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0016_email_auth"
down_revision = "0015_job_industry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "auth_email_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(10), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("purpose IN ('verify','reset')", name="ck_auth_email_tokens_purpose"),
    )
    op.create_index("idx_auth_email_tokens_hash", "auth_email_tokens", ["token_hash"])


def downgrade() -> None:
    op.drop_index("idx_auth_email_tokens_hash", table_name="auth_email_tokens")
    op.drop_table("auth_email_tokens")
    op.drop_column("users", "email_verified_at")
