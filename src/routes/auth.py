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
from ..config import (
    FIXED_PATIENT_ID,
    SECOND_DEMO_PATIENT_ID,
    SESSION_COOKIE_SECURE,
)

from .database import (
    assign_doctor_staff_id,
    create_user,
    create_session,
    delete_session,
    get_patient_profile,
    get_session_user,
    get_user_by_email,
    update_user_patient_id,
)
router = APIRouter(prefix="/api/auth", tags=["Authentication"])
@router.get("/status")
def auth_status():
    return {
        "message": "Healthwatch authentication router is working"
    }
password_hasher = PasswordHasher()

DEMO_ACCOUNTS = (
    {
        "email": "patient@example.com",
        "password": "PatientPassword123!",
        "role": "patient",
        "patient_id": FIXED_PATIENT_ID,
    },
    {
        "email": "patient2@example.com",
        "password": "PatientPassword456!",
        "role": "patient",
        "patient_id": SECOND_DEMO_PATIENT_ID,
    },
    {
        "email": "doctor@example.com",
        "password": "DoctorPassword123!",
        "role": "doctor",
        "patient_id": None,
        "doctor_staff_id": "742619",
    },
)


def seed_demo_accounts() -> None:
    """Create the documented demo accounts when they are not already present."""
    for account in DEMO_ACCOUNTS:
        existing_user = get_user_by_email(account["email"])
        if existing_user is None:
            create_user(
                email=account["email"],
                password_hash=hash_password(account["password"]),
                role=account["role"],
                patient_id=account["patient_id"],
                doctor_staff_id=account.get("doctor_staff_id"),
            )
        elif (
            account["role"] == "doctor"
            and existing_user["doctor_staff_id"] is None
        ):
            assign_doctor_staff_id(
                account["email"], account["doctor_staff_id"]
            )
        elif (
            account["role"] == "patient"
            and existing_user["patient_id"] != account["patient_id"]
        ):
            update_user_patient_id(
                account["email"], account["patient_id"]
            )


class LoginRequest(BaseModel):
    email: str
    password: str
    doctor_staff_id: str | None = None


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

    valid_password = bool(user) and verify_password(
        payload.password, user["password_hash"]
    )
    valid_staff_id = False
    if user and user["role"] == "doctor":
        valid_staff_id = bool(payload.doctor_staff_id) and bool(
            user["doctor_staff_id"]
        ) and secrets.compare_digest(
            payload.doctor_staff_id.strip(), user["doctor_staff_id"]
        )
    elif user and user["role"] == "patient":
        # A patient cannot use the doctor-specific sign-in form.
        valid_staff_id = payload.doctor_staff_id is None

    if not valid_password or not valid_staff_id:
        # Do not reveal whether the password or assigned doctor ID was wrong.
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
        secure=SESSION_COOKIE_SECURE,
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
    """Require a patient account assigned to a valid patient profile."""

    if user["role"] != "patient":
        raise HTTPException(
            status_code=403,
            detail="Patient access required.",
        )

    patient_id = user.get("patient_id")
    if not patient_id or get_patient_profile(patient_id) is None:
        raise HTTPException(
            status_code=403,
            detail="Access to this patient is forbidden.",
        )

    return user

def require_doctor_user(
    user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Allow only authenticated doctor accounts."""

    if user["role"] != "doctor":
        raise HTTPException(
            status_code=403,
            detail="Doctor access required.",
        )

    return user