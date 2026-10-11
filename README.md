# csc394-5
This vertical slice demonstrates one patient feature: select symptoms, submit a report, and see the saved report in the patient's history. It uses a fixed synthetic patient and stores reports in SQLite. It does not include authentication, doctor views, diagnosis, or treatment recommendations.

API
POST /api/symptom_report creates a report for the demo patient.
GET /api/symptom_report?limit=20&offset=0 lists that patient's saved reports.
GET /api/symptoms returns the symptom choices shown by the form.
The demo intentionally uses synthetic data only and is not suitable for real patient information or clinical use.
