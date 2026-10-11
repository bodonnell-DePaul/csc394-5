from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError

from ..config import AVAILABLE_SYMPTOMS, FIXED_PATIENT_ID


class SymptomReportRequest(BaseModel):
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
