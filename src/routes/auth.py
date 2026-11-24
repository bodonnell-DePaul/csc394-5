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
from urllib.parse import urlencode
from fastapi import Request
from fastapi.responses import RedirectResponse
import httpx
from authlib.jose import JsonWebKey, JsonWebToken
import hashlib
import threading
import time
from ..config import GOOGLE_CLIENT_SECRET
from ..config import GOOGLE_CLIENT_ID, GOOGLE_REDIRECT_URI
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

    # Google OAuth authentication
GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_STATE_COOKIE = "healthwatch_oauth_state"
OAUTH_STATE_LIFETIME = 600


def google_patient_login_available() -> bool:
    """Google login is optional; password login works without provider settings."""
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI)


@router.get("/providers")
def auth_providers():
    """Expose provider availability without exposing OAuth credentials."""
    return {"google_patient_login": google_patient_login_available()}

# Store hashes rather than raw OAuth state values.
_oauth_states = {}
_oauth_states_lock = threading.Lock()


def register_oauth_state(state: str) -> str:
    """Store a short-lived OAuth state and return its nonce."""
    state_hash = hashlib.sha256(state.encode()).hexdigest()
    nonce = secrets.token_urlsafe(32)
    expires_at = time.time() + OAUTH_STATE_LIFETIME

    with _oauth_states_lock:
        now = time.time()

        expired = [
            key
            for key, entry in _oauth_states.items()
            if entry["expires_at"] <= now
        ]

        for key in expired:
            del _oauth_states[key]

        _oauth_states[state_hash] = {
            "expires_at": expires_at,
            "nonce": nonce,
        }

    return nonce


def consume_oauth_state(state: str) -> str | None:
    """Consume an OAuth state once and return its nonce."""
    state_hash = hashlib.sha256(state.encode()).hexdigest()

    with _oauth_states_lock:
        entry = _oauth_states.pop(state_hash, None)

    if entry is None or entry["expires_at"] <= time.time():
        return None

    return entry["nonce"]

@router.get("/google")
def start_google_oauth():
    if not google_patient_login_available():
        raise HTTPException(
            status_code=503,
            detail="Google sign-in is unavailable. Please use email and password.",
        )

    # Generate a unique state to protect against OAuth login CSRF.
    state = secrets.token_urlsafe(32)
    nonce = register_oauth_state(state)

    parameters = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
    }

    authorization_url = (
        GOOGLE_AUTHORIZATION_URL + "?" + urlencode(parameters)
    )

    response = RedirectResponse(url=authorization_url, status_code=302)

    response.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=state,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
        max_age=600,
        path="/api/auth/google",
    )

    return response

def exchange_google_code(code: str, expected_nonce: str) -> dict:
    """Exchange a Google authorization code for a verified identity."""

    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise RuntimeError("Google OAuth credentials are not configured.")

    with httpx.Client(timeout=10.0) as client:
        token_response = client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        token_response.raise_for_status()
        tokens = token_response.json()

        id_token = tokens["id_token"]

        keys_response = client.get(
            "https://www.googleapis.com/oauth2/v3/certs"
        )
        keys_response.raise_for_status()
        google_keys = JsonWebKey.import_key_set(keys_response.json())

    # Only accept Google's RS256 signing algorithm.
    verifier = JsonWebToken(["RS256"])

    claims = verifier.decode(
        id_token,
        google_keys,
        claims_options={
            "iss": {
                "essential": True,
                "values": [
                    "https://accounts.google.com",
                    "accounts.google.com",
                ],
            },
            "aud": {
                "essential": True,
                "value": GOOGLE_CLIENT_ID,
            },
            "exp": {"essential": True},
            "sub": {"essential": True},
            "email": {"essential": True},
            "email_verified": {"essential": True},
            "nonce": {
                "essential": True,
                "value": expected_nonce,
            },
        },
    )

    claims.validate()

    return {
        "sub": claims["sub"],
        "email": claims["email"],
        "email_verified": claims["email_verified"],
    }

@router.get("/google/callback")
def google_oauth_callback(
    request: Request,
    response: Response,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """Handle Google OAuth callback for existing Healthwatch patients."""
    if not google_patient_login_available():
        raise HTTPException(
            status_code=503,
            detail="Google sign-in is unavailable. Please use email and password.",
        )

    expected_state = request.cookies.get(OAUTH_STATE_COOKIE)

    # Validate state against the browser cookie FIRST.
    if (
        not state
        or not expected_state
        or not secrets.compare_digest(state, expected_state)
        ):
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state.",
        )

    # Consume state once and retrieve its associated nonce.
    expected_nonce = consume_oauth_state(state)

    if expected_nonce is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OAuth state.",
        )

    if error:
        raise HTTPException(
            status_code=400,
            detail="Google authentication was canceled or denied.",
        )

    if not code:
        raise HTTPException(
            status_code=400,
            detail="Missing Google authorization code.",
        )

    # Exchange authorization code for verified Google identity.
    try:
        google_identity = exchange_google_code(code, expected_nonce)
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Unable to verify Google authentication.",
        )

    # Reject incomplete or unverified identities.
    if (
        not isinstance(google_identity, dict)
        or not isinstance(google_identity.get("sub"), str)
        or not google_identity["sub"]
        or not isinstance(google_identity.get("email"), str)
        or not google_identity["email"].strip()
        or google_identity.get("email_verified") is not True
    ):
        raise HTTPException(
            status_code=403,
            detail="Google account could not be verified.",
        )

    # Allow only existing patient accounts.
    email = google_identity["email"].strip().lower()
    user = get_user_by_email(email)

    if user is None or user["role"] != "patient":
        raise HTTPException(
            status_code=403,
            detail="No authorized patient account found.",
        )

    # Create Healthwatch session.
    token = secrets.token_urlsafe(32)
    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(seconds=SESSION_DURATION)
    ).isoformat()

    create_session(user["id"], token, expires_at)

    redirect = RedirectResponse(url="/", status_code=302)

    redirect.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
        max_age=SESSION_DURATION,
        path="/",
    )

    # Remove OAuth state cookie after successful login.
    redirect.delete_cookie(
        key=OAUTH_STATE_COOKIE,
        path="/api/auth/google",
    )

    return redirect