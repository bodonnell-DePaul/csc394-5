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
const patientNavigation = [
  { id: 'overview', label: 'Overview', icon: '⌂' },
  { id: 'medications', label: 'My medications', icon: '+' },
  { id: 'reports', label: 'Symptom reports', icon: '▤' },
  { id: 'new-report', label: 'New report', icon: '✚' },
];

const doctorNavigation = [
  { id: 'overview', label: 'Overview', icon: '⌂' },
  { id: 'reports', label: 'Patient reports', icon: '▤' },
  { id: 'medications', label: 'Medications', icon: '+' },
];

function PortalLayout({
  role,
  userName,
  navigation,
  section,
  onNavigate,
  onLogout,
  onRefresh,
  refreshing,
  title,
  subtitle,
  children,
}) {
  const activeNavigation = navigation.find((item) => item.id === section);

  return (
    <div className="portal-shell">
      <aside className="portal-sidebar">
        <a className="portal-brand" href="#overview" onClick={() => onNavigate('overview')}>
          <span className="brand-mark">H</span>
          <span>healthwatch</span>
        </a>
        <div className="sidebar-user">
          <span className="user-avatar">{userName?.slice(0, 1) ?? 'H'}</span>
          <span className="sidebar-user-copy">
            <strong>{userName || 'Healthwatch user'}</strong>
            <span>{role === 'patient' ? 'Patient portal' : 'Care team portal'}</span>
          </span>
        </div>
        <span className="sidebar-section-label">Workspace</span>
        <nav className="portal-nav" aria-label="Portal navigation">
          {navigation.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`portal-nav-link${section === item.id ? ' active' : ''}`}
              aria-current={section === item.id ? 'page' : undefined}
              onClick={() => onNavigate(item.id)}
            >
              <span className="nav-icon" aria-hidden="true">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-help">
          <span className="help-icon" aria-hidden="true">?</span>
          <strong>Need help?</strong>
          <p>Contact your care team for questions about your health record.</p>
        </div>
        <div className="sidebar-footer">
          <span className="online-dot" />
          Secure demo environment
        </div>
      </aside>
      <div className="portal-workspace">
        <header className="portal-topbar">
          <div className="portal-heading">
            <span className="breadcrumb">
              Healthwatch <span>/</span> {activeNavigation?.label}
            </span>
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>
          <div className="topbar-actions">
            <div className="date-chip">
              <span className="date-icon" aria-hidden="true">◷</span>
              <span>
                <strong>Today</strong>
                <small>{new Date().toLocaleDateString(undefined, {
                  weekday: 'short',
                  month: 'short',
                  day: 'numeric',
                })}</small>
              </span>
            </div>
            {onRefresh && (
              <button
                type="button"
                className={`icon-button${refreshing ? ' is-refreshing' : ''}`}
                onClick={onRefresh}
                disabled={refreshing}
                aria-label="Refresh portal data"
                title="Refresh"
              >
                ↻
              </button>
            )}
            <button type="button" className="logout-button" onClick={onLogout}>
              Log out
            </button>
          </div>
        </header>
        <main className="portal-content">{children}</main>
      </div>
    </div>
  );
}

function PatientDashboard({ user, onLogout }) {
  const [patient, setPatient] = useState(null);
  const [symptoms, setSymptoms] = useState([]);
  const [symptomChoice, setSymptomChoice] = useState('');
  const [selectedSymptoms, setSelectedSymptoms] = useState([]);
  const [medications, setMedications] = useState([]);
  const [reports, setReports] = useState([]);
  const [summary, setSummary] = useState(null);
  const [status, setStatus] = useState(null);
  const [section, setSection] = useState('overview');
  const [medicationFilter, setMedicationFilter] = useState('active');
  const [refreshing, setRefreshing] = useState(false);

  async function refreshPortal() {
    setRefreshing(true);
    try {
      const [patientResult, symptomsResult, medicationResult, reportResult, summaryResult] =
        await Promise.all([
          requestJson('/api/patient'),
          requestJson('/api/symptoms'),
          requestJson('/api/medications'),
          requestJson('/api/symptom_report?limit=20&offset=0'),
          requestJson('/api/symptom_report/summary'),
        ]);
      setPatient(patientResult.patient);
      setSymptoms(symptomsResult.symptoms);
      setMedications(medicationResult.medications);
      setReports(reportResult.reports);
      setSummary(summaryResult.summary);
    } catch (error) {
      setStatus({ message: error.message, isError: true });
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    let active = true;

    async function loadPortal() {
      try {
        const [patientResult, symptomsResult, medicationResult, reportResult, summaryResult] =
          await Promise.all([
            requestJson('/api/patient'),
            requestJson('/api/symptoms'),
            requestJson('/api/medications'),
            requestJson('/api/symptom_report?limit=20&offset=0'),
            requestJson('/api/symptom_report/summary'),
          ]);
        if (active) {
          setPatient(patientResult.patient);
          setSymptoms(symptomsResult.symptoms);
          setMedications(medicationResult.medications);
          setReports(reportResult.reports);
          setSummary(summaryResult.summary);
        }
      } catch (error) {
        if (active) setStatus({ message: error.message, isError: true });
      }
    }

    loadPortal();
    return () => { active = false; };
  }, [user]);

  async function submitReport(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);

    if (!selectedSymptoms.length) {
      setStatus({ message: 'Please select at least one symptom.', isError: true });
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
      await refreshPortal();
      setStatus({ message: 'Your symptom report was saved.', isError: false });
      setSection('reports');
    } catch (error) {
      setStatus({ message: error.message, isError: true });
    }
  }

  const activeMedications = medications.filter((medication) => medication.active);
  const pageTitles = {
    overview: ['Your health, at a glance', 'A clear view of your care and recent activity.'],
    medications: ['My medications', 'Review the medication list shared by your care team.'],
    reports: ['Symptom reports', 'Your report history, including medication details at submission.'],
    'new-report': ['New symptom report', 'Share how you are feeling with your care team.'],
  };
  const [title, subtitle] = pageTitles[section];

  return (
    <PortalLayout
      role="patient"
      userName={patient?.name}
      navigation={patientNavigation}
      section={section}
      onNavigate={(target) => { setSection(target); setStatus(null); }}
      onLogout={onLogout}
      onRefresh={() => refreshPortal()}
      refreshing={refreshing}
      title={title}
      subtitle={subtitle}
    >
      {status && (
        <div className={`portal-alert ${status.isError ? 'error' : 'success'}`} role="status">
          <span>{status.isError ? '!' : '✓'}</span>
          {status.message}
          <button type="button" aria-label="Dismiss message" onClick={() => setStatus(null)}>×</button>
        </div>
      )}

      {section === 'overview' && (
        <>
          <section className="welcome-banner">
            <div>
              <span className="eyebrow">PATIENT PORTAL</span>
              <h2>Good day, {patient?.name?.split(' ')[0] ?? 'there'} <span aria-hidden="true">✦</span></h2>
              <p>Keep track of your symptoms and stay connected with your care team.</p>
              <button type="button" className="primary-button" onClick={() => { setSection('new-report'); setStatus(null); }}>
                <span aria-hidden="true">＋</span> Create symptom report
              </button>
            </div>
            <div className="welcome-art" aria-hidden="true">
              <span className="art-ring ring-one" />
              <span className="art-ring ring-two" />
              <span className="art-cross">+</span>
              <span className="art-heart">♥</span>
            </div>
          </section>
          <section className="portal-stat-grid" aria-label="Health summary">
            <SummaryCard icon="▤" label="Symptom reports" value={summary?.total_reports ?? '—'} detail="Reports on your record" />
            <SummaryCard icon="＋" label="Active medications" value={activeMedications.length} detail="Managed by your care team" />
            <SummaryCard icon="✓" label="Reports reviewed" value={reports.filter((report) => report.review_status === 'reviewed').length} detail="Reviewed by your doctor" />
          </section>
          <div className="portal-two-column">
            <section className="portal-card">
              <div className="card-heading">
                <div><span className="eyebrow">RECENT ACTIVITY</span><h2>Recent symptom reports</h2></div>
                <button type="button" className="text-button" onClick={() => setSection('reports')}>View all <span aria-hidden="true">→</span></button>
              </div>
              {reports.length === 0 ? (
                <EmptyState title="No reports yet" detail="Your submitted symptom reports will appear here." />
              ) : (
                reports.slice(0, 3).map((report) => (
                  <PatientReportCard key={report.id} report={report} compact />
                ))
              )}
            </section>
            <div className="portal-stack">
              <section className="portal-card">
                <div className="card-heading">
                  <div><span className="eyebrow">YOUR CARE</span><h2>Care team</h2></div>
                  <span className="care-avatar" aria-hidden="true">✚</span>
                </div>
                <strong className="care-team-name">{patient?.care_team ?? 'Loading care team…'}</strong>
                <p className="muted">Your primary care contact</p>
              </section>
              <section className="portal-card">
                <div className="card-heading">
                  <div><span className="eyebrow">MEDICATIONS</span><h2>Active list</h2></div>
                  <button type="button" className="text-button" onClick={() => setSection('medications')}>View all →</button>
                </div>
                {activeMedications.length === 0 ? (
                  <p className="muted">No active medications on file.</p>
                ) : activeMedications.slice(0, 3).map((medication) => (
                  <div className="mini-medication" key={medication.id}>
                    <span className="medication-symbol">Rx</span>
                    <span><strong>{medication.name}</strong><small>{formatMedicationDosage(medication)}</small></span>
                  </div>
                ))}
              </section>
            </div>
          </div>
        </>
      )}

      {section === 'medications' && (
        <section className="portal-card">
          <div className="card-heading">
            <div><span className="eyebrow">MEDICATION LIST</span><h2>Medications shared with you</h2></div>
            <label className="filter-control">Show
              <select value={medicationFilter} onChange={(event) => setMedicationFilter(event.target.value)}>
                <option value="active">Active</option>
                <option value="all">All medications</option>
              </select>
            </label>
          </div>
          <p className="muted">Your care team manages this list. Changes are reflected in future symptom reports.</p>
          {(medicationFilter === 'all' ? medications : activeMedications).length === 0 ? (
            <EmptyState title="No medications to show" detail="Your care team has not added any medications to this list." />
          ) : (
            <div className="medication-list">
              {(medicationFilter === 'all' ? medications : activeMedications).map((medication) => (
                <article className="medication-portal-card" key={medication.id}>
                  <span className="medication-symbol">Rx</span>
                  <div className="medication-details">
                    <div className="medication-title-row">
                      <h3>{medication.name}</h3>
                      <span className={`review-badge ${medication.active ? 'active' : 'inactive'}`}>
                        {medication.active ? 'Active' : 'Discontinued'}
                      </span>
                    </div>
                    <p className="medication-dose">{formatMedicationDosage(medication)}</p>
                    {medication.instructions && <p>{medication.instructions}</p>}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      )}

      {section === 'reports' && (
        <section className="portal-card">
          <div className="card-heading">
            <div><span className="eyebrow">HEALTH TIMELINE</span><h2>Your symptom history</h2></div>
            <button type="button" className="primary-button compact-button" onClick={() => { setSection('new-report'); setStatus(null); }}>
              + New report
            </button>
          </div>
          {reports.length === 0 ? (
            <EmptyState title="No symptom reports yet" detail="Create a report to share symptoms with your care team." />
          ) : reports.map((report) => <PatientReportCard key={report.id} report={report} />)}
        </section>
      )}

      {section === 'new-report' && (
        <section className="portal-card report-form-card">
          <div className="card-heading">
            <div><span className="eyebrow">NEW ENTRY</span><h2>How are you feeling?</h2></div>
            <span className="form-step">01 <span>/</span> 01</span>
          </div>
          <p className="muted">Select all symptoms that apply. Your active medications will be included automatically.</p>
          <form onSubmit={submitReport}>
            <div className="field">
              <label className="field-label" htmlFor="symptom-select">Select a symptom</label>
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
                <option value="">Choose from the list</option>
                {symptoms.map((symptom) => <option key={symptom} value={symptom}>{symptom}</option>)}
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
                        onClick={() => setSelectedSymptoms(selectedSymptoms.filter((item) => item !== symptom))}
                      >Remove</button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="field">
              <label className="field-label" htmlFor="report-notes">Additional details <span>(optional)</span></label>
              <textarea
                id="report-notes"
                name="notes"
                rows="5"
                maxLength="1000"
                placeholder="When did it start? How severe is it? Add anything that may help your care team."
              />
              <span className="character-hint">Up to 1,000 characters</span>
            </div>
            <div className="form-footer">
              <span className="muted"><span aria-hidden="true">🔒</span> Shared securely with your care team</span>
              <button type="submit" className="primary-button">Submit report <span aria-hidden="true">→</span></button>
            </div>
          </form>
        </section>
      )}
    </PortalLayout>
  );
}

function PatientReportCard({ report, compact = false }) {
  return (
    <article className={`timeline-report${compact ? ' compact-report' : ''}`}>
      <span className="timeline-marker" aria-hidden="true" />
      <div className="timeline-report-content">
        <div className="report-card-heading">
          <div>
            <strong>{compact ? `Report #${report.id}` : 'Symptom report'}</strong>
            <span className="meta">{new Date(report.submitted_at).toLocaleString()}</span>
          </div>
          <span className={`review-badge ${report.review_status}`}>
            {report.review_status === 'reviewed' ? 'Reviewed' : 'Awaiting review'}
          </span>
        </div>
        <div className="pill-list">
          {report.symptoms.map((symptom) => <span className="pill" key={symptom}>{symptom}</span>)}
        </div>
        {!compact && report.notes && <p className="report-notes">{report.notes}</p>}
        {!compact && report.medications?.length > 0 && (
          <div className="report-medications">
            <strong>Medications at submission</strong>
            {report.medications.map((medication) => (
              <span key={medication.id}>{medication.name} · {formatMedicationDosage(medication)}</span>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}

function SummaryCard({ icon, label, value, detail, tone = 'blue' }) {
  return (
    <article className="summary-card">
      <span className={`summary-icon ${tone}`} aria-hidden="true">{icon}</span>
      <span className="summary-label">{label}</span>
      <strong className="summary-value">{value}</strong>
      <span className="summary-detail">{detail}</span>
    </article>
  );
}

function EmptyState({ title, detail }) {
  return (
    <div className="empty-state">
      <span className="empty-state-icon" aria-hidden="true">＋</span>
      <strong>{title}</strong>
      <p>{detail}</p>
    </div>
  );
}

function formatMedicationDosage(medication) {
  return `${medication.dosage_value} ${medication.dosage_unit}${
    medication.frequency ? ` · ${medication.frequency}` : ''
  }`;
}


function DoctorDashboard({ onLogout }) {
  const [dashboard, setDashboard] = useState(null);
  const [filter, setFilter] = useState('all');
  const [drafts, setDrafts] = useState({});
  const [busyId, setBusyId] = useState(null);
  const [busyMedication, setBusyMedication] = useState(false);
  const [message, setMessage] = useState('');
  const [section, setSection] = useState('overview');
  const [refreshing, setRefreshing] = useState(false);
  const [editingMedicationId, setEditingMedicationId] = useState(null);
  const [medicationDraft, setMedicationDraft] = useState({
    name: '',
    dosage_value: '',
    dosage_unit: 'mg',
    frequency: '',
    instructions: '',
    active: true,
  });

  async function loadDashboard() {
    const data = await requestJson('/api/doctor/dashboard?limit=100');
    setDashboard(data);
  }

  async function refreshDashboard() {
    setRefreshing(true);
    try {
      await loadDashboard();
      setMessage('');
    } catch (error) {
      setMessage(error.message);
    } finally {
      setRefreshing(false);
    }
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
      setDrafts((old) => {
        const next = { ...old };
        delete next[report.id];
        return next;
      });
      setMessage('Review saved successfully.');
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusyId(null);
    }
  }

  function editMedication(medication) {
    setEditingMedicationId(medication.id);
    setMedicationDraft({
      name: medication.name,
      dosage_value: medication.dosage_value,
      dosage_unit: medication.dosage_unit,
      frequency: medication.frequency,
      instructions: medication.instructions,
      active: medication.active,
    });
  }

  function resetMedicationForm() {
    setEditingMedicationId(null);
    setMedicationDraft({
      name: '',
      dosage_value: '',
      dosage_unit: 'mg',
      frequency: '',
      instructions: '',
      active: true,
    });
  }

  async function saveMedication(event) {
    event.preventDefault();
    setBusyMedication(true);
    setMessage('');
    const isEditing = editingMedicationId !== null;
    try {
      await requestJson(
        isEditing
          ? `/api/doctor/medications/${editingMedicationId}`
          : '/api/doctor/medications',
        {
          method: isEditing ? 'PATCH' : 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ...(isEditing ? {} : { name: medicationDraft.name }),
            dosage_value: Number(medicationDraft.dosage_value),
            dosage_unit: medicationDraft.dosage_unit,
            frequency: medicationDraft.frequency,
            instructions: medicationDraft.instructions,
            active: medicationDraft.active,
          }),
        },
      );
      await loadDashboard();
      resetMedicationForm();
      setMessage(isEditing ? 'Medication updated.' : 'Medication added.');
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusyMedication(false);
    }
  }

  const displayed = (dashboard?.reports ?? []).filter(
    (report) => filter === 'all' || report.review_status === filter
  );
  const medications = dashboard?.medications ?? [];
  const reports = dashboard?.reports ?? [];
  const pageTitles = {
    overview: ['Care team dashboard', 'A snapshot of patient activity and care tasks.'],
    reports: ['Patient reports', 'Review symptom history and document follow-up.'],
    medications: ['Medication management', 'Maintain the medication list shared with the patient.'],
  };
  const [title, subtitle] = pageTitles[section];

  return (
    <PortalLayout
      role="doctor"
      userName="Care team"
      navigation={doctorNavigation}
      section={section}
      onNavigate={(target) => { setSection(target); setMessage(''); }}
      onLogout={onLogout}
      onRefresh={() => refreshDashboard()}
      refreshing={refreshing}
      title={title}
      subtitle={subtitle}
    >
      {message && (
        <div className={`portal-alert ${message.includes('successfully') || message.includes('updated') || message.includes('added') ? 'success' : 'error'}`} role="status">
          <span aria-hidden="true">{message.includes('successfully') || message.includes('updated') || message.includes('added') ? '✓' : '!'}</span>
          {message}
          <button type="button" aria-label="Dismiss message" onClick={() => setMessage('')}>×</button>
        </div>
      )}
      {!dashboard && !message && <div className="portal-card loading-card">Loading patient workspace…</div>}

      {section === 'overview' && dashboard && (
        <>
          <section className="welcome-banner doctor-welcome">
            <div>
              <span className="eyebrow">CARE TEAM WORKSPACE</span>
              <h2>{dashboard.patient.name}<span className="patient-id">Patient record</span></h2>
              <p>Review health updates and keep the medication record current.</p>
              <button type="button" className="primary-button" onClick={() => setSection('reports')}>
                Review patient reports <span aria-hidden="true">→</span>
              </button>
            </div>
            <div className="welcome-art" aria-hidden="true">
              <span className="art-ring ring-one" />
              <span className="art-ring ring-two" />
              <span className="art-cross">+</span>
              <span className="art-heart">♥</span>
            </div>
          </section>
          <section className="portal-stat-grid" aria-label="Patient overview">
            <SummaryCard icon="▤" label="Total reports" value={dashboard.page.total} detail="Patient-submitted reports" />
            <SummaryCard icon="◷" label="Pending review" value={dashboard.review_counts.pending} detail="Reports need your attention" tone="orange" />
            <SummaryCard icon="✓" label="Reviewed" value={dashboard.review_counts.reviewed} detail="Reports you've completed" tone="green" />
          </section>
          <div className="portal-two-column">
            <section className="portal-card">
              <div className="card-heading">
                <div><span className="eyebrow">ACTION REQUIRED</span><h2>Reports awaiting review</h2></div>
                <button type="button" className="text-button" onClick={() => { setFilter('pending'); setSection('reports'); }}>View queue →</button>
              </div>
              {reports.filter((report) => report.review_status === 'pending').length === 0 ? (
                <EmptyState title="All caught up" detail="There are no reports waiting for review." />
              ) : reports.filter((report) => report.review_status === 'pending').slice(0, 3).map((report) => (
                <DoctorReportCard
                  key={report.id}
                  report={report}
                  drafts={drafts}
                  setDrafts={setDrafts}
                  busyId={busyId}
                  saveReview={saveReview}
                  compact
                />
              ))}
            </section>
            <section className="portal-card">
              <div className="card-heading">
                <div><span className="eyebrow">MEDICATIONS</span><h2>Patient medication list</h2></div>
                <button type="button" className="text-button" onClick={() => setSection('medications')}>Manage →</button>
              </div>
              {medications.filter((medication) => medication.active).length === 0 ? (
                <p className="muted">No active medications on this patient's record.</p>
              ) : medications.filter((medication) => medication.active).slice(0, 3).map((medication) => (
                <div className="mini-medication" key={medication.id}>
                  <span className="medication-symbol">Rx</span>
                  <span><strong>{medication.name}</strong><small>{formatMedicationDosage(medication)}</small></span>
                </div>
              ))}
            </section>
          </div>
        </>
      )}

      {section === 'reports' && dashboard && (
        <section className="portal-card">
          <div className="card-heading">
            <div><span className="eyebrow">PATIENT ACTIVITY</span><h2>Symptom report review</h2></div>
            <label className="filter-control">Show
              <select value={filter} onChange={(event) => setFilter(event.target.value)}>
                <option value="all">All reports</option>
                <option value="pending">Pending</option>
                <option value="reviewed">Reviewed</option>
              </select>
            </label>
          </div>
          <p className="muted">Doctor review notes are visible to the care team only.</p>
          {displayed.length === 0 ? (
            <EmptyState title="No reports in this view" detail="Try changing the status filter." />
          ) : displayed.map((report) => (
            <DoctorReportCard
              key={report.id}
              report={report}
              drafts={drafts}
              setDrafts={setDrafts}
              busyId={busyId}
              saveReview={saveReview}
            />
          ))}
          {dashboard.page.total > dashboard.reports.length && (
            <p className="muted">Showing the latest {dashboard.reports.length} reports out of {dashboard.page.total}.</p>
          )}
        </section>
      )}

      {section === 'medications' && dashboard && (
        <div className="portal-two-column medication-page-grid">
          <section className="portal-card medication-management">
            <div className="card-heading">
              <div><span className="eyebrow">{editingMedicationId === null ? 'NEW PRESCRIPTION' : 'UPDATE PRESCRIPTION'}</span><h2>{editingMedicationId === null ? 'Add medication' : 'Edit medication details'}</h2></div>
            </div>
            <p className="muted">Medication names are fixed after creation. Update dosage or instructions here.</p>
            <form className="medication-form" onSubmit={saveMedication}>
              <div className="field">
                <label className="field-label" htmlFor="medication-name">Medication name</label>
                <input id="medication-name" required maxLength={120}
                  readOnly={editingMedicationId !== null}
                  value={medicationDraft.name}
                  onChange={(event) => setMedicationDraft((old) => ({...old, name: event.target.value}))} />
              </div>
              <div className="medication-form-row">
                <div className="field">
                  <label className="field-label" htmlFor="medication-dose">Dosage</label>
                  <input id="medication-dose" type="number" min="0.001" step="any" required
                    value={medicationDraft.dosage_value}
                    onChange={(event) => setMedicationDraft((old) => ({...old, dosage_value: event.target.value}))} />
                </div>
                <div className="field">
                  <label className="field-label" htmlFor="medication-unit">Unit</label>
                  <select id="medication-unit" value={medicationDraft.dosage_unit}
                    onChange={(event) => setMedicationDraft((old) => ({...old, dosage_unit: event.target.value}))}>
                    {['mg', 'mcg', 'ml', 'g', 'tablets'].map((unit) => <option key={unit}>{unit}</option>)}
                  </select>
                </div>
              </div>
              <div className="field">
                <label className="field-label" htmlFor="medication-frequency">Frequency</label>
                <input id="medication-frequency" maxLength={120} placeholder="e.g. twice daily"
                  value={medicationDraft.frequency}
                  onChange={(event) => setMedicationDraft((old) => ({...old, frequency: event.target.value}))} />
              </div>
              <div className="field">
                <label className="field-label" htmlFor="medication-instructions">Instructions</label>
                <textarea id="medication-instructions" maxLength={1000} rows={3}
                  value={medicationDraft.instructions}
                  onChange={(event) => setMedicationDraft((old) => ({...old, instructions: event.target.value}))} />
              </div>
              <label className="medication-active">
                <input type="checkbox" checked={medicationDraft.active}
                  onChange={(event) => setMedicationDraft((old) => ({...old, active: event.target.checked}))} />
                Active medication
              </label>
              <div className="button-row">
                <button type="submit" className="primary-button" disabled={busyMedication}>
                  {busyMedication ? 'Saving…' : editingMedicationId === null ? 'Add medication' : 'Save changes'}
                </button>
                {editingMedicationId !== null && (
                  <button type="button" className="secondary-button" onClick={resetMedicationForm}>Cancel</button>
                )}
              </div>
            </form>
          </section>
          <section className="portal-card">
            <div className="card-heading">
              <div><span className="eyebrow">PATIENT RECORD</span><h2>Medication list</h2></div>
              <span className="count-chip">{medications.length}</span>
            </div>
            {medications.length === 0 ? (
              <EmptyState title="No medications added" detail="Add a medication to begin the patient's list." />
            ) : (
              <div className="medication-list">
                {medications.map((medication) => (
                  <article className="medication-portal-card" key={medication.id}>
                    <span className="medication-symbol">Rx</span>
                    <div className="medication-details">
                      <div className="medication-title-row">
                        <h3>{medication.name}</h3>
                        <span className={`review-badge ${medication.active ? 'active' : 'inactive'}`}>
                          {medication.active ? 'Active' : 'Discontinued'}
                        </span>
                      </div>
                      <p className="medication-dose">{formatMedicationDosage(medication)}</p>
                      {medication.instructions && <p>{medication.instructions}</p>}
                      <button type="button" className="text-button" onClick={() => editMedication(medication)}>Edit details →</button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </PortalLayout>
  );
}

function DoctorReportCard({ report, drafts, setDrafts, busyId, saveReview, compact = false }) {
  return (
    <article className={`doctor-report-card${compact ? ' compact-doctor-report' : ''}`}>
      <div className="report-card-heading">
        <div>
          <strong>Report #{report.id}</strong>
          <span className="meta">{new Date(report.submitted_at).toLocaleString()}</span>
        </div>
        <span className={`review-badge ${report.review_status}`}>
          {report.review_status === 'reviewed' ? 'Reviewed' : 'Pending review'}
        </span>
      </div>
      <div className="pill-list">
        {report.symptoms.map((symptom) => <span className="pill" key={symptom}>{symptom}</span>)}
      </div>
      <p className="report-notes"><strong>Patient notes:</strong> {report.notes || 'No additional details'}</p>
      {report.medications?.length > 0 && (
        <div className="report-medications">
          <strong>Medications at submission</strong>
          {report.medications.map((medication) => (
            <span key={medication.id}>{medication.name} · {formatMedicationDosage(medication)}</span>
          ))}
        </div>
      )}
      {!compact && (
        <>
          <label className="field-label" htmlFor={`doctor-note-${report.id}`}>Doctor review notes</label>
          <textarea
            id={`doctor-note-${report.id}`}
            className="doctor-note-input"
            maxLength={1000}
            rows={3}
            value={drafts[report.id] ?? report.doctor_note ?? ''}
            onChange={(event) => setDrafts((old) => ({...old, [report.id]: event.target.value}))}
            placeholder="Add private notes for the care team"
          />
          <div className="button-row review-actions">
            <button disabled={busyId !== null} onClick={() => saveReview(report, 'reviewed')}>Mark reviewed</button>
            <button disabled={busyId !== null} className="secondary-button" onClick={() => saveReview(report, 'pending')}>Save as pending</button>
          </div>
        </>
      )}
    </article>
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
      } catch {
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
      <DoctorDashboard onLogout={handleLogout} />
    );
  }

  return <main className="login-page">Your account role is not supported.</main>;
}

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <HealthwatchApp />
  </React.StrictMode>,
);
