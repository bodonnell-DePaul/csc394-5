import os
from pathlib import Path

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
SAFE_DOSE_RANGES={"warfarin"= {"mg": (1, 10)}}