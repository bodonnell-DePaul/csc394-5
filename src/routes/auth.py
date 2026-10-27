"""Authentication and authorization for Healthwatch."""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from fastapi import APIRouter
from fastapi import HTTPException, status
from pydantic import BaseModel
from typing import Any
from ..config import FIXED_PATIENT_ID

from .database import (
    create_session,
    delete_session,
    get_session_user,
    get_user_by_email,
)
router = APIRouter(prefix="/api/auth", tags=["Authentication"])
@router.get("/status")
def auth_status():
    return {
        "message": "Healthwatch authentication router is working"
    }
password_hasher = PasswordHasher()
class LoginRequest(BaseModel):
    email: str
    password: str


def hash_password(password: str) -> str:
    """Securely hash a password before storing it."""
    return password_hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    """Check whether a password matches its stored hash."""
    try:
        return password_hasher.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False

SESSION_COOKIE = "healthwatch_session"
SESSION_DURATION = 60 * 60 * 8  # 8 hours


@router.post("/login")
def login(payload: LoginRequest, response: Response):
    user = get_user_by_email(payload.email)

    if not user or not verify_password(
        payload.password, user["password_hash"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = secrets.token_urlsafe(32)
    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(seconds=SESSION_DURATION)
    ).isoformat()

    create_session(user["id"], token, expires_at)

    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=False,  # Local HTTP development only
        samesite="lax",
        max_age=SESSION_DURATION,
        path="/",
    )

    return {
        "message": "Login successful.",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "role": user["role"],
        },
    }
    

@router.post("/logout")
def logout(
    response: Response,
    healthwatch_session: str | None = Cookie(default=None),
):
    if healthwatch_session:
        delete_session(healthwatch_session)

    response.delete_cookie(
        key=SESSION_COOKIE,
        path="/",
    )

    return {"message": "Logged out successfully."}


@router.get("/me")
def get_current_user(
    healthwatch_session: str | None = Cookie(default=None),
):
    if not healthwatch_session:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated.",
        )

    user = get_session_user(healthwatch_session)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session.",
        )

    return {"user": user}

def require_authenticated_user(
    healthwatch_session: str | None = Cookie(default=None),
) -> dict[str, Any]:
    """Require a valid session before accessing protected data."""
    if not healthwatch_session:
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
        )

    user = get_session_user(healthwatch_session)

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session.",
        )

    return user
def require_patient_user(
    user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Require a patient account assigned to the demo patient."""

    if user["role"] != "patient":
        raise HTTPException(
            status_code=403,
            detail="Patient access required.",
        )

    if user["patient_id"] != FIXED_PATIENT_ID:
        raise HTTPException(
            status_code=403,
            detail="Access to this patient is forbidden.",
        )

    return user