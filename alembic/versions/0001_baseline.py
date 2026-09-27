"""0001_baseline: extensions + V1 core tables (users, profiles, skills,
certifications, education, documents, job_sources, jobs, job_matches,
tailored_cvs, recruiters, messages, emails, applications,
application_stage_history, analytics_snapshots, skill_gap_reports,
career_coach_insights, activity_logs (unpartitioned in V1), documents.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.create_table(
        "users",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('user','admin')", name="ck_users_role"),
    )

    op.create_table(
        "profiles",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_name", sa.String(255)),
        sa.Column("phone", sa.String(50)),
        sa.Column("linkedin_url", sa.String(500)),
        sa.Column("current_role", sa.String(255)),
        sa.Column("years_experience", sa.Integer),
        sa.Column("industry", sa.String(255)),
        sa.Column("desired_roles", pg.ARRAY(sa.String)),
        sa.Column("salary_expectation_min", sa.Integer),
        sa.Column("salary_expectation_max", sa.Integer),
        sa.Column("salary_currency", sa.String(10), server_default="ZAR"),
        sa.Column("location_preferences", pg.ARRAY(sa.String)),
        sa.Column("work_mode_preference", sa.String(20)),
        sa.Column("career_transition_target", sa.String(255)),
        sa.Column("profile_completion_score", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="uq_profiles_user_id"),
        sa.CheckConstraint("years_experience >= 0", name="ck_profiles_years_experience"),
        sa.CheckConstraint("salary_expectation_min >= 0", name="ck_profiles_salary_min"),
        sa.CheckConstraint(
            "salary_expectation_max >= salary_expectation_min", name="ck_profiles_salary_max_gte_min"
        ),
        sa.CheckConstraint(
            "work_mode_preference IN ('remote','hybrid','onsite')", name="ck_profiles_work_mode"
        ),
        sa.CheckConstraint(
            "profile_completion_score BETWEEN 0 AND 100", name="ck_profiles_completion_score"
        ),
    )

    op.create_table(
        "skills",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("profile_id", pg.UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("proficiency", sa.String(20)),
        sa.Column("years_used", sa.Integer),
        sa.Column("source", sa.String(20), server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("profile_id", "name", name="uq_skills_profile_name"),
        sa.CheckConstraint(
            "proficiency IN ('beginner','intermediate','advanced','expert')", name="ck_skills_proficiency"
        ),
        sa.CheckConstraint("years_used >= 0", name="ck_skills_years_used"),
        sa.CheckConstraint("source IN ('manual','cv_extracted')", name="ck_skills_source"),
    )

    op.create_table(
        "certifications",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("profile_id", pg.UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("issuer", sa.String(255)),
        sa.Column("issued_date", sa.Date),
        sa.Column("expiry_date", sa.Date),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "expiry_date IS NULL OR expiry_date >= issued_date", name="ck_certifications_expiry_after_issued"
        ),
    )

    op.create_table(
        "education",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("profile_id", pg.UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("qualification", sa.String(255), nullable=False),
        sa.Column("institution", sa.String(255)),
        sa.Column("status", sa.String(20), server_default="completed"),
        sa.Column("start_date", sa.Date),
        sa.Column("end_date", sa.Date),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('in_progress','completed')", name="ck_education_status"),
        sa.CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_education_end_after_start",
        ),
    )

    op.create_table(
        "documents",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("profile_id", pg.UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_type", sa.String(30), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("mime_type", sa.String(100)),
        sa.Column("version", sa.Integer, server_default="1"),
        sa.Column("parsed_text", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "document_type IN ('master_cv','certificate','cover_letter','generated_cv')",
            name="ck_documents_type",
        ),
        sa.CheckConstraint("version >= 1", name="ck_documents_version"),
    )

    op.create_table(
        "job_sources",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("last_polled_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "jobs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("source_id", pg.UUID(as_uuid=True), sa.ForeignKey("job_sources.id", ondelete="SET NULL")),
        sa.Column("external_id", sa.String(255)),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("company", sa.String(255)),
        sa.Column("location", sa.String(255)),
        sa.Column("is_remote", sa.Boolean, server_default=sa.text("false")),
        sa.Column("salary_min", sa.Integer),
        sa.Column("salary_max", sa.Integer),
        sa.Column("description", sa.Text),
        sa.Column("apply_url", sa.String(1000)),
        sa.Column("date_posted", sa.Date),
        sa.Column("is_syndicated", sa.Boolean, server_default=sa.text("true")),
        sa.Column("competition_score", sa.String(10)),
        sa.Column("is_hidden_gem", sa.Boolean, server_default=sa.text("false")),
        sa.Column("raw_payload", pg.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("source_id", "external_id", name="uq_jobs_source_external"),
        sa.CheckConstraint("salary_min >= 0", name="ck_jobs_salary_min"),
        sa.CheckConstraint("salary_max >= salary_min", name="ck_jobs_salary_max_gte_min"),
        sa.CheckConstraint("competition_score IN ('low','medium','high')", name="ck_jobs_competition_score"),
    )

    op.create_table(
        "job_matches",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("profile_id", pg.UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", pg.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("match_score", sa.Integer, nullable=False),
        sa.Column("strengths", pg.JSONB),
        sa.Column("missing_skills", pg.JSONB),
        sa.Column("experience_gaps", pg.JSONB),
        sa.Column("recommendations", pg.JSONB),
        sa.Column("scored_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("profile_id", "job_id", name="uq_job_matches_profile_job"),
        sa.CheckConstraint("match_score BETWEEN 0 AND 100", name="ck_job_matches_score_range"),
    )

    op.create_table(
        "tailored_cvs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("profile_id", pg.UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", pg.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="SET NULL")),
        sa.Column("variant", sa.String(20), nullable=False),
        sa.Column("content_json", pg.JSONB, nullable=False),
        sa.Column("added_keywords", pg.ARRAY(sa.String)),
        sa.Column("optimization_score", sa.Integer),
        sa.Column("ats_score", sa.Integer),
        sa.Column("pdf_document_id", pg.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="SET NULL")),
        sa.Column("docx_document_id", pg.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("profile_id", "job_id", "variant", name="uq_tailored_cvs_profile_job_variant"),
        sa.CheckConstraint("variant IN ('ats','recruiter_friendly')", name="ck_tailored_cvs_variant"),
        sa.CheckConstraint("optimization_score BETWEEN 0 AND 100", name="ck_tailored_cvs_optimization_score"),
        sa.CheckConstraint("ats_score BETWEEN 0 AND 100", name="ck_tailored_cvs_ats_score"),
    )

    op.create_table(
        "recruiters",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("job_id", pg.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="SET NULL")),
        sa.Column("name", sa.String(255)),
        sa.Column("email", sa.String(255)),
        sa.Column("role_title", sa.String(255)),
        sa.Column("company", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "messages",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("profile_id", pg.UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", pg.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="SET NULL")),
        sa.Column("recruiter_id", pg.UUID(as_uuid=True), sa.ForeignKey("recruiters.id", ondelete="SET NULL")),
        sa.Column("message_type", sa.String(30), nullable=False),
        sa.Column("tone", sa.String(20)),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "message_type IN ('cover_letter','recruiter_email','linkedin_message','follow_up')",
            name="ck_messages_type",
        ),
        sa.CheckConstraint(
            "tone IN ('professional','formal','executive','friendly')", name="ck_messages_tone"
        ),
        sa.CheckConstraint("status IN ('draft','reviewed','approved','sent')", name="ck_messages_status"),
        sa.CheckConstraint("sent_at IS NULL OR status = 'sent'", name="ck_messages_sent_requires_status"),
        sa.CheckConstraint(
            "sent_at IS NULL OR approved_at IS NOT NULL", name="ck_messages_sent_requires_approval"
        ),
    )

    op.create_table(
        "emails",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("message_id", pg.UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="CASCADE"), unique=True),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("opened_at", sa.DateTime(timezone=True)),
        sa.Column("clicked_at", sa.DateTime(timezone=True)),
        sa.Column("replied_at", sa.DateTime(timezone=True)),
        sa.Column("interview_requested", sa.Boolean, server_default=sa.text("false")),
    )

    op.create_table(
        "applications",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("profile_id", pg.UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", pg.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tailored_cv_id", pg.UUID(as_uuid=True), sa.ForeignKey("tailored_cvs.id", ondelete="SET NULL")),
        sa.Column("stage", sa.String(20), nullable=False, server_default="saved"),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("profile_id", "job_id", name="uq_applications_profile_job"),
        sa.CheckConstraint(
            "stage IN ('saved','applying','submitted','screening','interview','assessment','offer','rejected','closed')",
            name="ck_applications_stage",
        ),
    )

    op.create_table(
        "application_stage_history",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("application_id", pg.UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_stage", sa.String(20)),
        sa.Column("to_stage", sa.String(20), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "analytics_snapshots",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("profile_id", pg.UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("applications_submitted", sa.Integer, server_default="0"),
        sa.Column("interviews", sa.Integer, server_default="0"),
        sa.Column("offers", sa.Integer, server_default="0"),
        sa.Column("rejections", sa.Integer, server_default="0"),
        sa.Column("response_rate", sa.Numeric(5, 2)),
        sa.Column("interview_rate", sa.Numeric(5, 2)),
        sa.Column("offer_rate", sa.Numeric(5, 2)),
        sa.Column("avg_time_to_response_days", sa.Numeric(6, 2)),
        sa.Column("breakdown_by_source", pg.JSONB),
        sa.Column("breakdown_by_role", pg.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "profile_id", "period_start", "period_end", name="uq_analytics_snapshots_profile_period"
        ),
        sa.CheckConstraint("period_end >= period_start", name="ck_analytics_snapshots_period_range"),
    )

    op.create_table(
        "skill_gap_reports",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("profile_id", pg.UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("top_missing_skills", pg.JSONB),
        sa.Column("recommended_courses", pg.JSONB),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "career_coach_insights",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("profile_id", pg.UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("insight_type", sa.String(20)),
        sa.Column("content", sa.Text),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("insight_type IN ('weekly','monthly')", name="ck_career_coach_insight_type"),
    )

    op.create_table(
        "activity_logs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("entity_type", sa.String(100)),
        sa.Column("entity_id", pg.UUID(as_uuid=True)),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("metadata", pg.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for table in [
        "activity_logs", "career_coach_insights", "skill_gap_reports", "analytics_snapshots",
        "application_stage_history", "applications", "emails", "messages", "recruiters",
        "tailored_cvs", "job_matches", "jobs", "job_sources", "documents", "education",
        "certifications", "skills", "profiles", "users",
    ]:
        op.drop_table(table)
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
