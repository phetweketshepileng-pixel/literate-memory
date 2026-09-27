"""JWT auth dependencies, wired to the real Auth module (app.modules.auth.service)
rather than decoding ad hoc — token type validation ('access' vs a stray
JWT) and expiry both matter and are easy to accidentally skip if this
duplicates the decode logic instead of importing it."""
from __future__ import annotations

from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.service import decode_access_token


async def get_current_user_id(authorization: str = Header(...)) -> UUID:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "FORBIDDEN", "message": "Missing bearer token"})
    token = authorization.removeprefix("Bearer ")
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail={"code": "FORBIDDEN", "message": "Invalid or expired token"}) from exc
    return UUID(payload["sub"])


async def require_admin(
    authorization: str = Header(...), db: AsyncSession = Depends(get_db)
) -> UUID:
    """Unlike get_current_user_id, this checks the role claim embedded in
    the token AND is a separate dependency — an endpoint depending on
    get_current_user_id alone never grants admin access, and one depending
    on require_admin rejects any non-admin token outright."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "FORBIDDEN", "message": "Missing bearer token"})
    token = authorization.removeprefix("Bearer ")
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail={"code": "FORBIDDEN", "message": "Invalid or expired token"}) from exc

    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Admin access required"})
    return UUID(payload["sub"])
