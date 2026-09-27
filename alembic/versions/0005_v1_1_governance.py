"""0005_v1_1_governance: recruiter PII governance fields (V1.1 review,
security section — "no handling policy" for scraped recruiter data), and
data_requests for POPIA/GDPR-style export & deletion audit trail.

Revision ID: 0005_v1_1_governance
Revises: 0004_v1_1_job_lifecycle
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0005_v1_1_governance"
down_revision = "0004_v1_1_job_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("recruiters", sa.Column("data_source", sa.String(50)))
    op.add_column(
        "recruiters",
        sa.Column("consent_basis", sa.String(50), server_default="legitimate_interest"),
    )
    op.add_column("recruiters", sa.Column("retention_expires_at", sa.DateTime(timezone=True)))
    op.create_index(
        "idx_recruiters_retention", "recruiters", ["retention_expires_at"],
        postgresql_where="retention_expires_at IS NOT NULL",
    )

    op.create_table(
        "data_requests",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("request_type IN ('export','deletion')", name="ck_data_requests_type"),
        sa.CheckConstraint(
            "status IN ('pending','processing','completed','failed')", name="ck_data_requests_status"
        ),
    )
    op.create_index("idx_data_requests_user", "data_requests", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_data_requests_user", table_name="data_requests")
    op.drop_table("data_requests")
    op.drop_index("idx_recruiters_retention", table_name="recruiters")
    op.drop_column("recruiters", "retention_expires_at")
    op.drop_column("recruiters", "consent_basis")
    op.drop_column("recruiters", "data_source")
