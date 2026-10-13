import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const result = await response.json();

  if (!response.ok) {
    const detail = Array.isArray(result.detail)
      ? result.detail[0]?.msg
      : result.detail;
    throw new Error(detail || 'The request could not be completed.');
  }

  return result;
}

function App() {
  const [patient, setPatient] = useState(null);
  const [symptoms, setSymptoms] = useState([]);
  const [reports, setReports] = useState([]);
  const [summary, setSummary] = useState(null);
  const [status, setStatus] = useState(null);

  async function refreshHistory() {
    const [reportResult, summaryResult] = await Promise.all([
      requestJson('/api/symptom_report?limit=20&offset=0'),
      requestJson('/api/symptom_report/summary'),
    ]);
    setReports(reportResult.reports);
    setSummary(summaryResult.summary);
  }

  useEffect(() => {
    let active = true;

    async function loadDemo() {
      try {
        const [patientResult, symptomsResult, reportResult, summaryResult] =
          await Promise.all([
            requestJson('/api/patient'),
            requestJson('/api/symptoms'),
            requestJson('/api/symptom_report?limit=20&offset=0'),
            requestJson('/api/symptom_report/summary'),
          ]);

        if (active) {
          setPatient(patientResult.patient);
          setSymptoms(symptomsResult.symptoms);
          setReports(reportResult.reports);
          setSummary(summaryResult.summary);
        }
      } catch (error) {
        if (active) {
          setStatus({ message: error.message, isError: true });
        }
      }
    }

    loadDemo();
    return () => {
      active = false;
    };
  }, []);

  async function submitReport(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    const selectedSymptoms = formData.getAll('symptom');

    if (!selectedSymptoms.length) {
      setStatus({
        message: 'Please select at least one symptom.',
        isError: true,
      });
      return;
    }

    try {
      await requestJson('/api/symptom_report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symptoms: selectedSymptoms,
          notes: formData.get('notes'),
        }),
      });

      form.reset();
      setStatus({ message: 'Symptom report saved.', isError: false });
      await refreshHistory();
    } catch (error) {
      setStatus({ message: error.message, isError: true });
    }
  }

  async function clearReportHistory() {
    try {
      const result = await requestJson('/api/symptom_report', {
        method: 'DELETE',
      });
      setStatus({
        message: `Cleared ${result.deleted_rows} saved report(s).`,
        isError: false,
      });
      await refreshHistory();
    } catch (error) {
      setStatus({ message: error.message, isError: true });
    }
  }

  return (
    <div className="container">
      <header className="hero">
        <h1>Healthwatch Demo</h1>
        <p>Patient symptom logging for a synthetic demo patient.</p>
      </header>

      <main className="grid">
        <section className="panel" aria-labelledby="patient-heading">
          <h2 id="patient-heading">Patient profile</h2>
          <div className="patient-card">
            {patient ? (
              <>
                <Stat label="Patient" value={patient.name} />
                <Stat label="Age" value={patient.age} />
                <Stat label="Gender" value={patient.gender} />
                <Stat label="Condition" value={patient.condition} />
                <Stat label="Care team" value={patient.care_team} />
              </>
            ) : (
              <p>Loading patient profile…</p>
            )}
          </div>

          <h2>Submit a symptom report</h2>
          <form onSubmit={submitReport}>
            <div className="field">
              <span className="field-label">Patient</span>
              <div>{patient?.id || 'Loading patient ID…'}</div>
            </div>

            <fieldset className="field symptom-field">
              <legend className="field-label">Select symptoms</legend>
              <div className="checklist">
                {symptoms.map((symptom) => (
                  <label className="checkbox-item" key={symptom}>
                    <input type="checkbox" name="symptom" value={symptom} />
                    <span>{symptom}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            <div className="field">
              <label className="field-label" htmlFor="report-notes">
                Additional details (optional)
              </label>
              <textarea
                id="report-notes"
                name="notes"
                rows="4"
                maxLength="1000"
                placeholder="Add any details about your symptoms (up to 1,000 characters)."
              />
            </div>

            <div className="button-row">
              <button type="submit">Submit report</button>
              <button
                type="button"
                className="button-danger"
                onClick={clearReportHistory}
              >
                Clear database
              </button>
            </div>
            <div
              className={`status${status?.isError ? ' error' : status ? ' success' : ''}`}
              role="status"
              aria-live="polite"
            >
              {status?.message}
            </div>
          </form>
        </section>

        <section className="panel" aria-labelledby="history-heading">
          <h2 id="history-heading">Saved symptom history</h2>
          {summary && (
            <div className="patient-card">
              <Stat label="Total reports" value={summary.total_reports} />
              <Stat
                label="Logged symptoms"
                value={summary.total_symptom_entries}
              />
            </div>
          )}
          <button
            type="button"
            className="button-danger history-clear"
            onClick={clearReportHistory}
          >
            Clear saved history
          </button>
          <div>
            {reports.length === 0 ? (
              <p>No symptom reports saved yet.</p>
            ) : (
              reports.map((report) => (
                <article className="history-item" key={report.id}>
                  <h3>Report #{report.id}</h3>
                  <div className="meta">
                    Submitted: {new Date(report.submitted_at).toLocaleString()}
                  </div>
                  <div className="pill-list">
                    {report.symptoms.map((symptom) => (
                      <span className="pill" key={symptom}>
                        {symptom}
                      </span>
                    ))}
                  </div>
                  {report.notes && (
                    <p className="report-notes">{report.notes}</p>
                  )}
                </article>
              ))
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="stat-box">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
