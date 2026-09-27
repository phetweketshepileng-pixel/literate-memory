# Deploying Ascend on Railway

Project `literate-memory` on Railway runs these services:

| Service    | Source                          | Start command                                                                 |
|------------|---------------------------------|-------------------------------------------------------------------------------|
| backend    | this repo (root)                | Dockerfile default; pre-deploy command `alembic upgrade head`; healthcheck `/health` |
| worker     | this repo (root)                | `celery -A app.core.celery_app worker --loglevel=info -Q ai_heavy,scraping,default,celery --concurrency=2` |
| beat       | this repo (root)                | `celery -A app.core.celery_app beat --loglevel=info`                          |
| job-poller | this repo (root)                | `python scripts/poll_jobs.py` — cron `0 */6 * * *`, restart policy Never      |
| web        | this repo, root dir `/frontend` | Dockerfile in `frontend/` (nginx serving `frontend/public/index.html`)        |
| Postgres, Redis | Railway templates          | —                                                                             |

Shared variables for backend/worker/beat/job-poller:

```
DATABASE_URL=postgresql+asyncpg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.RAILWAY_PRIVATE_DOMAIN}}:5432/${{Postgres.PGDATABASE}}
REDIS_CACHE_URL=${{Redis.REDIS_URL}}/0
REDIS_BROKER_URL=${{Redis.REDIS_URL}}/1
JWT_SECRET=<long random string, set on backend; others reference ${{backend.JWT_SECRET}}>
OPENAI_API_KEY=<your key — backend and worker>
```

Frontend: edit files in `frontend/src/`, run `frontend/build.sh` to regenerate
`frontend/public/index.html`, commit both.
