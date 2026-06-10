"""Authorization primitive tests.

The clinical-decision endpoints (sign, accept/reject/refine finding,
set RADS, approve plan) now depend on ``require_role("clinician",
"admin")``. This exercises that dependency directly — it raises 403 for
an out-of-scope role and returns the user for an allowed role — without
needing a DB-backed TestClient.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import HTTPException

from app.core.security import require_role


@dataclass
class StubUser:
    role: str


def _resolve(dep, user):
    """Call the FastAPI dependency callable the way the framework would,
    with `current_user` already resolved to `user`."""
    return dep(user=user)


def test_require_role_allows_listed_role():
    dep = require_role("clinician", "admin")
    user = StubUser(role="clinician")
    assert _resolve(dep, user) is user


def test_require_role_allows_admin():
    dep = require_role("clinician", "admin")
    user = StubUser(role="admin")
    assert _resolve(dep, user) is user


def test_require_role_rejects_unlisted_role():
    dep = require_role("clinician", "admin")
    user = StubUser(role="tech")
    with pytest.raises(HTTPException) as exc:
        _resolve(dep, user)
    assert exc.value.status_code == 403


def test_require_role_admin_only_rejects_clinician():
    dep = require_role("admin")
    with pytest.raises(HTTPException) as exc:
        _resolve(dep, StubUser(role="clinician"))
    assert exc.value.status_code == 403
