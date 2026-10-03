"""Auth router. Register/login/refresh/logout, backed by refresh_tokens
for revocable, rotatable sessions per the V1.1 security review."""
from __future__ import annotations

import hmac
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.email import email_configured, send_email
from app.core.security import get_current_user_id
from app.models import AuthEmailToken, Profile, RefreshToken, User
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


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    reset_code: str
    new_password: str


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
async def register(payload: RegisterRequest, background: BackgroundTasks, db: AsyncSession = Depends(get_db)) -> TokenResponse:
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

    if email_configured():
        link = await _new_email_link(db, user, "verify")
        background.add_task(_send_verify_email, user.email, link)
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


# Wrong reset codes are rate limited: after MAX_RESET_FAILURES within the
# window, every attempt is refused until the window passes (stops guessing).
MAX_RESET_FAILURES = 5
RESET_WINDOW_SECONDS = 15 * 60
MIN_RESET_CODE_LENGTH = 12
_reset_failures: list[float] = []


def _reset_locked(now: float) -> bool:
    _reset_failures[:] = [t for t in _reset_failures if now - t < RESET_WINDOW_SECONDS]
    return len(_reset_failures) >= MAX_RESET_FAILURES


@router.post("/reset-password", status_code=204)
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)) -> None:
    """Self-service reset for a forgotten password, authorised by the
    PASSWORD_RESET_CODE secret that only the site owner knows (no email
    service is configured yet). Signs the account out everywhere."""
    expected = settings.PASSWORD_RESET_CODE.strip()
    if len(expected) < MIN_RESET_CODE_LENGTH:
        raise HTTPException(status_code=503, detail={"code": "NOT_CONFIGURED",
            "message": "Password reset isn't set up yet: add a PASSWORD_RESET_CODE variable (12+ characters) to the backend in Railway."})
    now = time.monotonic()
    if _reset_locked(now):
        raise HTTPException(status_code=429, detail={"code": "RATE_LIMITED",
            "message": "Too many wrong reset codes. Wait 15 minutes and try again."})
    if not hmac.compare_digest(payload.reset_code.strip().encode(), expected.encode()):
        _reset_failures.append(now)
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "That reset code is not right."})
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "The new password needs at least 8 characters."})
    user = (await db.execute(select(User).where(User.email == payload.email.lower()))).scalar_one_or_none()
    if user is None:
        user = (await db.execute(select(User).where(User.email.ilike(payload.email)))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "No account uses that email."})
    user.password_hash = hash_password(payload.new_password)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await db.commit()


# ===================== Email verification & emailed reset links =====================

VERIFY_LINK_HOURS = 72
RESET_LINK_MINUTES = 60
MAX_LINK_EMAILS_PER_ADDRESS_PER_HOUR = 3
_link_email_log: dict[str, list[float]] = {}


def _link_email_allowed(email: str, now: float) -> bool:
    """At most a few emails per address per hour, so the form can't be used
    to flood someone's inbox (or burn the 300/day email allowance)."""
    sent = [t for t in _link_email_log.get(email, []) if now - t < 3600]
    _link_email_log[email] = sent
    if len(sent) >= MAX_LINK_EMAILS_PER_ADDRESS_PER_HOUR:
        return False
    sent.append(now)
    return True


async def _new_email_link(db: AsyncSession, user: User, purpose: str) -> str:
    """Creates a one-time token (only its hash is stored), voiding older
    unused links of the same kind, and returns the full link for the email."""
    now = datetime.now(UTC)
    await db.execute(
        update(AuthEmailToken)
        .where(AuthEmailToken.user_id == user.id, AuthEmailToken.purpose == purpose, AuthEmailToken.used_at.is_(None))
        .values(used_at=now)
    )
    raw = generate_refresh_token()
    life = timedelta(hours=VERIFY_LINK_HOURS) if purpose == "verify" else timedelta(minutes=RESET_LINK_MINUTES)
    db.add(AuthEmailToken(user_id=user.id, purpose=purpose, token_hash=hash_refresh_token(raw), expires_at=now + life))
    await db.commit()
    return f"{settings.APP_URL.rstrip('/')}/#{purpose}={raw}"


async def _use_email_token(db: AsyncSession, raw: str, purpose: str) -> AuthEmailToken:
    token = (
        await db.execute(select(AuthEmailToken).where(AuthEmailToken.token_hash == hash_refresh_token(raw.strip())))
    ).scalar_one_or_none()
    if token is None or token.purpose != purpose or token.used_at is not None or token.expires_at < datetime.now(UTC):
        what = "password reset" if purpose == "reset" else "verification"
        raise HTTPException(status_code=400, detail={"code": "LINK_INVALID",
            "message": f"This {what} link has expired or was already used. Please ask for a new one."})
    token.used_at = datetime.now(UTC)
    return token


async def _send_verify_email(to: str, link: str) -> None:
    await send_email(to, "Confirm your email for Ascend",
                     "Welcome to Ascend!\n\nPlease confirm this is your email address, so you can reset your password if you ever forget it.",
                     "Confirm my email", link)


async def _send_reset_email(to: str, link: str) -> None:
    await send_email(to, "Reset your Ascend password",
                     f"Someone (hopefully you) asked to reset the password for this Ascend account.\n\nThe link works once and expires in {RESET_LINK_MINUTES} minutes.",
                     "Choose a new password", link)


class EmailRequest(BaseModel):
    email: EmailStr


class TokenPasswordRequest(BaseModel):
    token: str
    new_password: str


class TokenRequest(BaseModel):
    token: str


@router.get("/me")
async def me(user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
    return {"data": {"email": user.email, "email_verified": user.email_verified_at is not None,
                     "email_enabled": email_configured()}, "meta": {}, "error": None}


@router.post("/forgot-password", status_code=202)
async def forgot_password(payload: EmailRequest, background: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Emails a reset link. Always answers the same way, so it can't be used
    to find out which emails have accounts."""
    if not email_configured():
        raise HTTPException(status_code=503, detail={"code": "NOT_CONFIGURED",
            "message": "Reset emails aren't set up on this site yet. Use 'Have a reset code?' instead."})
    email = payload.email.lower()
    if _link_email_allowed(email, time.monotonic()):
        user = (await db.execute(select(User).where(User.email.ilike(email)))).scalar_one_or_none()
        if user is not None and user.is_active:
            link = await _new_email_link(db, user, "reset")
            background.add_task(_send_reset_email, user.email, link)
    return {"data": {"message": "If an account uses that email, a reset link is on its way. Check your inbox and spam folder."},
            "meta": {}, "error": None}


@router.post("/reset-password-link", status_code=204)
async def reset_password_with_link(payload: TokenPasswordRequest, db: AsyncSession = Depends(get_db)) -> None:
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "The new password needs at least 8 characters."})
    token = await _use_email_token(db, payload.token, "reset")
    user = (await db.execute(select(User).where(User.id == token.user_id))).scalar_one()
    user.password_hash = hash_password(payload.new_password)
    # following a link from the inbox proves the address, too
    user.email_verified_at = user.email_verified_at or datetime.now(UTC)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await db.commit()


@router.post("/verify-email", status_code=204)
async def verify_email(payload: TokenRequest, db: AsyncSession = Depends(get_db)) -> None:
    token = await _use_email_token(db, payload.token, "verify")
    user = (await db.execute(select(User).where(User.id == token.user_id))).scalar_one()
    user.email_verified_at = user.email_verified_at or datetime.now(UTC)
    await db.commit()


@router.post("/resend-verification", status_code=202)
async def resend_verification(background: BackgroundTasks, user_id: UUID = Depends(get_current_user_id),
                              db: AsyncSession = Depends(get_db)):
    if not email_configured():
        raise HTTPException(status_code=503, detail={"code": "NOT_CONFIGURED", "message": "Emails aren't set up on this site yet."})
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
    if user.email_verified_at is None:
        if not _link_email_allowed(user.email.lower(), time.monotonic()):
            raise HTTPException(status_code=429, detail={"code": "RATE_LIMITED", "message": "We've sent a few already. Please wait an hour and check your spam folder."})
        link = await _new_email_link(db, user, "verify")
        background.add_task(_send_verify_email, user.email, link)
    return {"data": {"message": "Confirmation email sent."}, "meta": {}, "error": None}


# ===================== Privacy: site info, data export, account deletion (POPIA) =====================

@router.get("/site-info")
async def site_info():
    """Public details the privacy notice shows (no sign-in needed)."""
    return {"data": {"privacy_contact": settings.PRIVACY_CONTACT_EMAIL or settings.EMAIL_FROM or None},
            "meta": {}, "error": None}


def _jsonable(value):
    import uuid as _uuid
    from datetime import date as _date, datetime as _dt
    from decimal import Decimal
    if isinstance(value, (_dt, _date)):
        return value.isoformat()
    if isinstance(value, (_uuid.UUID, Decimal)):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return None
    return value


_EXPORT_SKIP_COLUMNS = {"password_hash", "token_hash"}


@router.post("/export")
async def export_my_data(user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """Everything Ascend holds about you, as one JSON file (POPIA right of access).
    Uploaded files themselves can be downloaded from My Profile."""
    from fastapi.responses import JSONResponse
    from app.models import Base, DataRequest

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one_or_none()
    out: dict = {"exported_at": datetime.now(UTC).isoformat(),
                 "account": {c.name: _jsonable(getattr(user, c.key)) for c in User.__table__.columns
                             if c.name not in _EXPORT_SKIP_COLUMNS}}
    for table in Base.metadata.sorted_tables:
        if table.name in ("users", "document_blobs", "refresh_tokens", "auth_email_tokens"):
            continue
        key = "profile_id" if "profile_id" in table.c else ("user_id" if "user_id" in table.c else None)
        if table.name == "profiles":
            key, owner = "user_id", user_id
        elif key == "profile_id":
            owner = profile.id if profile else None
        elif key == "user_id":
            owner = user_id
        if not key or owner is None:
            continue
        rows = (await db.execute(table.select().where(table.c[key] == owner))).mappings().all()
        if rows:
            out[table.name] = [{k: _jsonable(v) for k, v in r.items() if k not in _EXPORT_SKIP_COLUMNS} for r in rows]
    db.add(DataRequest(user_id=user_id, request_type="export", status="completed", completed_at=datetime.now(UTC)))
    await db.commit()
    return JSONResponse(out, headers={"Content-Disposition": 'attachment; filename="ascend-my-data.json"'})


class DeleteAccountRequest(BaseModel):
    password: str
    confirm: str


@router.post("/delete-account", status_code=204)
async def delete_account(payload: DeleteAccountRequest, user_id: UUID = Depends(get_current_user_id),
                         db: AsyncSession = Depends(get_db)) -> None:
    """Permanently deletes the account and everything linked to it (POPIA
    right to deletion). Needs the password and the word DELETE."""
    from sqlalchemy import delete, text as sql_text
    from app.models import Document, DocumentBlob

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
    if payload.confirm.strip().upper() != "DELETE":
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "Type DELETE to confirm."})
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "That password is not right."})
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one_or_none()
    if profile is not None:
        paths = list((await db.execute(select(Document.storage_path).where(Document.profile_id == profile.id))).scalars())
        if paths:  # file contents aren't linked by a foreign key, so remove them explicitly
            await db.execute(delete(DocumentBlob).where(DocumentBlob.storage_path.in_(paths)))
    await db.execute(sql_text("DELETE FROM activity_logs WHERE user_id = :u"), {"u": user_id})
    # a plain DELETE lets Postgres cascade to the profile, CVs, applications,
    # tokens etc. (ON DELETE CASCADE); the ORM would try to unlink them instead
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()


# ===================== Feedback: what real users tell us =====================

FEEDBACK_PER_USER_PER_HOUR = 5
FEEDBACK_PER_DAY = 100          # stays well inside the free email allowance
_feedback_log: dict[str, list[float]] = {}


def _feedback_allowed(key: str, now: float) -> bool:
    user_sent = [t for t in _feedback_log.get(key, []) if now - t < 3600]
    all_sent = [t for t in _feedback_log.get("*", []) if now - t < 86400]
    _feedback_log[key], _feedback_log["*"] = user_sent, all_sent
    if len(user_sent) >= FEEDBACK_PER_USER_PER_HOUR or len(all_sent) >= FEEDBACK_PER_DAY:
        return False
    user_sent.append(now)
    all_sent.append(now)
    return True


class FeedbackRequest(BaseModel):
    message: str
    screen: str | None = None
    may_contact: bool = False


@router.post("/feedback", status_code=202)
async def send_feedback(payload: FeedbackRequest, background: BackgroundTasks,
                        user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """Emails a signed-in user's feedback to the site owner."""
    message = payload.message.strip()[:3000]
    if len(message) < 3:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "Please write a few words."})
    to = settings.FEEDBACK_EMAIL or settings.PRIVACY_CONTACT_EMAIL or settings.EMAIL_FROM
    if not (email_configured() and to):
        raise HTTPException(status_code=503, detail={"code": "UNAVAILABLE", "message": "Feedback isn't switched on yet."})
    if not _feedback_allowed(str(user_id), time.monotonic()):
        raise HTTPException(status_code=429, detail={"code": "RATE_LIMITED", "message": "Thanks — you've sent a lot just now. Please try again later."})
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
    who = f"From: {user.email} (happy to be contacted)" if payload.may_contact else "From: a signed-in user (asked not to be contacted)"
    screen = (payload.screen or "").strip()[:40]
    body = f"{who}\nScreen: {screen or 'not given'}\n\n{message}"
    background.add_task(send_email, to, "Ascend feedback" + (f" ({screen})" if screen else ""), body)
    return {"data": {"message": "Thank you — your feedback was sent."}, "meta": {}, "error": None}
