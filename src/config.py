import os
from pathlib import Path

_secure_cookie_setting = os.environ.get(
    "HEALTHWATCH_COOKIE_SECURE", "false"
).strip().lower()
if _secure_cookie_setting not in {"true", "false"}:
    raise ValueError("HEALTHWATCH_COOKIE_SECURE must be 'true' or 'false'")

SESSION_COOKIE_SECURE = _secure_cookie_setting == "true"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / "src" / "public"
DB_PATH = Path(
    os.environ.get(
        "HEALTHWATCH_DB_PATH",
        str(PROJECT_ROOT / "src" / "data" / "healthwatch.db"),
    )
)

FIXED_PATIENT_ID = "11111111-1111-2111-6111-111111111111"
AVAILABLE_SYMPTOMS = [
    "Dizziness",
    "Fatigue",
    "Headache",
    "Nausea",
    "Rash",
    "Shortness of breath",
    "Sleep disturbance",
    "Swelling",
    "Tremor",
    "Vomiting",
]

AVAILABLE_MEDICATIONS = [
    "Lexapro",
    "Amoxicillin",
    "Fluoxetine",
    "Metformin",
    "Bupropion",
    "Warfarin",
]

SAFE_DOSE_RANGES = {
    "warfarin": {"mg": (1.0, 10.0)},
    "lexapro": {"mg": (5.0, 20.0)},
    "amoxicillin": {"mg": (250.0, 875.0)},
    "fluoxetine": {"mg": (10.0, 80.0)},
    "metformin": {"mg": (500.0, 2550.0)},
    "bupropion": {"mg": (75.0, 450.0)},
}