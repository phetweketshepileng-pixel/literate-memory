"""Download my data / Delete my account (POPIA) helpers."""
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.modules.auth import router as auth


def test_export_values_become_json_safe():
    u = uuid.uuid4()
    assert auth._jsonable(u) == str(u)
    assert auth._jsonable(datetime(2026, 10, 3, tzinfo=UTC)).startswith("2026-10-03T")
    assert auth._jsonable(Decimal("1.5")) == "1.5"
    assert auth._jsonable(b"raw") is None          # file bytes never go in the export
    assert auth._jsonable({"a": 1}) == {"a": 1}


def test_export_never_includes_secrets():
    assert {"password_hash", "token_hash"} <= auth._EXPORT_SKIP_COLUMNS
