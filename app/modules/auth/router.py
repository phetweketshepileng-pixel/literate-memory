"""Auth router. Register/login/refresh/logout, backed by refresh_tokens
for revocable, rotatable sessions per the V1.1 security review."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Profile, RefreshToken, User
from app.modules.auth.service import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_token_expiry,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


async def _issue_tokens(db: AsyncSession, user: User) -> TokenResponse:
    access_token = create_access_token(user_id=str(user.id), role=user.role)

    raw_refresh = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id, token_hash=hash_refresh_token(raw_refresh), expires_at=refresh_token_expiry()
        )
    )
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=raw_refresh)


@router.post("/register", status_code=201, response_model=TokenResponse)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409, detail={"code": "VALIDATION_ERROR", "message": "Email already registered"}
        )

    user = User(email=payload.email, password_hash=hash_password(payload.password), role="user")
    db.add(user)
    await db.flush()

    # Every user gets an empty Profile row at registration — every other
    # module's routers assume exactly one Profile per User (Profile.UNIQUE
    # on user_id) and load it via this relationship without a null check.
    db.add(Profile(user_id=user.id))
    await db.commit()
    await db.refresh(user)

    return await _issue_tokens(db, user)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail={"code": "FORBIDDEN", "message": "Invalid email or password"})
    if not user.is_active:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Account is deactivated"})

    return await _issue_tokens(db, user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    token_hash = hash_refresh_token(payload.refresh_token)
    existing = (
        await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    ).scalar_one_or_none()

    if existing is None or existing.revoked_at is not None or existing.expires_at < datetime.now(UTC):
        raise HTTPException(
            status_code=401, detail={"code": "FORBIDDEN", "message": "Refresh token invalid or expired"}
        )

    user = (await db.execute(select(User).where(User.id == existing.user_id))).scalar_one()

    # Rotation: issue a new refresh token, revoke the old one, chain them
    # via replaced_by — reused-token detection is possible later precisely
    # because this chain exists (V1.1 review, refresh-token audit design).
    new_raw = generate_refresh_token()
    new_token = RefreshToken(
        user_id=user.id, token_hash=hash_refresh_token(new_raw), expires_at=refresh_token_expiry()
    )
    db.add(new_token)
    await db.flush()

    existing.revoked_at = datetime.now(UTC)
    existing.replaced_by = new_token.id
    await db.commit()

    access_token = create_access_token(user_id=str(user.id), role=user.role)
    return TokenResponse(access_token=access_token, refresh_token=new_raw)


@router.post("/logout", status_code=204)
async def logout(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> None:
    token_hash = hash_refresh_token(payload.refresh_token)
    existing = (
        await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    ).scalar_one_or_none()
    if existing is not None and existing.revoked_at is None:
        existing.revoked_at = datetime.now(UTC)
        await db.commit()
