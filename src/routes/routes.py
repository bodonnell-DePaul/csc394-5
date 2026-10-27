from fastapi import APIRouter, HTTPException, Query, status, Depends
from fastapi.responses import FileResponse
from .auth import require_patient_user, require_doctor_user

from ..config import AVAILABLE_SYMPTOMS, FIXED_PATIENT_ID, STATIC_DIR
from .database import (
    clear_symptom_reports,
    get_patient_profile,
    get_review_counts,
    get_report_summary,
    list_symptom_reports,
    save_symptom_report,
    update_report_review,
)
from ..middleware.schemas import DoctorReviewUpdate, SymptomReportRequest

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
def get_patient(
    patient_id: str = FIXED_PATIENT_ID,
    user: dict = Depends(require_patient_user),
) -> dict[str, object]:
    require_demo_patient(patient_id)
    return {
        "patient": {
            "id": user["patient_id"],
            "email": user["email"],
        }
    }


@router.get("/api/symptoms")
def get_symptoms() -> dict[str, list[str]]:
    return {"symptoms": AVAILABLE_SYMPTOMS}


@router.get("/api/symptom_report/summary")
def get_summary(
    patient_id: str = FIXED_PATIENT_ID,
    _user: dict = Depends(require_patient_user),
) -> dict[str, object]:
    require_demo_patient(patient_id)
    return {"summary": get_report_summary(patient_id)}


@router.post("/api/symptom_report", status_code=status.HTTP_201_CREATED)
def create_symptom_report(
    payload: SymptomReportRequest,
    user: dict = Depends(require_patient_user),
) -> dict[str, object]:
    require_demo_patient(payload.patient_id)

    if payload.patient_id != user["patient_id"]:
        raise HTTPException(
            status_code=403,
            detail="Cannot submit reports for another patient.",
        )

    report = save_symptom_report(
        user["patient_id"],
        payload.symptoms,
        payload.notes,
    )

    return {
        "message": "Symptom report saved.",
        "report": report,
    }


@router.delete("/api/symptom_report")
def clear_reports(
    patient_id: str = Query(default=FIXED_PATIENT_ID),
    user: dict = Depends(require_patient_user),
) -> dict[str, object]:

    if patient_id != user["patient_id"]:
        raise HTTPException(
            status_code=403,
            detail="Cannot delete another patient's reports.",
        )

    require_demo_patient(patient_id)

    deleted_rows = clear_symptom_reports(user["patient_id"])

    return {
        "message": "Symptom history cleared.",
        "deleted_rows": deleted_rows,
    }


@router.get("/api/symptom_report")
def list_reports(
    patient_id: str = Query(default=FIXED_PATIENT_ID),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(require_patient_user),
) -> dict[str, object]:
    if patient_id != user["patient_id"]:
        raise HTTPException(
            status_code=403,
            detail="Cannot access another patient's reports.",
        )

    require_demo_patient(patient_id)

    reports, total = list_symptom_reports(
        user["patient_id"], limit, offset
    )

    return {
        "reports": reports,
        "page": {
            "limit": limit,
            "offset": offset,
            "total": total,
        },
    }


# Demo doctor endpoints protected by role-based authorization.
@router.get("/api/doctor/dashboard")
def get_doctor_dashboard(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _user: dict = Depends(require_doctor_user),
) -> dict[str, object]:
    reports, total = list_symptom_reports(
        FIXED_PATIENT_ID, limit, offset, include_doctor_notes=True
    )
    patient = get_patient_profile(FIXED_PATIENT_ID)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient account not found.",
        )
    return {
        "patient": patient,
        "summary": get_report_summary(FIXED_PATIENT_ID),
        "review_counts": get_review_counts(FIXED_PATIENT_ID),
        "reports": reports,
        "page": {"limit": limit, "offset": offset, "total": total},
    }


@router.patch("/api/doctor/reports/{report_id}")
def review_symptom_report(
    report_id: int,
    payload: DoctorReviewUpdate,
    _user: dict = Depends(require_doctor_user),
) -> dict[str, object]:
    report = update_report_review(
        report_id, FIXED_PATIENT_ID, payload.review_status, payload.doctor_note
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Symptom report not found.",
        )
    return {"message": "Review saved.", "report": report}
