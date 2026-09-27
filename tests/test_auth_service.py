import time

import jwt
import pytest

from app.modules.auth.service import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def test_hash_password_produces_different_hash_each_time():
    # argon2 includes a random salt — same password, different hash
    h1 = hash_password("correct horse battery staple")
    h2 = hash_password("correct horse battery staple")
    assert h1 != h2


def test_verify_password_correct():
    h = hash_password("my-secret-password")
    assert verify_password("my-secret-password", h) is True


def test_verify_password_incorrect():
    h = hash_password("my-secret-password")
    assert verify_password("wrong-password", h) is False


def test_verify_password_never_raises_on_garbage_hash():
    # a corrupted/garbage hash should return False, not crash
    assert verify_password("anything", "not-a-real-hash") is False


def test_access_token_roundtrip():
    token = create_access_token(user_id="abc-123", role="user")
    payload = decode_access_token(token)
    assert payload["sub"] == "abc-123"
    assert payload["role"] == "user"


def test_access_token_rejects_tampered_signature():
    token = create_access_token(user_id="abc-123", role="user")
    tampered = token[:-4] + "abcd"
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(tampered)


def test_access_token_carries_role_for_admin_gating():
    token = create_access_token(user_id="admin-1", role="admin")
    payload = decode_access_token(token)
    assert payload["role"] == "admin"


def test_refresh_token_is_high_entropy_and_unique():
    t1 = generate_refresh_token()
    t2 = generate_refresh_token()
    assert t1 != t2
    assert len(t1) > 40


def test_refresh_token_hash_is_deterministic_and_never_stores_raw():
    raw = generate_refresh_token()
    h1 = hash_refresh_token(raw)
    h2 = hash_refresh_token(raw)
    assert h1 == h2  # same input -> same hash, needed to look it up later
    assert h1 != raw  # never store the raw token itself
    assert len(h1) == 64  # sha256 hex digest length
