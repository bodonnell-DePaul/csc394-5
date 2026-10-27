"""Seed the built-in synthetic demo accounts without replacing existing users."""
import logging
from dataclasses import dataclass
from typing import Literal

from ..config import FIXED_PATIENT_ID
from .auth import hash_password
from .database import create_user, get_user_by_email

logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class DemoAccount:
    email: str
    password: str
    role: Literal["patient", "doctor"]
    patient_id: str | None


DEMO_ACCOUNTS = (
    DemoAccount(
        email="patient@example.com",
        password="PatientPassword123!",
        role="patient",
        patient_id=FIXED_PATIENT_ID,
    ),
    DemoAccount(
        email="doctor@example.com",
        password="DoctorPassword123!",
        role="doctor",
        patient_id=None,
    ),
)


def seed_demo_accounts() -> None:
    """Create missing demo users; never overwrite existing credentials."""
    for account in DEMO_ACCOUNTS:
        if get_user_by_email(account.email) is not None:
            continue

        create_user(
            email=account.email,
            password_hash=hash_password(account.password),
            role=account.role,
            patient_id=account.patient_id,
        )
        logger.info("Seeded demo %s account.", account.role)