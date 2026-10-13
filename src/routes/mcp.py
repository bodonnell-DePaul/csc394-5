from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from ..config import AVAILABLE_SYMPTOMS, FIXED_PATIENT_ID
from ..middleware.schemas import SymptomReportRequest
from .database import (
    get_patient_profile,
    get_report_summary,
    list_symptom_reports as fetch_symptom_reports,
    save_symptom_report,
)

mcp = FastMCP("Healthwatch")


def _validate_patient_id(patient_id: str) -> None:
    if patient_id != FIXED_PATIENT_ID:
        raise ValueError("Patient not found.")


@mcp.tool
def get_patient(patient_id: str = FIXED_PATIENT_ID) -> dict[str, Any]:
    """Get the demo patient's profile."""
    _validate_patient_id(patient_id)
    return get_patient_profile(patient_id)


@mcp.tool
def get_symptoms() -> list[str]:
    """List the symptom choices available for a report."""
    return AVAILABLE_SYMPTOMS


@mcp.tool
def get_symptom_report_summary(
    patient_id: str = FIXED_PATIENT_ID,
) -> dict[str, Any]:
    """Summarize the demo patient's symptom report history."""
    _validate_patient_id(patient_id)
    return get_report_summary(patient_id)


@mcp.tool
def submit_symptom_report(
    symptoms: list[str],
    notes: str | None = None,
    patient_id: str = FIXED_PATIENT_ID,
) -> dict[str, Any]:
    """Save a symptom report for the demo patient."""
    _validate_patient_id(patient_id)
    request = SymptomReportRequest(
        patient_id=patient_id,
        symptoms=symptoms,
        notes=notes,
    )
    return save_symptom_report(
        request.patient_id,
        request.symptoms,
        request.notes,
    )


@mcp.tool
def list_symptom_reports(
    patient_id: str = FIXED_PATIENT_ID,
    limit: Annotated[int, Field(ge=1, le=100)] = 20,
    offset: Annotated[int, Field(ge=0)] = 0,
) -> dict[str, Any]:
    """List the demo patient's symptom reports, newest first."""
    _validate_patient_id(patient_id)
    reports, total = fetch_symptom_reports(patient_id, limit, offset)
    return {
        "reports": reports,
        "page": {
            "limit": limit,
            "offset": offset,
            "total": total,
        },
    }
