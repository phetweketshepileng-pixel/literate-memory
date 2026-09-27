"""0010_career_transition_engine: transition_pathways,
transferable_skill_mappings, transition_readiness_snapshots. See
ai-job-hunter-career-transition-engine.md section 6. Additive only.

Revision ID: 0010_career_transition_engine
Revises: 0009_v1_1_advanced_analytics
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0010_career_transition_engine"
down_revision = "0009_v1_1_advanced_analytics"
branch_labels = None
depends_on = None

SOURCE_DOMAINS = ("collections", "operations", "banking", "call_centre")
TARGET_DOMAINS = ("business_analysis", "systems_analysis", "data_analysis", "it_management", "project_management")


def upgrade() -> None:
    op.create_table(
        "transition_pathways",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("source_domain", sa.String(30), nullable=False),
        sa.Column("target_domain", sa.String(30), nullable=False),
        sa.Column("base_affinity_score", sa.Integer, nullable=False),
        sa.Column("recommended_certifications", pg.JSONB),
        sa.Column("typical_timeline_months", sa.Integer),
        sa.CheckConstraint(
            f"source_domain IN {SOURCE_DOMAINS}", name="ck_transition_pathways_source_domain"
        ),
        sa.CheckConstraint(
            f"target_domain IN {TARGET_DOMAINS}", name="ck_transition_pathways_target_domain"
        ),
        sa.CheckConstraint("base_affinity_score BETWEEN 0 AND 100", name="ck_transition_pathways_score_range"),
        sa.UniqueConstraint("source_domain", "target_domain", name="uq_transition_pathways_source_target"),
    )

    op.create_table(
        "transferable_skill_mappings",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("source_domain", sa.String(30), nullable=False),
        sa.Column("source_competency", sa.String(255), nullable=False),
        sa.Column("target_domain", sa.String(30), nullable=False),
        sa.Column("target_competency", sa.String(255), nullable=False),
        sa.Column("transfer_strength", sa.String(10), nullable=False),
        sa.Column("reframing_template", sa.Text, nullable=False),
        sa.CheckConstraint(
            "transfer_strength IN ('direct','strong','partial')", name="ck_transferable_mappings_strength"
        ),
    )
    op.create_index(
        "idx_transferable_mappings_lookup", "transferable_skill_mappings", ["source_domain", "target_domain"]
    )

    op.create_table(
        "transition_readiness_snapshots",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("profile_id", pg.UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_domain", sa.String(30), nullable=False),
        sa.Column("readiness_score", sa.Integer, nullable=False),
        sa.Column("skill_coverage_pct", sa.Numeric(5, 2)),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("readiness_score BETWEEN 0 AND 100", name="ck_transition_readiness_score_range"),
        sa.UniqueConstraint(
            "profile_id", "target_domain", "computed_at", name="uq_transition_readiness_profile_domain_time"
        ),
    )
    op.create_index(
        "idx_transition_readiness_profile",
        "transition_readiness_snapshots",
        ["profile_id", "target_domain", "computed_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_transition_readiness_profile", table_name="transition_readiness_snapshots")
    op.drop_table("transition_readiness_snapshots")
    op.drop_index("idx_transferable_mappings_lookup", table_name="transferable_skill_mappings")
    op.drop_table("transferable_skill_mappings")
    op.drop_table("transition_pathways")
