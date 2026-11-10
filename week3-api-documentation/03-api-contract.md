# API contract

## Conventions
- Business requests require Authorization: bearer <access-token>
- Request and response bodies use JSON. UUIDS can be used to identify, tickets, symptom logs, and medications.
- Malformed JSON, malformed path UUIDS and unknown parameters receive 400 BAD_REQUEST. Invalid JSON fields or values will receive 422 VALIDATION_ERROR.
- The server reports all safely detectable field errors together rather than discovering them one request at a time.
- Single resource bodies are packaged with the resource itself. Collection bodies use page;
- limit is restricted to 1 through 100. offset is an integer from 0 to 10000.

## Endpoint API

|Endpoint Method & Path| Purpose & Inputs| Success & Error Response|
|---|---|---|
| PATCH /api/tickets/{ticketid} | change ticket status to resolved;| 200: request confirmation |
| GET /api/tickets | tickets; optional resolved = true or false, optional patientID, limit, offset | 200: ticket collection |
| GET /api/tickets/{ticketid} | specific ticket | 200: ticket | 200:ticket|
| POST /api/symptom_report | update health history; patientID, symptoms| 200: request confirmation |
| GET /api/symptom_report | patient's symptom reports; patientID, limit, offset| 200: symptom_report collection|
| PATCH /api/medication | Doctor only; JSON body with `patient_id`, `medication_name`, and `active: false` to mark a prescription inactive. Inactive prescriptions cannot be reactivated or deleted. | 200: update confirmation; 401/403: authentication or role failure; 404: patient or active medication not found; 422: invalid request or reactivation attempt |
| GET /api/medication | Patient only; optional `patient_id`, `limit` (1-100), and `offset` (0 or greater). Returns that patient's prescriptions, including inactive records. | 200: paginated medication collection; 401/403: authentication or patient-scope failure |

example using synthetic data:
~~~
GET /api/medication?patient_id=11111111-1111-2111-6111-111111111111&limit=20&offset=0
Authorization: Bearer <access-token>
~~~
~~~
{
  "medications": [
    {
      "patient_id": "11111111-1111-2111-6111-111111111111",
      "medication_name": "warfarin",
      "dosage_value": 3,
      "dosage_unit": "mg",
      "updated_at": "2026-01-01T12:00:00+00:00",
      "is_active": 1
    }
  ],
  "page":{"limit":20,"offset":0,"total":1}
}
    
~~~

## Patient symptom-reporting demo

The vertical-slice demo implements only symptom reporting for one fixed synthetic patient. It does not implement authentication; it must not be used with real health information.

`GET /api/symptoms` returns the symptom choices supported by the form.

`POST /api/symptom_report` accepts `application/json` with exactly these fields:

```json
{
  "patientID": "11111111-1111-2111-6111-111111111111",
  "symptoms": ["Nausea", "Headache"]
}


## Acceptance tests
|ID|Action|Success|
|---|---|---|
| AT-01 | Sent Symptom Report | adds one persistent symptom report |
| AT-02 | List own medication; get/patch another patient's medication  | No foreign medication in list; 403 for both requests|
| AT-03 | Patient attempts to get/patch tickets | 403 |
| AT-04 | List patients symptoms | 403 |
| AT-05 | Submit malformed JSON, or non-JSON body | 400 for malformed json; 415 for unsupported media type|
| AT-06 | Rate limit, unexpected server error | safe 429/500 envelope; Retry-After on 429; no fake success|
| AT-07 | View a known tickets details, request a nonexistent ticket; supply a malformed path UUID | 200 with appropriate fields; 404 for missing ID; 400 for malformed pathID |
