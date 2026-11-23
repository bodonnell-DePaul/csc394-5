import os
from pathlib import Path
# Google OAuth configuration
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get(
    "GOOGLE_REDIRECT_URI",
    "http://localhost:8000/api/auth/google/callback",
)

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
SECOND_DEMO_PATIENT_ID = "22222222-2222-4222-8222-222222222222"
AVAILABLE_SYMPTOMS = [
    "Acid reflux",
    "Change in appetite",
    "Congestion",
    "Cough",
    "Depression",
    "Diarrhea",
    "Dizziness",
    "Fainting",
    "Fatigue",
    "Fever",
    "Flatulence",
    "Hair loss",
    "Hearing impairment",
    "Headache",
    "Indigestion",
    "Nausea",
    "Rash",
    "Seizure",
    "Sleepiness",
    "Sleep disturbance",
    "Shortness of breath",
    "Swelling",
    "Thirst",
    "Tremor",
    "Vomiting",
    "Vision impairment",
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