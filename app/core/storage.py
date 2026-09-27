"""Document storage — signed-URL upload/download per the security
requirements in ai-job-hunter-db-schema-v1.1.md section 3.

Bytes currently live in the `document_blobs` table (Postgres), keyed by the
same opaque storage_path an object store would use. Swapping in an
S3-compatible bucket later only changes the two functions below; callers
and the documents table stay as they are."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024  # 10MB, matches the UI's stated limit


def build_storage_path(profile_id: str, file_name: str) -> str:
    safe_name = (file_name or "document").replace("/", "_").replace("\\", "_")[-200:]
    return f"profiles/{profile_id}/documents/{uuid.uuid4()}/{safe_name}"


async def save_document_bytes(db: AsyncSession, storage_path: str, content: bytes) -> None:
    from app.models import DocumentBlob

    db.add(DocumentBlob(storage_path=storage_path, content=content, size_bytes=len(content)))


async def load_document_bytes(db: AsyncSession, storage_path: str) -> bytes | None:
    from app.models import DocumentBlob

    blob = (
        await db.execute(select(DocumentBlob).where(DocumentBlob.storage_path == storage_path))
    ).scalar_one_or_none()
    return blob.content if blob else None


async def generate_signed_download_url(storage_path: str, expires_seconds: int = 300) -> str:
    raise NotImplementedError("Generated CV exports are not produced yet; see cv_tailoring_tasks.")
