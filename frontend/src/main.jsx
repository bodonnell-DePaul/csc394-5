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
function App() {

  // Authentication
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [loginError, setLoginError] = useState('');
  
  
  const [patient, setPatient] = useState(null);
  const [symptoms, setSymptoms] = useState([]);
  const [symptomChoice, setSymptomChoice] = useState('');
  const [selectedSymptoms, setSelectedSymptoms] = useState([]);
  const [reports, setReports] = useState([]);
  const [summary, setSummary] = useState(null);
  const [status, setStatus] = useState(null);

  async function handleLogin(email, password) {
  setLoginError('');

  try {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'same-origin',
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      throw new Error(
        response.status === 401
          ? 'Invalid email or password.'
          : 'Unable to sign in. Please try again.'
      );
    }

    const result = await response.json();
    setUser(result.user);
  } catch (error) {
    setLoginError(error.message);
  }
}
async function handleLogout() {
  try {
    const response = await fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'same-origin',
    });

    if (!response.ok) {
      throw new Error('Unable to log out. Please try again.');
    }

    // Clear patient information from React
    setPatient(null);
    setReports([]);
    setSummary(null);
    setSelectedSymptoms([]);
    setSymptomChoice('');
    setStatus(null);
    setLoginError('');

    // Return to the login screen
    setUser(null);
  } catch (error) {
    setStatus({
      message: error.message,
      isError: true,
    });
  }
}

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
  return (
    <div className="container">
      <header className="hero">
        <h1>Healthwatch Demo</h1>

        <button type="button" onClick={handleLogout}>
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

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
