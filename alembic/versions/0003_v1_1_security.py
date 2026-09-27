"""0003_v1_1_security: refresh_tokens table for revocable/auditable JWT
refresh (V1.1 review, section 3 — "JWT refresh token storage/rotation
mechanics unspecified"). Ownership checks are enforced at the application
dependency layer, not schema, so no DDL for that fix.

Revision ID: 0003_v1_1_security
Revises: 0002_v1_indexes
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0003_v1_1_security"
down_revision = "0002_v1_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("replaced_by", pg.UUID(as_uuid=True), sa.ForeignKey("refresh_tokens.id")),
    )
    op.create_index(
        "idx_refresh_tokens_user_active", "refresh_tokens", ["user_id"],
        postgresql_where="revoked_at IS NULL",
    )
    op.create_index("idx_refresh_tokens_hash", "refresh_tokens", ["token_hash"])


def downgrade() -> None:
    op.drop_index("idx_refresh_tokens_hash", table_name="refresh_tokens")
    op.drop_index("idx_refresh_tokens_user_active", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
