from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from ..config import (
    AVAILABLE_MEDICATIONS,
    AVAILABLE_SYMPTOMS,
    FIXED_PATIENT_ID,
    SAFE_DOSE_RANGES,
)


class SymptomDetail(BaseModel):
    name: str = Field(..., min_length=1)
    severity: int = Field(..., ge=1, le=10)
    location: str = Field(default="Unspecified", max_length=200)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned_name = value.strip()
        if cleaned_name not in AVAILABLE_SYMPTOMS:
            raise ValueError(f"Unsupported symptom: {cleaned_name}")
        return cleaned_name

    @field_validator("location", mode="before")
    @classmethod
    def clean_location(cls, value: str | None) -> str:
        if value is None:
            return "Unspecified"
        cleaned_location = str(value).strip()
        return cleaned_location or "Unspecified"


class SymptomReportRequest(BaseModel):
    patient_id: str = FIXED_PATIENT_ID
    symptoms: list[SymptomDetail | str]
    notes: str | None = Field(default=None, max_length=1000)
    associated_medication: str | None = Field(default=None, min_length=1)
    medication_name: str | None = Field(default=None, min_length=1)
    dosage_value: float | None = Field(default=None, gt=0)
    dosage_unit: str | None = Field(
        default=None,
        pattern="^(mg|mcg|ml|g|tablets)$",
    )
    @field_validator("symptoms")
    @classmethod
    def validate_symptoms(
        cls, value: list[SymptomDetail | str]
    ) -> list[SymptomDetail | str]:
        cleaned: list[SymptomDetail | str] = []
        seen: set[str] = set()

        for symptom in value:
            cleaned_name = (
                symptom.name if isinstance(symptom, SymptomDetail) else symptom.strip()
            )
            if not cleaned_name:
                continue
            if cleaned_name not in AVAILABLE_SYMPTOMS:
                raise ValueError(f"Unsupported symptom: {cleaned_name}")
            if cleaned_name not in seen:
                cleaned.append(symptom if isinstance(symptom, SymptomDetail) else cleaned_name)
                seen.add(cleaned_name)

        if not cleaned:
            raise PydanticCustomError(
                "empty_symptoms",
                "Please select at least one symptom.",
            )

        return cleaned

    @field_validator("associated_medication")
    @classmethod
    def validate_associated_medication(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned_name = value.strip()
        for medication in AVAILABLE_MEDICATIONS:
            if medication.casefold() == cleaned_name.casefold():
                return medication
        raise ValueError("Unsupported medication.")

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

class DosageUpdateRequest(BaseModel):
    patient_id: str = FIXED_PATIENT_ID
    medication_name: str = Field(..., min_length=1)
    dosage_value: float = Field(..., gt=0, description="Dosage must be greater than 0")
    dosage_unit: str

    @field_validator("medication_name")
    @classmethod
    def clean_medication(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def check_safe_range(self):
        limits = SAFE_DOSE_RANGES.get(self.medication_name, {}).get(self.dosage_unit)
        if limits is None:
            return self  # unknown medication or unit: no range to check
        low, high = limits
        if not low <= self.dosage_value <= high:
            raise ValueError(
                f"{self.dosage_value} {self.dosage_unit} is outside the safe range "
                f"for {self.medication_name} ({low}-{high} {self.dosage_unit})."
            )
        return self


class MedicationRemoveRequest(BaseModel):
    patient_id: str = FIXED_PATIENT_ID
    medication_name: str = Field(..., min_length=1)

    @field_validator("medication_name")
    @classmethod
    def clean_medication(cls, value: str) -> str:
        return value.strip().lower()


class MedicationStatusUpdateRequest(BaseModel):
    patient_id: str = FIXED_PATIENT_ID
    medication_name: str = Field(..., min_length=1)
    active: bool

    @field_validator("medication_name")
    @classmethod
    def clean_medication(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("Medication name cannot be empty.")
        return cleaned
