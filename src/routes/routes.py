from fastapi import APIRouter, HTTPException, Query, status, Depends
from fastapi import APIRouter, HTTPException, Query, status, Depends
from fastapi.responses import FileResponse
from .auth import require_patient_user, require_doctor_user

from ..config import (
    AVAILABLE_MEDICATIONS,
    AVAILABLE_SYMPTOMS,
    FIXED_PATIENT_ID,
    STATIC_DIR,
)
from .database import (
    clear_symptom_reports,
    deactivate_prescription,
    get_patient_profile,
    get_review_counts,
    get_report_summary,
    list_patient_profiles,
    list_prescriptions,
    list_symptom_reports,
    save_symptom_report,
    update_prescription_dosage,
    update_report_review,
)
from ..middleware.schemas import (
    DoctorReviewUpdate,
    DosageUpdateRequest,
    MedicationStatusUpdateRequest,
    SymptomDetail,
    SymptomReportRequest,
)

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


@router.get("/api/medications/")
def get_available_medications() -> dict[str, list[str]]:
    return {"medications": AVAILABLE_MEDICATIONS}


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
        [
            symptom.model_dump()
            if isinstance(symptom, SymptomDetail)
            else symptom
            for symptom in payload.symptoms
        ],
        payload.notes,
        payload.associated_medication,
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


@router.get("/api/medication")
def get_medications(
    patient_id: str = Query(default=FIXED_PATIENT_ID),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(require_patient_user),
) -> dict[str, object]:
    if patient_id != user["patient_id"]:
        raise HTTPException(
            status_code=403,
            detail="Cannot access another patient's medications.",
        )
    require_demo_patient(patient_id)
    medications, total = list_prescriptions(user["patient_id"], limit, offset)
    return {
        "medications": medications,
        "page": {"limit": limit, "offset": offset, "total": total},
    }


@router.patch("/api/medication")
def update_medication_status(
    payload: MedicationStatusUpdateRequest,
    _user: dict = Depends(require_doctor_user),
) -> dict[str, object]:
    if get_patient_profile(payload.patient_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found.",
        )
    if payload.active:
        raise HTTPException(
            status_code=422,
            detail="Inactive medications cannot be reactivated.",
        )

    updated = deactivate_prescription(
        payload.patient_id, payload.medication_name
    )
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Active medication not found.",
        )

    return {
        "message": "Medication marked inactive.",
        "medication_name": payload.medication_name,
        "active": False,
    }


# Demo doctor endpoints protected by role-based authorization.
@router.get("/api/doctor/medications")
def get_patient_medications(
    patient_id: str = Query(...),
    _user: dict = Depends(require_doctor_user),
) -> dict[str, list[dict[str, object]]]:
    if get_patient_profile(patient_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found.",
        )
    medications, _total = list_prescriptions(patient_id, 100, 0)
    return {"medications": medications}


@router.post("/api/doctor/medications", status_code=status.HTTP_201_CREATED)
def add_patient_medication(
    payload: DosageUpdateRequest,
    _user: dict = Depends(require_doctor_user),
) -> dict[str, object]:
    if get_patient_profile(payload.patient_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found.",
        )

    medications, _total = list_prescriptions(payload.patient_id, 100, 0)
    existing = next(
        (
            medication
            for medication in medications
            if medication["medication_name"] == payload.medication_name
        ),
        None,
    )
    if existing and not existing["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This medication is inactive and cannot be reactivated.",
        )

    medication = update_prescription_dosage(
        payload.patient_id,
        payload.medication_name,
        payload.dosage_value,
        payload.dosage_unit,
    )
    return {
        "message": "Patient medication saved.",
        "medication": {**medication, "is_active": True},
    }


@router.get("/api/doctor/patients")
def get_doctor_patients(
    _user: dict = Depends(require_doctor_user),
) -> dict[str, list[dict[str, object]]]:
    return {"patients": list_patient_profiles()}


@router.get("/api/doctor/dashboard")
def get_doctor_dashboard(
    patient_id: str = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _user: dict = Depends(require_doctor_user),
) -> dict[str, object]:
    patient = get_patient_profile(patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient account not found.",
        )
    reports, total = list_symptom_reports(
        patient_id, limit, offset, include_doctor_notes=True
    )
    return {
        "patient": patient,
        "summary": get_report_summary(patient_id),
        "review_counts": get_review_counts(patient_id),
        "reports": reports,
        "page": {"limit": limit, "offset": offset, "total": total},
    }


@router.patch("/api/doctor/reports/{report_id}")
def review_symptom_report(
    report_id: int,
    payload: DoctorReviewUpdate,
    patient_id: str = Query(...),
    _user: dict = Depends(require_doctor_user),
) -> dict[str, object]:
    if get_patient_profile(patient_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found.",
        )
    report = update_report_review(
        report_id, patient_id, payload.review_status, payload.doctor_note
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Symptom report not found.",
        )
    return {"message": "Review saved.", "report": report}
