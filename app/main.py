"""FastAPI app factory. Mounts every V1 module router under /api/v1 per
the API spec in ai-job-hunter-v1-spec.md section 5. Each module owns its
own router/schemas/service — this file only assembles them, per the
module-registry pattern in the system architecture doc."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.analytics.router import router as analytics_router
from app.modules.applications.router import router as applications_router
from app.modules.auth.router import router as auth_router
from app.modules.career_transition.router import router as career_transition_router
from app.modules.cv_tailoring.router import router as cv_router
from app.modules.interview_prep.router import router as interview_prep_router
from app.modules.job_discovery.router import router as jobs_router
from app.modules.match_scoring.router import router as matches_router
from app.modules.profile.router import router as profile_router
from app.modules.professional_branding.router import router as branding_router
from app.modules.recruiter_intelligence.router import router as recruiter_intelligence_router


def create_app() -> FastAPI:
    app = FastAPI(title="AI Job Hunter Platform API", version="1.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # tightened to the actual frontend origin in production
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],  # lets the browser see download file names
    )

    api_v1 = "/api/v1"
    app.include_router(auth_router, prefix=api_v1)
    app.include_router(profile_router, prefix=api_v1)
    app.include_router(jobs_router, prefix=api_v1)
    app.include_router(matches_router, prefix=api_v1)
    app.include_router(cv_router, prefix=api_v1)
    app.include_router(applications_router, prefix=api_v1)
    app.include_router(analytics_router, prefix=api_v1)
    app.include_router(career_transition_router, prefix=api_v1)
    app.include_router(recruiter_intelligence_router, prefix=api_v1)
    app.include_router(interview_prep_router, prefix=api_v1)
    app.include_router(branding_router, prefix=api_v1)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
