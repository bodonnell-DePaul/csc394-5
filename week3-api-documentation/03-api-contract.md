# API contract

## Conventions
- Request and response bodies use JSON. UUIDS can be used to identify, tickets, symptom logs, and medications.
- Malformed JSON, malformed path UUIDS and unknown parameters receive 400 BAD_REQUEST. Invalid JSON fields or values will receive 422 VALIDATION_ERROR.
- The server reports all safely detectable field errors together rather than discovering them one request at a time.
- Single resource bodies are packaged with the resource itself. Collection bodies use page;

## Endpoint API

|Endpoint Method & Path| Purpose & Inputs| Success & Error Response|
|---|---|---|
| POST /api/tickets/{ticketid} | change ticket status to resolved;| 200: request confirmation |
| GET /api/tickets | tickets; optional resolved = true or false, optional patientID, limit, offset | 200: ticket collection |
| GET /api/tickets/{ticketid} | specific ticket | 200: ticket | 200:ticket|
| POST /api/symptom_report | update health history; patientID, symptoms| 200: request confirmation |
| GET /api/symptom_report | patient's symptom reports; patientID, limit, offset| 200: symptom_report collection|
| POST /api/medication | update health prescription; patientID, medicationID| 200: request confirmation |
| GET /api/medication | health prescription; patientID, limit, offset| 200: medication collection|

example using synthetic data:
~~~
{
  "medications": [
  {
    "id": "11111111-1111-4111-8111-111111111111",
    "name": "Benadryl",
    "manufacturer": "Kenvue"
  }
  ],
  "page":{"limit":20,"offset":0,"total":1}
}
    
~~~
## Rules
for validation, permissions, conflicts, retries, filtering, or pagination when applicable


## Acceptance tests
|ID|Action|Success|
|---|---|---|
| | | |
