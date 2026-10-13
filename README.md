# Healthwatch symptom-reporting demo

This vertical slice demonstrates one patient feature: 

## User Story: 
patient selects the symptoms associated with their prescription use, patient submits a report, to which the doctor then sees the saved report in the patient's history from their interface. 

# Frontend:
An example of a UI component to use Healthwatch will include a drop-down menu of the the types of symptoms patients can log through either clicking or pressing on the symptom name box, depending on whether they are interacting with a mobile or desktop interface. If a patient presses/clicks on the option other, then they are allowed to write their symptoms through a text box. Next, we will implement a button to press/click on which states "log symptoms". 
As for the doctor interface, we can include another button which allows them to make modifications, and from there will inlcude a drop down menu with options that include creating an appointment or changing prescription dosage.
It uses a fixed synthetic patient and stores reports in SQLite. It does not include authentication, doctor views, diagnosis, or treatment recommendations.

## API

- `POST /api/symptom_report` creates a report for the demo patient.
- `GET /api/symptom_report?limit=20&offset=0` lists that patient's saved reports.
- `GET /api/symptoms` returns the symptom choices shown by the form.

The demo intentionally uses synthetic data only and is not suitable for real patient information or clinical use.
