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

function LoginForm({ onLogin, error }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);

    try {
      await onLogin(email, password);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-page">
      <form className="login-form" onSubmit={handleSubmit}>
        <h1>Healthwatch</h1>
        <p>Sign in to access your patient dashboard.</p>

        <label htmlFor="login-email">Email</label>
        <input
          id="login-email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          autoComplete="username"
          required
        />

        <label htmlFor="login-password">Password</label>
        <input
          id="login-password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          required
        />

        {error && <p role="alert">{error}</p>}

        <button type="submit" disabled={loading}>
          {loading ? 'Signing in...' : 'Sign In'}
        </button>
      </form>
    </main>
  );
}
function PatientDashboard({ user, onLogout }) {
  
  
  const [patient, setPatient] = useState(null);
  const [symptoms, setSymptoms] = useState([]);
  const [symptomChoice, setSymptomChoice] = useState('');
  const [selectedSymptoms, setSelectedSymptoms] = useState([]);
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
    if (!user) return;

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
  }, [user]);

  async function submitReport(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);

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
      setSymptomChoice('');
      setSelectedSymptoms([]);
      setStatus({ message: 'Symptom report saved.', isError: false });
      await refreshHistory();
    } catch (error) {
      setStatus({ message: error.message, isError: true });
    }
  }
  
  return (
    <div className="container">
      <header className="hero">
        <h1>Healthwatch Demo</h1>

        <button type="button" onClick={onLogout}>
          Log Out
        </button>
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
                <Stat label="Care team" value={patient.care_team} />
              </>
            ) : (
              <p>Loading patient profile…</p>
            )}
          </div>

          <h2>Submit a symptom report</h2>
          <form onSubmit={submitReport}>
            <div className="field">
              <label className="field-label" htmlFor="symptom-select">
                Add a symptom
              </label>
              <select
                id="symptom-select"
                value={symptomChoice}
                onChange={(event) => {
                  const symptom = event.target.value;
                  setSymptomChoice('');
                  if (symptom && !selectedSymptoms.includes(symptom)) {
                    setSelectedSymptoms([...selectedSymptoms, symptom]);
                  }
                }}
              >
                <option value="">Choose a symptom</option>
                {symptoms.map((symptom) => (
                  <option key={symptom} value={symptom}>
                    {symptom}
                  </option>
                ))}
              </select>
              {selectedSymptoms.length > 0 && (
                <ul className="selected-symptoms" aria-label="Selected symptoms">
                  {selectedSymptoms.map((symptom) => (
                    <li className="selected-symptom" key={symptom}>
                      <span>{symptom}</span>
                      <button
                        type="button"
                        className="remove-symptom"
                        aria-label={`Remove ${symptom}`}
                        onClick={() =>
                          setSelectedSymptoms(
                            selectedSymptoms.filter((item) => item !== symptom),
                          )
                        }
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

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
          <div>
            {reports.length === 0 ? (
              <p>No symptom reports saved yet.</p>
            ) : (
              reports.map((report) => (
                <article className="history-item" key={report.id}>
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


function DoctorDashboard() {
  const [dashboard, setDashboard] = useState(null);
  const [filter, setFilter] = useState('all');
  const [drafts, setDrafts] = useState({});
  const [busyId, setBusyId] = useState(null);
  const [message, setMessage] = useState('');

  async function loadDashboard() {
    const data = await requestJson('/api/doctor/dashboard?limit=100');
    setDashboard(data);
  }

  useEffect(() => {
    let active = true;
    requestJson('/api/doctor/dashboard?limit=100')
      .then((data) => { if (active) setDashboard(data); })
      .catch((error) => { if (active) setMessage(error.message); });
    return () => { active = false; };
  }, []);

  async function saveReview(report, reviewStatus) {
    setBusyId(report.id);
    setMessage('');
    try {
      await requestJson(`/api/doctor/reports/${report.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          review_status: reviewStatus,
          doctor_note: drafts[report.id] ?? report.doctor_note ?? '',
        }),
      });
      await loadDashboard();
      setMessage('Review saved successfully.');
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusyId(null);
    }
  }

  const displayed = (dashboard?.reports ?? []).filter(
    (report) => filter === 'all' || report.review_status === filter
  );
  return (
    <main className="doctor-layout">
      <div className="doctor-heading">
        <div><h2>Doctor dashboard</h2><p>Demo review workspace for synthetic patient reports.</p></div>
        <button className="secondary-button" onClick={() => loadDashboard().catch((error) => setMessage(error.message))}>Refresh reports</button>
      </div>
      <div className="patient-card dashboard-stats">
        <Stat label="Total reports" value={dashboard?.page.total ?? '—'} />
        <Stat label="Pending review" value={dashboard?.review_counts.pending ?? '—'} />
        <Stat label="Reviewed" value={dashboard?.review_counts.reviewed ?? '—'} />
        <Stat label="Patient" value={dashboard?.patient.name ?? 'Loading…'} />
      </div>
      <section className="panel">
        <div className="doctor-toolbar">
          <h2>Patient symptom reports</h2>
          <label>Show <select value={filter} onChange={(event) => setFilter(event.target.value)}>
            <option value="all">All reports</option>
            <option value="pending">Pending</option>
            <option value="reviewed">Reviewed</option>
          </select></label>
        </div>
        <p className="muted">
          Doctor notes are only visible to authorized doctors and are not shown in the patient's symptom history.
        </p>
        <div role="status" aria-live="polite" className="status">{message}</div>
        {!dashboard && !message && <p>Loading reports…</p>}
        {dashboard && displayed.length === 0 && <p>No reports match this filter.</p>}
        {displayed.map((report) => (
          <article className="history-item doctor-report" key={report.id}>
            <div className="doctor-report-top">
              <div><strong>Report #{report.id}</strong><div className="meta">{new Date(report.submitted_at).toLocaleString()}</div></div>
              <span className={`review-badge ${report.review_status}`}>{report.review_status === 'reviewed' ? 'Reviewed' : 'Pending review'}</span>
            </div>
            <div className="pill-list">{report.symptoms.map((symptom) => <span className="pill" key={symptom}>{symptom}</span>)}</div>
            <p><strong>Patient notes:</strong> {report.notes || 'No additional details'}</p>
            <label className="field-label" htmlFor={`doctor-note-${report.id}`}>Doctor review notes</label>
            <textarea id={`doctor-note-${report.id}`} maxLength={1000} rows={3}
              value={drafts[report.id] ?? report.doctor_note ?? ''}
              onChange={(event) => setDrafts((old) => ({...old, [report.id]: event.target.value}))}
              placeholder="Enter review notes (demo only)" />
            <div className="button-row review-actions">
              <button disabled={busyId !== null} onClick={() => saveReview(report, 'reviewed')}>Mark reviewed & save</button>
              <button disabled={busyId !== null} className="secondary-button" onClick={() => saveReview(report, 'pending')}>Save as pending</button>
            </div>
          </article>
        ))}
        {dashboard && dashboard.page.total > dashboard.reports.length && <p className="muted">Showing the latest {dashboard.reports.length} reports out of {dashboard.page.total}.</p>}
      </section>
    </main>
  );
}

function HealthwatchApp() {
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [loginError, setLoginError] = useState('');

  // Check whether the user already has an active session.
  useEffect(() => {
    let active = true;

    async function checkSession() {
      try {
        const result = await requestJson('/api/auth/me');

        if (active) {
          setUser(result.user);
        }
      } catch (error) {
        if (active) {
          setUser(null);
        }
      } finally {
        if (active) {
          setAuthLoading(false);
        }
      }
    }

    checkSession();

    return () => {
      active = false;
    };
  }, []);

  async function handleLogin(email, password) {
    setLoginError('');

    try {
      const result = await requestJson('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'same-origin',
        body: JSON.stringify({ email, password }),
      });

      setUser(result.user);
    } catch (error) {
      setLoginError(error.message);
    }
  }

  async function handleLogout() {
    try {
      await requestJson('/api/auth/logout', {
        method: 'POST',
        credentials: 'same-origin',
      });

      setUser(null);
      setLoginError('');
    } catch (error) {
      alert(`Unable to log out: ${error.message}`);
    }
  }

  if (authLoading) {
    return <main className="login-page">Checking session...</main>;
  }

  if (!user) {
    return (
      <LoginForm
        onLogin={handleLogin}
        error={loginError}
      />
    );
  }

  if (user.role === 'patient') {
    return (
      <PatientDashboard
        user={user}
        onLogout={handleLogout}
      />
    );
  }

  if (user.role === 'doctor') {
    return (
      <div className="container">
        <header className="hero">
          <h1>Healthwatch Doctor Dashboard</h1>
          <button type="button" onClick={handleLogout}>
            Log Out
          </button>
        </header>
        <DoctorDashboard />
      </div>
    );
  }

  return <main className="login-page">Your account role is not supported.</main>;
}

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <HealthwatchApp />
  </React.StrictMode>,
);
