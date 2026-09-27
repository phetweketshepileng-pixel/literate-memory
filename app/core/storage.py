"""Encrypted object storage — signed-URL upload/download per the security
requirements in ai-job-hunter-db-schema-v1.1.md section 3. Stub here;
production implementation wraps an S3-compatible SDK with SSE-KMS."""
from __future__ import annotations

import uuid

from fastapi import UploadFile


async def upload_to_encrypted_storage(file: UploadFile, profile_id: str) -> str:
    """Returns the opaque storage_path key. Never a public URL — downloads
    are always mediated through a signed-URL endpoint."""
    key = f"profiles/{profile_id}/documents/{uuid.uuid4()}/{file.filename}"
    # Real implementation: stream file.file to S3-compatible storage with
    # SSE-KMS server-side encryption, return `key` unchanged.
    return key


async def generate_signed_download_url(storage_path: str, expires_seconds: int = 300) -> str:
    raise NotImplementedError("Wire up to the object storage provider's signed-URL API.")
