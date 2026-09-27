"""Output schemas the raw AI response is validated against before it's
trusted and persisted. See ai-architecture.md section 4 ("structured in,
structured out")."""
from __future__ import annotations

from pydantic import BaseModel, Field, conint


class JobMatchResult(BaseModel):
    match_score: conint(ge=0, le=100)
    strengths: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    experience_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    def to_json_schema(self) -> dict:  # convenience for provider calls
        return self.model_json_schema()


class CVSectionContent(BaseModel):
    summary: str
    experience: list[dict]
    skills_section: list[str]


class CVTailoringResult(BaseModel):
    content_json: CVSectionContent
    added_keywords: list[str] = Field(default_factory=list)
    optimization_score: conint(ge=0, le=100)


class MessageGenerationResult(BaseModel):
    content: str


JOB_MATCH_JSON_SCHEMA = JobMatchResult.model_json_schema()
CV_TAILORING_JSON_SCHEMA = CVTailoringResult.model_json_schema()
MESSAGE_JSON_SCHEMA = MessageGenerationResult.model_json_schema()
