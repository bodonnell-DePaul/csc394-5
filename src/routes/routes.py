from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from ..config import AVAILABLE_SYMPTOMS, FIXED_PATIENT_ID, STATIC_DIR
from .database import (
    clear_symptom_reports,
    get_patient_profile,
    get_report_summary,
    list_symptom_reports,
    save_symptom_report,
)
from ..middleware.schemas import SymptomReportRequest

router = APIRouter()


def require_demo_patient(patient_id: str) -> None:
    if patient_id != FIXED_PATIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found.",
        )


@router.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/patient")
def get_patient(patient_id: str = FIXED_PATIENT_ID) -> dict[str, object]:
    require_demo_patient(patient_id)
    return {"patient": get_patient_profile(patient_id)}


@router.get("/api/symptoms")
def get_symptoms() -> dict[str, list[str]]:
    return {"symptoms": AVAILABLE_SYMPTOMS}


@router.get("/api/symptom_report/summary")
def get_summary(patient_id: str = FIXED_PATIENT_ID) -> dict[str, object]:
    require_demo_patient(patient_id)
    return {"summary": get_report_summary(patient_id)}


@router.post("/api/symptom_report", status_code=status.HTTP_201_CREATED)
def create_symptom_report(payload: SymptomReportRequest) -> dict[str, object]:
    require_demo_patient(payload.patient_id)
    report = save_symptom_report(
        payload.patient_id,
        payload.symptoms,
        payload.notes,
    )
    return {
        "message": "Symptom report saved.",
        "report": report,
    }


@router.delete("/api/symptom_report")
def clear_reports(patient_id: str = Query(default=FIXED_PATIENT_ID)) -> dict[str, object]:
    require_demo_patient(patient_id)
    deleted_rows = clear_symptom_reports(patient_id)
    return {
        "message": "Symptom history cleared.",
        "deleted_rows": deleted_rows,
    }


@router.get("/api/symptom_report")
def list_reports(
    patient_id: str = Query(default=FIXED_PATIENT_ID),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    require_demo_patient(patient_id)
    reports, total = list_symptom_reports(patient_id, limit, offset)
    return {
        "reports": reports,
        "page": {
            "limit": limit,
            "offset": offset,
            "total": total,
        },
    }
