"""
SQLAlchemy 2.0 ORM models — AI Job Hunter Platform, schema V1.1.

Mirrors docs/db-schema-v1.1.md exactly. Every table, column, constraint,
and index here has a 1:1 counterpart in that document and in the Alembic
migrations under alembic/versions/. If you change one, change all three.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )


# ===================== AUTH / USERS =====================
class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('user','admin')", name="ck_users_role"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="user")
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    profile: Mapped["Profile | None"] = relationship(back_populates="user", uselist=False)
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("idx_refresh_tokens_user_active", "user_id", postgresql_where=text("revoked_at IS NULL")),
        Index("idx_refresh_tokens_hash", "token_hash"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("refresh_tokens.id"))

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


# ===================== MODULE 1: PROFILE =====================
class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_profiles_user_id"),
        CheckConstraint("years_experience >= 0", name="ck_profiles_years_experience"),
        CheckConstraint("salary_expectation_min >= 0", name="ck_profiles_salary_min"),
        CheckConstraint(
            "salary_expectation_max >= salary_expectation_min", name="ck_profiles_salary_max_gte_min"
        ),
        CheckConstraint(
            "work_mode_preference IN ('remote','hybrid','onsite')", name="ck_profiles_work_mode"
        ),
        CheckConstraint(
            "profile_completion_score BETWEEN 0 AND 100", name="ck_profiles_completion_score"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    current_role: Mapped[str | None] = mapped_column(String(255))
    years_experience: Mapped[int | None] = mapped_column(Integer)
    industry: Mapped[str | None] = mapped_column(String(255))
    desired_roles: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    salary_expectation_min: Mapped[int | None] = mapped_column(Integer)
    salary_expectation_max: Mapped[int | None] = mapped_column(Integer)
    salary_currency: Mapped[str] = mapped_column(String(10), server_default="ZAR")
    location_preferences: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    work_mode_preference: Mapped[str | None] = mapped_column(String(20))
    career_transition_target: Mapped[str | None] = mapped_column(String(255))
    profile_completion_score: Mapped[int] = mapped_column(Integer, server_default="0")
    # opt-in for pooled cross-user analytics — see
    # ai-job-hunter-recruiter-intelligence.md section 2. Default FALSE:
    # contributing outcome data to a cross-user dataset is a feature the
    # user opts into, never a silent default.
    contributes_to_pooled_analytics: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    # the user's identified source domain for Career Transition Intelligence
    # (collections/operations/banking/call_centre) — set via the profile
    # editor or inferred from career_transition_target; nullable because
    # not every user has gone through that flow. This is what lets
    # Recruiter Intelligence segment "companies likely to interview
    # candidates with your background" per
    # ai-job-hunter-recruiter-intelligence.md section 1.
    primary_source_domain: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="profile")
    skills: Mapped[list["Skill"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    certifications: Mapped[list["Certification"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    education: Mapped[list["Education"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    career_tracks: Mapped[list["CareerTrack"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    job_matches: Mapped[list["JobMatch"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    tailored_cvs: Mapped[list["TailoredCV"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    messages: Mapped[list["Message"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    applications: Mapped[list["Application"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    saved_searches: Mapped[list["SavedSearch"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (
        UniqueConstraint("profile_id", "name", name="uq_skills_profile_name"),
        CheckConstraint(
            "proficiency IN ('beginner','intermediate','advanced','expert')", name="ck_skills_proficiency"
        ),
        CheckConstraint("years_used >= 0", name="ck_skills_years_used"),
        CheckConstraint("source IN ('manual','cv_extracted')", name="ck_skills_source"),
        Index("idx_skills_profile", "profile_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    proficiency: Mapped[str | None] = mapped_column(String(20))
    years_used: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(20), server_default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["Profile"] = relationship(back_populates="skills")


class Certification(Base):
    __tablename__ = "certifications"
    __table_args__ = (
        CheckConstraint(
            "expiry_date IS NULL OR expiry_date >= issued_date", name="ck_certifications_expiry_after_issued"
        ),
        Index("idx_certifications_profile", "profile_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    issuer: Mapped[str | None] = mapped_column(String(255))
    issued_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["Profile"] = relationship(back_populates="certifications")


class Education(Base):
    __tablename__ = "education"
    __table_args__ = (
        CheckConstraint("status IN ('in_progress','completed')", name="ck_education_status"),
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_education_end_after_start",
        ),
        Index("idx_education_profile", "profile_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    qualification: Mapped[str] = mapped_column(String(255), nullable=False)
    institution: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), server_default="completed")
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["Profile"] = relationship(back_populates="education")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "document_type IN ('master_cv','certificate','cover_letter','generated_cv')",
            name="ck_documents_type",
        ),
        CheckConstraint("version >= 1", name="ck_documents_version"),
        Index("idx_documents_profile", "profile_id", postgresql_where=text("deleted_at IS NULL")),
        Index(
            "idx_documents_type", "profile_id", "document_type", postgresql_where=text("deleted_at IS NULL")
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(30), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    parsed_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped["Profile"] = relationship(back_populates="documents")


class DocumentBlob(Base):
    """File bytes for uploaded documents, keyed by Document.storage_path.
    Stands in for the object-storage bucket described in
    ai-job-hunter-db-schema-v1.1.md section 3 until one is provisioned —
    the storage_path contract is unchanged, so moving the bytes to S3 later
    only touches app/core/storage.py."""
    __tablename__ = "document_blobs"

    storage_path: Mapped[str] = mapped_column(String(1000), primary_key=True)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CareerTrack(Base):
    __tablename__ = "career_tracks"
    __table_args__ = (
        UniqueConstraint("profile_id", "track_name", name="uq_career_tracks_profile_name"),
        Index("idx_career_tracks_profile", "profile_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    track_name: Mapped[str] = mapped_column(String(255), nullable=False)
    master_cv_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    priority: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["Profile"] = relationship(back_populates="career_tracks")


# ===================== MODULE 2/3: JOBS =====================
class JobSource(Base):
    __tablename__ = "job_sources"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # adapter_type + per-instance settings (URLs, credentials, selectors,
    # discovery_queries, etc.) — see job-discovery-architecture.md section 3.
    # Credentials here are references to a secrets store in production, not
    # plaintext, per the platform's security requirements.
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    poll_frequency_minutes: Mapped[int] = mapped_column(Integer, server_default="120")

    jobs: Mapped[list["Job"]] = relationship(back_populates="source")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_jobs_source_external"),
        CheckConstraint("salary_min >= 0", name="ck_jobs_salary_min"),
        CheckConstraint("salary_max >= salary_min", name="ck_jobs_salary_max_gte_min"),
        CheckConstraint("competition_score IN ('low','medium','high')", name="ck_jobs_competition_score"),
        Index("idx_jobs_posted", "date_posted", postgresql_using="btree"),
        Index(
            "idx_jobs_active_filters",
            "is_remote",
            "location",
            "date_posted",
            postgresql_where=text("is_active = true"),
        ),
        Index("idx_jobs_industry_date", "company", "date_posted", postgresql_where=text("is_active = true")),
        Index("idx_jobs_industry_active", "industry", postgresql_where=text("is_active = true")),
        Index(
            "idx_jobs_hidden_gem",
            "is_hidden_gem",
            postgresql_where=text("is_hidden_gem = true AND is_active = true"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job_sources.id", ondelete="SET NULL"))
    external_id: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255))
    is_remote: Mapped[bool] = mapped_column(server_default=text("false"))
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    apply_url: Mapped[str | None] = mapped_column(String(1000))
    date_posted: Mapped[date | None] = mapped_column(Date)
    is_syndicated: Mapped[bool] = mapped_column(server_default=text("true"))
    competition_score: Mapped[str | None] = mapped_column(String(10))
    industry: Mapped[str | None] = mapped_column(String(80))
    is_hidden_gem: Mapped[bool] = mapped_column(server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped["JobSource | None"] = relationship(back_populates="jobs")
    matches: Mapped[list["JobMatch"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    applications: Mapped[list["Application"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    source_references: Mapped[list["JobSourceReference"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class JobSourceReference(Base):
    """Cross-source duplicate tracking — see job-discovery-architecture.md
    section 5.2. When the same real-world vacancy is confirmed posted on
    multiple sources, it stays one `jobs` row with multiple references here
    instead of duplicate job rows; the reference count also drives
    `jobs.competition_score` directly."""
    __tablename__ = "job_source_references"
    __table_args__ = (
        UniqueConstraint("job_id", "source_id", name="uq_job_source_references_job_source"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_sources.id", ondelete="CASCADE"), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255))
    apply_url: Mapped[str | None] = mapped_column(String(1000))
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped["Job"] = relationship(back_populates="source_references")


# ===================== MODULE 4: MATCH SCORING =====================
class JobMatch(Base):
    __tablename__ = "job_matches"
    __table_args__ = (
        UniqueConstraint("profile_id", "job_id", name="uq_job_matches_profile_job"),
        CheckConstraint("match_score BETWEEN 0 AND 100", name="ck_job_matches_score_range"),
        Index("idx_matches_profile_score", "profile_id", "match_score"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    match_score: Mapped[int] = mapped_column(Integer, nullable=False)
    strengths: Mapped[dict | None] = mapped_column(JSONB)
    missing_skills: Mapped[dict | None] = mapped_column(JSONB)
    experience_gaps: Mapped[dict | None] = mapped_column(JSONB)
    recommendations: Mapped[dict | None] = mapped_column(JSONB)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["Profile"] = relationship(back_populates="job_matches")
    job: Mapped["Job"] = relationship(back_populates="matches")


# ===================== MODULE 5: CV TAILORING =====================
class TailoredCV(Base):
    __tablename__ = "tailored_cvs"
    __table_args__ = (
        UniqueConstraint("profile_id", "job_id", "variant", name="uq_tailored_cvs_profile_job_variant"),
        CheckConstraint("variant IN ('ats','recruiter_friendly')", name="ck_tailored_cvs_variant"),
        CheckConstraint("optimization_score BETWEEN 0 AND 100", name="ck_tailored_cvs_optimization_score"),
        CheckConstraint("ats_score BETWEEN 0 AND 100", name="ck_tailored_cvs_ats_score"),
        Index("idx_tailored_cvs_profile", "profile_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    variant: Mapped[str] = mapped_column(String(20), nullable=False)
    content_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    added_keywords: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    optimization_score: Mapped[int | None] = mapped_column(Integer)
    ats_score: Mapped[int | None] = mapped_column(Integer)
    pdf_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    docx_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["Profile"] = relationship(back_populates="tailored_cvs")
    applications: Mapped[list["Application"]] = relationship(back_populates="tailored_cv")


# ===================== MODULE 6/7: LETTERS, RECRUITERS, MESSAGES =====================
class Recruiter(Base):
    __tablename__ = "recruiters"
    __table_args__ = (
        Index("idx_recruiters_job", "job_id"),
        Index(
            "idx_recruiters_retention", "retention_expires_at", postgresql_where=text("retention_expires_at IS NOT NULL")
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    role_title: Mapped[str | None] = mapped_column(String(255))
    company: Mapped[str | None] = mapped_column(String(255))
    data_source: Mapped[str | None] = mapped_column(String(50))
    consent_basis: Mapped[str] = mapped_column(String(50), server_default="legitimate_interest")
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    messages: Mapped[list["Message"]] = relationship(back_populates="recruiter")


class RecruiterIntelligenceSnapshot(Base):
    """Pooled, k-anonymity-gated recruiter responsiveness stats. See
    ai-job-hunter-recruiter-intelligence.md sections 3-4. NULL metric
    columns mean 'below contributor threshold', never a real zero."""
    __tablename__ = "recruiter_intelligence_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "recruiter_id", "period_start", "period_end", name="uq_recruiter_intel_recruiter_period"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    recruiter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recruiters.id", ondelete="CASCADE"), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    postings_count: Mapped[int] = mapped_column(Integer, server_default="0")
    contributing_user_count: Mapped[int] = mapped_column(Integer, nullable=False)
    response_rate: Mapped[float | None] = mapped_column(Numeric(5, 2))
    avg_hours_to_first_response: Mapped[float | None] = mapped_column(Numeric(8, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CompanyIntelligenceSnapshot(Base):
    """Pooled, k-anonymity-gated company hiring stats, including the
    per-source-domain interview-rate breakdown that answers 'companies
    most likely to interview candidates with my background'. Each segment
    in interview_rate_by_source_domain is independently gated — see
    ai-job-hunter-recruiter-intelligence.md section 4."""
    __tablename__ = "company_intelligence_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "company_name", "period_start", "period_end", name="uq_company_intel_name_period"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    contributing_user_count: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_turnaround_days: Mapped[float | None] = mapped_column(Numeric(6, 2))
    interview_rate_overall: Mapped[float | None] = mapped_column(Numeric(5, 2))
    interview_rate_by_source_domain: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "message_type IN ('cover_letter','recruiter_email','linkedin_message','follow_up')",
            name="ck_messages_type",
        ),
        CheckConstraint(
            "tone IN ('professional','formal','executive','friendly')", name="ck_messages_tone"
        ),
        CheckConstraint("status IN ('draft','reviewed','approved','sent')", name="ck_messages_status"),
        CheckConstraint("sent_at IS NULL OR status = 'sent'", name="ck_messages_sent_requires_status"),
        CheckConstraint(
            "sent_at IS NULL OR approved_at IS NOT NULL", name="ck_messages_sent_requires_approval"
        ),
        Index("idx_messages_profile", "profile_id"),
        Index("idx_messages_status", "status"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    recruiter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("recruiters.id", ondelete="SET NULL"))
    message_type: Mapped[str] = mapped_column(String(30), nullable=False)
    tone: Mapped[str | None] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["Profile"] = relationship(back_populates="messages")
    recruiter: Mapped["Recruiter | None"] = relationship(back_populates="messages")
    email: Mapped["Email | None"] = relationship(back_populates="message", uselist=False, cascade="all, delete-orphan")


class Email(Base):
    __tablename__ = "emails"

    id: Mapped[uuid.UUID] = _uuid_pk()
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), unique=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    interview_requested: Mapped[bool] = mapped_column(server_default=text("false"))

    message: Mapped["Message"] = relationship(back_populates="email")


# ===================== MODULE 8: APPLICATIONS =====================
class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("profile_id", "job_id", name="uq_applications_profile_job"),
        CheckConstraint(
            "stage IN ('saved','applying','submitted','screening','interview','assessment','offer','rejected','closed')",
            name="ck_applications_stage",
        ),
        Index("idx_applications_profile_stage", "profile_id", "stage"),
        Index("idx_applications_dashboard", "profile_id", "stage", "applied_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    tailored_cv_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tailored_cvs.id", ondelete="SET NULL")
    )
    stage: Mapped[str] = mapped_column(String(20), nullable=False, server_default="saved")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    profile: Mapped["Profile"] = relationship(back_populates="applications")
    job: Mapped["Job"] = relationship(back_populates="applications")
    tailored_cv: Mapped["TailoredCV | None"] = relationship(back_populates="applications")
    stage_history: Mapped[list["ApplicationStageHistory"]] = relationship(
        back_populates="application", cascade="all, delete-orphan", order_by="ApplicationStageHistory.changed_at"
    )


class ApplicationStageHistory(Base):
    __tablename__ = "application_stage_history"
    __table_args__ = (Index("idx_stage_history_application", "application_id", "changed_at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    from_stage: Mapped[str | None] = mapped_column(String(20))
    to_stage: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    application: Mapped["Application"] = relationship(back_populates="stage_history")


# ===================== MODULE 9: ANALYTICS =====================
class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "period_start", "period_end", name="uq_analytics_snapshots_profile_period"
        ),
        CheckConstraint("period_end >= period_start", name="ck_analytics_snapshots_period_range"),
        Index("idx_analytics_profile_period", "profile_id", "period_start"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    applications_submitted: Mapped[int] = mapped_column(Integer, server_default="0")
    interviews: Mapped[int] = mapped_column(Integer, server_default="0")
    offers: Mapped[int] = mapped_column(Integer, server_default="0")
    rejections: Mapped[int] = mapped_column(Integer, server_default="0")
    response_rate: Mapped[float | None] = mapped_column(Numeric(5, 2))
    interview_rate: Mapped[float | None] = mapped_column(Numeric(5, 2))
    offer_rate: Mapped[float | None] = mapped_column(Numeric(5, 2))
    avg_time_to_response_days: Mapped[float | None] = mapped_column(Numeric(6, 2))
    breakdown_by_source: Mapped[dict | None] = mapped_column(JSONB)
    breakdown_by_role: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ===================== MODULE 10 / 11: SCAFFOLDS =====================
class SkillGapReport(Base):
    __tablename__ = "skill_gap_reports"
    __table_args__ = (Index("idx_skill_gap_profile", "profile_id", "generated_at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    top_missing_skills: Mapped[dict | None] = mapped_column(JSONB)
    recommended_courses: Mapped[dict | None] = mapped_column(JSONB)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CareerCoachInsight(Base):
    __tablename__ = "career_coach_insights"
    __table_args__ = (
        CheckConstraint("insight_type IN ('weekly','monthly')", name="ck_career_coach_insight_type"),
        Index("idx_career_coach_profile", "profile_id", "generated_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    insight_type: Mapped[str | None] = mapped_column(String(20))
    content: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ===================== SAVED SEARCHES & NOTIFICATIONS (V1.1) =====================
class SavedSearch(Base):
    __tablename__ = "saved_searches"
    __table_args__ = (
        CheckConstraint(
            "alert_frequency IN ('instant','daily','weekly','off')", name="ck_saved_searches_frequency"
        ),
        Index("idx_saved_searches_profile", "profile_id"),
        Index(
            "idx_saved_searches_due",
            "alert_frequency",
            "last_run_at",
            postgresql_where=text("alert_frequency != 'off'"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    filters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    alert_frequency: Mapped[str] = mapped_column(String(20), server_default="daily")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["Profile"] = relationship(back_populates="saved_searches")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("idx_notifications_profile_unread", "profile_id", postgresql_where=text("read_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["Profile"] = relationship(back_populates="notifications")


# ===================== SECURITY / AUDIT =====================
class ActivityLog(Base):
    __tablename__ = "activity_logs"
    __table_args__ = (
        Index("idx_activity_logs_user", "user_id", "created_at"),
        Index("idx_activity_logs_entity", "entity_type", "entity_id"),
        {"postgresql_partition_by": "RANGE (created_at)"},
    )

    # Composite PK (id, created_at): Postgres requires a partitioned
    # table's primary key to include every partitioning column — caught
    # only by running the actual migration against live Postgres (see
    # alembic/versions/0007_v1_1_activity_partition.py).
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(100))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)


class DataRequest(Base):
    __tablename__ = "data_requests"
    __table_args__ = (
        CheckConstraint("request_type IN ('export','deletion')", name="ck_data_requests_type"),
        CheckConstraint(
            "status IN ('pending','processing','completed','failed')", name="ck_data_requests_status"
        ),
        Index("idx_data_requests_user", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    request_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InterviewPrepSession(Base):
    """One practice session for a (profile, source_domain, target_domain)
    pathway. See ai-job-hunter-interview-preparation.md."""
    __tablename__ = "interview_prep_sessions"
    __table_args__ = (
        Index("idx_interview_prep_sessions_profile", "profile_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    source_domain: Mapped[str] = mapped_column(String(30), nullable=False)
    target_domain: Mapped[str] = mapped_column(String(30), nullable=False)
    readiness_score: Mapped[int | None] = mapped_column(Integer)
    weak_competencies: Mapped[list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    answers: Mapped[list["InterviewPrepAnswer"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class InterviewPrepAnswer(Base):
    """One question+answer within a session, with its deterministic STAR
    score (behavioral) or correctness flag (technical)."""
    __tablename__ = "interview_prep_answers"
    __table_args__ = (
        Index("idx_interview_prep_answers_session", "session_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interview_prep_sessions.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'behavioral' | 'technical'
    target_competency: Mapped[str | None] = mapped_column(String(255))
    answer_text: Mapped[str | None] = mapped_column(Text)
    star_score: Mapped[int | None] = mapped_column(Integer)
    technical_correct: Mapped[bool | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["InterviewPrepSession"] = relationship(back_populates="answers")


class BrandProfile(Base):
    """LinkedIn/external-surface text the user has entered for consistency
    checking against their CV/platform profile. See
    ai-job-hunter-platform-vision.md section 3."""
    __tablename__ = "brand_profiles"

    id: Mapped[uuid.UUID] = _uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    linkedin_headline: Mapped[str | None] = mapped_column(String(220))
    linkedin_summary: Mapped[str | None] = mapped_column(Text)
    last_consistency_score: Mapped[int | None] = mapped_column(Integer)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
