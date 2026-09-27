"""Pydantic schemas for the Profile module (Module 1)."""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SkillIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    proficiency: str | None = Field(default=None, pattern="^(beginner|intermediate|advanced|expert)$")
    years_used: int | None = Field(default=None, ge=0)


class SkillOut(SkillIn):
    id: UUID
    source: str
    created_at: datetime


class CertificationIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    issuer: str | None = None
    issued_date: date | None = None
    expiry_date: date | None = None

    @field_validator("expiry_date")
    @classmethod
    def expiry_after_issued(cls, v: date | None, info) -> date | None:
        issued = info.data.get("issued_date")
        if v is not None and issued is not None and v < issued:
            raise ValueError("expiry_date must be on or after issued_date")
        return v


class EducationIn(BaseModel):
    qualification: str = Field(min_length=1, max_length=255)
    institution: str | None = None
    status: str = Field(default="completed", pattern="^(in_progress|completed)$")
    start_date: date | None = None
    end_date: date | None = None


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    current_role: str | None = None
    years_experience: int | None = Field(default=None, ge=0)
    industry: str | None = None
    desired_roles: list[str] | None = None
    salary_expectation_min: int | None = Field(default=None, ge=0)
    salary_expectation_max: int | None = Field(default=None, ge=0)
    salary_currency: str | None = None
    location_preferences: list[str] | None = None
    work_mode_preference: str | None = Field(default=None, pattern="^(remote|hybrid|onsite)$")
    career_transition_target: str | None = None

    @field_validator("salary_expectation_max")
    @classmethod
    def max_gte_min(cls, v: int | None, info) -> int | None:
        min_val = info.data.get("salary_expectation_min")
        if v is not None and min_val is not None and v < min_val:
            raise ValueError("salary_expectation_max must be >= salary_expectation_min")
        return v


class ProfileOut(BaseModel):
    id: UUID
    full_name: str | None
    current_role: str | None
    years_experience: int | None
    industry: str | None
    desired_roles: list[str] | None
    salary_expectation_min: int | None
    salary_expectation_max: int | None
    work_mode_preference: str | None
    profile_completion_score: int

    model_config = {"from_attributes": True}


class ProfileCompletionOut(BaseModel):
    score: int
    missing_fields: list[str]
