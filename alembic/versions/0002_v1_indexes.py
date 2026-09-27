"""0002_v1_indexes: all V1 search/lookup indexes.

Revision ID: 0002_v1_indexes
Revises: 0001_baseline
Create Date: 2026-09-27
"""
from alembic import op

revision = "0002_v1_indexes"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')

    op.create_index("idx_skills_profile", "skills", ["profile_id"])
    op.create_index("idx_certifications_profile", "certifications", ["profile_id"])
    op.create_index("idx_education_profile", "education", ["profile_id"])
    op.create_index(
        "idx_documents_profile", "documents", ["profile_id"],
        postgresql_where="deleted_at IS NULL",
    )
    op.create_index(
        "idx_documents_type", "documents", ["profile_id", "document_type"],
        postgresql_where="deleted_at IS NULL",
    )

    op.execute(
        "CREATE INDEX idx_jobs_title_fts ON jobs USING gin (to_tsvector('english', title))"
    )
    op.execute(
        "CREATE INDEX idx_jobs_title_trgm ON jobs USING gin (title gin_trgm_ops)"
    )
    op.create_index("idx_jobs_posted", "jobs", ["date_posted"])

    op.create_index("idx_matches_profile_score", "job_matches", ["profile_id", "match_score"])
    op.create_index("idx_tailored_cvs_profile", "tailored_cvs", ["profile_id"])
    op.create_index("idx_recruiters_job", "recruiters", ["job_id"])
    op.create_index("idx_messages_profile", "messages", ["profile_id"])
    op.create_index("idx_messages_status", "messages", ["status"])
    op.create_index("idx_applications_profile_stage", "applications", ["profile_id", "stage"])
    op.create_index(
        "idx_stage_history_application", "application_stage_history", ["application_id", "changed_at"]
    )
    op.create_index("idx_analytics_profile_period", "analytics_snapshots", ["profile_id", "period_start"])
    op.create_index("idx_activity_logs_user", "activity_logs", ["user_id", "created_at"])
    op.create_index("idx_activity_logs_entity", "activity_logs", ["entity_type", "entity_id"])


def downgrade() -> None:
    for name, table in [
        ("idx_activity_logs_entity", "activity_logs"),
        ("idx_activity_logs_user", "activity_logs"),
        ("idx_analytics_profile_period", "analytics_snapshots"),
        ("idx_stage_history_application", "application_stage_history"),
        ("idx_applications_profile_stage", "applications"),
        ("idx_messages_status", "messages"),
        ("idx_messages_profile", "messages"),
        ("idx_recruiters_job", "recruiters"),
        ("idx_tailored_cvs_profile", "tailored_cvs"),
        ("idx_matches_profile_score", "job_matches"),
        ("idx_jobs_posted", "jobs"),
        ("idx_jobs_title_trgm", "jobs"),
        ("idx_jobs_title_fts", "jobs"),
        ("idx_documents_type", "documents"),
        ("idx_documents_profile", "documents"),
        ("idx_education_profile", "education"),
        ("idx_certifications_profile", "certifications"),
        ("idx_skills_profile", "skills"),
    ]:
        op.drop_index(name, table_name=table)
    op.execute('DROP EXTENSION IF EXISTS "pg_trgm"')
