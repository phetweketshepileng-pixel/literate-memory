"""0014_document_storage: document_blobs table holding uploaded file bytes
(keyed by documents.storage_path). Additive only.

Revision ID: 0014_document_storage
Revises: 0013_professional_branding
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_document_storage"
down_revision = "0013_professional_branding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_blobs",
        sa.Column("storage_path", sa.String(1000), primary_key=True),
        sa.Column("content", sa.LargeBinary, nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("document_blobs")
