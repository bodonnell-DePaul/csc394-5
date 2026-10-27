from typing import Literal

from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError

from ..config import AVAILABLE_SYMPTOMS, FIXED_PATIENT_ID


class SymptomReportRequest(BaseModel):
    model_config = {"extra": "forbid"}

    patient_id: str = FIXED_PATIENT_ID
    symptoms: list[str]
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("symptoms")
    @classmethod
    def validate_symptoms(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()

        for symptom in value:
            cleaned_name = symptom.strip()
            if not cleaned_name:
                continue
            if cleaned_name not in AVAILABLE_SYMPTOMS:
                raise ValueError(f"Unsupported symptom: {cleaned_name}")
            if cleaned_name not in seen:
                cleaned.append(cleaned_name)
                seen.add(cleaned_name)

        if not cleaned:
            raise PydanticCustomError(
                "empty_symptoms",
                "Please select at least one symptom.",
            )

        return cleaned

    @field_validator("notes", mode="before")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Notes must be text.")

        cleaned_notes = value.strip()
        return cleaned_notes or None


class DoctorReviewUpdate(BaseModel):
    review_status: Literal["pending", "reviewed"]
    doctor_note: str = Field(default="", max_length=1000)

    @field_validator("doctor_note")
    @classmethod
    def clean_doctor_note(cls, value: str) -> str:
        return value.strip()


class MedicationDetails(BaseModel):
    dosage_value: float = Field(gt=0, allow_inf_nan=False)
    dosage_unit: Literal["mg", "mcg", "ml", "g", "tablets"]
    frequency: str = Field(default="", max_length=120)
    instructions: str = Field(default="", max_length=1000)
    active: bool = True

    @field_validator("frequency", "instructions")
    @classmethod
    def clean_medication_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned and len(value) != 0:
            raise ValueError("Medication text cannot be blank.")
        return cleaned


class MedicationRequest(MedicationDetails):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def clean_medication_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Medication name cannot be blank.")
        return cleaned


class MedicationUpdate(MedicationDetails):
    model_config = {"extra": "forbid"}
