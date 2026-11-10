import React, { useEffect, useRef, useState } from 'react';
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
  const validPages = ['overview', 'reports', 'log'];
  const pageFromHash = () => {
    const page = window.location.hash.slice(1);
    return validPages.includes(page) ? page : 'overview';
  };
  const [activePage, setActivePage] = useState(pageFromHash);
  const [patient, setPatient] = useState(null);
  const [symptoms, setSymptoms] = useState([]);
  const [symptomChoice, setSymptomChoice] = useState('');
  const [selectedSymptoms, setSelectedSymptoms] = useState([]);
  const [reports, setReports] = useState([]);
  const [reportTotal, setReportTotal] = useState(0);
  const [reportSearch, setReportSearch] = useState('');
  const [loadingMore, setLoadingMore] = useState(false);
  const [summary, setSummary] = useState(null);
  const [status, setStatus] = useState(null);
  const [submissionNotice, setSubmissionNotice] = useState(null);
  const [submittingReport, setSubmittingReport] = useState(false);
  const submissionDialogRef = useRef(null);

  useEffect(() => {
    const dialog = submissionDialogRef.current;
    if (submissionNotice && dialog && !dialog.open) {
      dialog.showModal();
    }

    return () => {
      if (dialog?.open) {
        dialog.close();
      }
    };
  }, [submissionNotice]);

  async function refreshHistory() {
    const [reportResult, summaryResult] = await Promise.all([
      requestJson('/api/symptom_report?limit=20&offset=0'),
      requestJson('/api/symptom_report/summary'),
    ]);
    setReports(reportResult.reports);
    setReportTotal(reportResult.page.total);
    setSummary(summaryResult.summary);
  }

  useEffect(() => {
    function syncPage() {
      setActivePage(pageFromHash());
      setStatus(null);
    }

    window.addEventListener('popstate', syncPage);
    window.addEventListener('hashchange', syncPage);
    return () => {
      window.removeEventListener('popstate', syncPage);
      window.removeEventListener('hashchange', syncPage);
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
          setReportTotal(reportResult.page.total);
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

  function navigateTo(page) {
    setActivePage(page);
    setStatus(null);
    window.history.pushState({ page }, '', `#${page}`);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async function loadMoreReports() {
    setLoadingMore(true);
    setStatus(null);
    try {
      const result = await requestJson(
        `/api/symptom_report?limit=20&offset=${reports.length}`,
      );
      setReports((current) => [...current, ...result.reports]);
      setReportTotal(result.page.total);
    } catch (error) {
      setStatus({ message: error.message, isError: true });
    } finally {
      setLoadingMore(false);
    }
  }

  async function submitReport(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);

    if (!selectedSymptoms.length) {
      setSubmissionNotice({
        title: 'Choose a symptom',
        message: 'Please select at least one symptom before submitting.',
        isError: true,
      });
      return;
    }

    setSubmittingReport(true);
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
      setSubmissionNotice({
        title: 'Report submitted',
        message: 'Your symptom report was saved successfully.',
        isError: false,
      });
      try {
        await refreshHistory();
      } catch (error) {
        setSubmissionNotice({
          title: 'Report submitted',
          message: `Your report was saved, but your history could not be refreshed: ${error.message}`,
          isError: false,
        });
      }
    } catch (error) {
      setSubmissionNotice({
        title: 'Report not submitted',
        message: error.message,
        isError: true,
      });
    } finally {
      setSubmittingReport(false);
    }
  }
  
  const patientEmail = patient?.email || user.email;
  const initials = patientEmail ? patientEmail.slice(0, 2).toUpperCase() : 'PT';
  const pageTitles = {
    overview: 'Overview',
    reports: 'Health reports',
    log: 'Log a symptom',
  };
  const visibleReports = reports.filter((report) => {
    const query = reportSearch.trim().toLowerCase();
    return !query
      || report.symptoms.some((symptom) => symptom.toLowerCase().includes(query))
      || report.notes.toLowerCase().includes(query);
  });

  function renderReport(report) {
    return (
      <article className="history-item" key={report.id}>
        <div className="history-topline">
          <span className="history-dot" aria-hidden="true" />
          <time className="meta" dateTime={report.submitted_at}>
            {new Date(report.submitted_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}
          </time>
        </div>
        <div className="pill-list">
          {report.symptoms.map((symptom) => <span className="pill" key={symptom}>{symptom}</span>)}
        </div>
        {report.notes && <p className="report-notes">{report.notes}</p>}
      </article>
    );
  }

  return (
    <div className="portal">
      <aside className="sidebar">
        <button type="button" className="brand" onClick={() => navigateTo('overview')} aria-label="Healthwatch home">
          <span className="brand-mark" aria-hidden="true">+</span>
          <span>health<span className="brand-light">watch</span></span>
        </button>
        <div className="sidebar-label">YOUR PORTAL</div>
        <nav className="portal-nav" aria-label="Main navigation">
          {[
            ['overview', '⌂', 'Overview'],
            ['reports', '▤', 'Health reports'],
            ['log', '＋', 'Log a symptom'],
          ].map(([page, icon, label]) => (
            <button
              type="button"
              className={`nav-link${activePage === page ? ' active' : ''}`}
              aria-current={activePage === page ? 'page' : undefined}
              key={page}
              onClick={() => navigateTo(page)}
            >
              <span className="nav-icon" aria-hidden="true">{icon}</span>{label}
            </button>
          ))}
        </nav>
        <div className="sidebar-help">
          <span className="help-mark" aria-hidden="true">i</span>
          <strong>Need help?</strong>
          <p>Your care team is here to support you.</p>
        </div>
        <div className="sidebar-foot">A clearer view of your health.</div>
      </aside>

      <div className="portal-main">
        <header className="topbar">
          <div className="breadcrumb">Patient portal <span>/</span> {pageTitles[activePage]}</div>
          <div className="account-menu">
            <span className="secure-label"><span aria-hidden="true">●</span> Secure portal</span>
            <span className="avatar" aria-label={`Signed in as ${patientEmail || 'patient'}`}>{initials}</span>
            <button type="button" className="logout-button" onClick={onLogout}>Sign out</button>
          </div>
        </header>

        <main className="portal-content">
          <section className="welcome-row">
            <div>
              <p className="eyebrow">{activePage === 'overview' ? 'YOUR HEALTH, AT A GLANCE' : 'PATIENT PORTAL'}</p>
              <h1>{activePage === 'overview' ? 'Your health overview' : pageTitles[activePage]}</h1>
              <p className="welcome-copy">
                {activePage === 'overview' && 'Keep track of your symptom reports and share updates with your care team.'}
                {activePage === 'reports' && 'Review your saved symptom reports and the details you shared with your care team.'}
                {activePage === 'log' && 'Share an update about how you’re feeling with your care team.'}
              </p>
              <p className="patient-meta">Signed in as <span>{patientEmail || 'Loading account…'}</span></p>
            </div>
            {activePage !== 'log' && (
              <button type="button" className="primary-link" onClick={() => navigateTo('log')}>
                <span aria-hidden="true">＋</span> Log a symptom
              </button>
            )}
          </section>

          {activePage === 'overview' && <section className="summary-grid" aria-label="Health overview">
            <article className="summary-card">
              <span className="summary-icon teal" aria-hidden="true">▤</span>
              <div><span className="summary-label">Symptom reports</span><strong>{summary?.total_reports ?? '—'}</strong><span className="summary-note">Reports saved to your history</span></div>
            </article>
            <article className="summary-card">
              <span className="summary-icon blue" aria-hidden="true">⌁</span>
              <div><span className="summary-label">Symptoms logged</span><strong>{summary?.total_symptom_entries ?? '—'}</strong><span className="summary-note">Across all your reports</span></div>
            </article>
          </section>
          }

          {activePage === 'overview' && (
          <div className="portal-columns">
            <section className="panel overview-card" aria-labelledby="overview-card-heading">
              <div className="section-heading">
                <div><span className="section-kicker">YOUR NEXT STEP</span><h2 id="overview-card-heading">Keep your care team in the loop</h2></div>
                <span className="heading-icon" aria-hidden="true">♡</span>
              </div>
              <p className="section-description">A quick symptom update can help your care team understand how you’re feeling between visits. Your reports are saved securely in your health history.</p>
              <button type="button" className="text-action" onClick={() => navigateTo('log')}>Create a symptom report <span aria-hidden="true">→</span></button>
            </section>
            <section className="panel history-panel" aria-labelledby="recent-heading">
              <div className="section-heading history-heading">
                <div><span className="section-kicker">YOUR RECORD</span><h2 id="recent-heading">Recent reports</h2></div>
                <span className="record-count">{reportTotal} {reportTotal === 1 ? 'report' : 'reports'}</span>
              </div>
              {reports.length === 0 ? (
                <div className="empty-history"><span className="empty-icon" aria-hidden="true">▤</span><strong>No reports yet</strong><p>Your saved symptom reports will appear here.</p></div>
              ) : (
                <div className="history-list">{reports.slice(0, 3).map(renderReport)}</div>
              )}
              {reports.length > 0 && <span className="overview-report-count">Showing {Math.min(3, reports.length)} most recent of {reportTotal} reports</span>}
              {reports.length > 0 && <button type="button" className="history-link" onClick={() => navigateTo('reports')}>View all reports <span aria-hidden="true">→</span></button>}
            </section>
          </div>
          )}

          {activePage === 'log' && (
            <section className="panel report-panel full-panel" aria-labelledby="report-heading">
              <div className="section-heading">
                <div><span className="section-kicker">HEALTH JOURNAL</span><h2 id="report-heading">How are you feeling?</h2></div>
                <span className="heading-icon" aria-hidden="true">＋</span>
              </div>
              <p className="section-description">Share any symptoms you’re experiencing. Your care team can use these updates to better understand how you’re doing.</p>
              <form onSubmit={submitReport}>
                <div className="field">
                  <label className="field-label" htmlFor="symptom-select">Symptoms</label>
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
                    <option value="">Choose a symptom to add</option>
                    {symptoms.map((symptom) => (
                      <option key={symptom} value={symptom}>{symptom}</option>
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
                            onClick={() => setSelectedSymptoms(selectedSymptoms.filter((item) => item !== symptom))}
                          >Remove</button>
                        </li>
                      ))}
                    </ul>
                  )}
                  <span className="field-hint">Add as many as you need.</span>
                </div>
                <div className="field">
                  <label className="field-label" htmlFor="report-notes">Anything else you’d like us to know? <span>(optional)</span></label>
                  <textarea
                    id="report-notes"
                    name="notes"
                    rows="4"
                    maxLength="1000"
                    onChange={() => status && setStatus(null)}
                    placeholder="Tell us when it started, how it feels, or anything else that may be helpful."
                  />
                  <span className="field-hint">Please don’t use this form for emergencies.</span>
                </div>
                <div className="report-submit">
                  <button type="submit" disabled={submittingReport}>
                    <span aria-hidden="true">＋</span>
                    {submittingReport ? 'Saving report…' : 'Save symptom report'}
                  </button>
                  <span className="privacy-note"><span aria-hidden="true">▣</span> Only you and your care team can see this</span>
                </div>
                <div
                  className={`status${status?.isError ? ' error' : status ? ' success' : ''}`}
                  role="status"
                  aria-live="polite"
                >{status?.message}</div>
              </form>
            </section>
          )}

          {activePage === 'reports' && (
            <section className="panel history-panel full-panel" aria-labelledby="history-heading">
              <div className="section-heading history-heading">
                <div><span className="section-kicker">YOUR RECORD</span><h2 id="history-heading">Symptom history</h2></div>
                <div className="history-tools">
                  <span className="record-count">{reportTotal} {reportTotal === 1 ? 'report' : 'reports'}</span>
                  <button type="button" className="refresh-button" onClick={() => refreshHistory().catch((error) => setStatus({ message: error.message, isError: true }))}>Refresh</button>
                </div>
              </div>
              <p className="section-description">Search reports by symptom or by details in the notes you shared.</p>
              <label className="search-field">
                <span aria-hidden="true">⌕</span>
                <input type="search" value={reportSearch} onChange={(event) => setReportSearch(event.target.value)} placeholder="Search symptoms or notes" aria-label="Search reports by symptom or notes" />
                {reportSearch && <button type="button" onClick={() => setReportSearch('')} aria-label="Clear search">Clear</button>}
              </label>
              <p className="search-hint">Search the reports currently loaded. Load older reports to include earlier entries.</p>
              {reports.length === 0 ? (
                <div className="empty-history">
                  <span className="empty-icon" aria-hidden="true">▤</span>
                  <strong>No reports yet</strong>
                  <p>Your saved symptom reports will appear here.</p>
                  <button type="button" className="text-action" onClick={() => navigateTo('log')}>Create your first report <span aria-hidden="true">→</span></button>
                </div>
              ) : visibleReports.length === 0 ? (
                <div className="empty-history"><span className="empty-icon" aria-hidden="true">⌕</span><strong>No matching reports</strong><p>Try a different symptom or search term.</p></div>
              ) : (
                <div className="history-list">{visibleReports.map(renderReport)}</div>
              )}
              {status && <div className={`status${status.isError ? ' error' : ' success'}`} role="status">{status.message}</div>}
              {reports.length < reportTotal && (
                <button type="button" className="load-more-button" onClick={loadMoreReports} disabled={loadingMore}>
                  {loadingMore ? 'Loading reports…' : 'Load older reports'}
                </button>
              )}
            </section>
          )}
          <footer className="portal-footer">Healthwatch <span>·</span> Your information is private and secure.</footer>
        </main>
      </div>
      {submissionNotice && (
        <dialog
          ref={submissionDialogRef}
          className={`submission-dialog ${submissionNotice.isError ? 'error' : 'success'}`}
          aria-labelledby="submission-dialog-title"
          onCancel={(event) => {
            event.preventDefault();
            setSubmissionNotice(null);
          }}
        >
          <div className="submission-dialog-icon" aria-hidden="true">
            {submissionNotice.isError ? '!' : '✓'}
          </div>
          <h2 id="submission-dialog-title">{submissionNotice.title}</h2>
          <p role={submissionNotice.isError ? 'alert' : 'status'}>{submissionNotice.message}</p>
          <button type="button" autoFocus onClick={() => setSubmissionNotice(null)}>
            Close
          </button>
        </dialog>
      )}
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


function DoctorDashboard({ user, onLogout }) {
  const [dashboard, setDashboard] = useState(null);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [drafts, setDrafts] = useState({});
  const [busyId, setBusyId] = useState(null);
  const [message, setMessage] = useState('');
  const [loadingMore, setLoadingMore] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  async function loadDashboard({ offset = 0, append = false } = {}) {
    const data = await requestJson(`/api/doctor/dashboard?limit=20&offset=${offset}`);
    setDashboard((current) => append && current
      ? { ...data, reports: [...current.reports, ...data.reports] }
      : data);
  }

  useEffect(() => {
    let active = true;
    requestJson('/api/doctor/dashboard?limit=20&offset=0')
      .then((data) => { if (active) setDashboard(data); })
      .catch((error) => { if (active) setMessage(error.message); });
    return () => { active = false; };
  }, []);

  async function refreshDashboard() {
    setRefreshing(true);
    setMessage('');
    try {
      await loadDashboard();
      setMessage('Reports refreshed.');
    } catch (error) {
      setMessage(error.message);
    } finally {
      setRefreshing(false);
    }
  }

  async function loadOlderReports() {
    setLoadingMore(true);
    setMessage('');
    try {
      await loadDashboard({ offset: dashboard.reports.length, append: true });
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoadingMore(false);
    }
  }

  async function saveReview(report, reviewStatus) {
    setBusyId(report.id);
    setMessage('');
    try {
      const result = await requestJson(`/api/doctor/reports/${report.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          review_status: reviewStatus,
          doctor_note: drafts[report.id] ?? report.doctor_note ?? '',
        }),
      });
      setDashboard((current) => {
        if (!current) return current;
        const previousStatus = report.review_status;
        const reviewCounts = { ...current.review_counts };
        if (previousStatus !== reviewStatus) {
          reviewCounts[previousStatus] -= 1;
          reviewCounts[reviewStatus] += 1;
        }
        return {
          ...current,
          review_counts: reviewCounts,
          reports: current.reports.map((item) =>
            item.id === report.id ? result.report : item
          ),
        };
      });
      setDrafts((current) => {
        const next = { ...current };
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

  const displayed = (dashboard?.reports ?? []).filter((report) => {
    const matchesStatus = filter === 'all' || report.review_status === filter;
    const query = search.trim().toLowerCase();
    const matchesSearch = !query
      || report.symptoms.some((symptom) => symptom.toLowerCase().includes(query))
      || report.notes.toLowerCase().includes(query)
      || String(report.id).includes(query);
    return matchesStatus && matchesSearch;
  });
  return (
    <div className="doctor-portal">
      <header className="doctor-topbar">
        <a className="brand doctor-brand" href="#doctor-dashboard" aria-label="Healthwatch clinician portal">
          <span className="brand-mark" aria-hidden="true">+</span>
          <span>health<span className="brand-light">watch</span></span>
        </a>
        <div className="doctor-account">
          <span className="doctor-role"><span aria-hidden="true">●</span> Clinician workspace</span>
          <span className="doctor-email">{user.email}</span>
          <button type="button" className="logout-button" onClick={onLogout}>Sign out</button>
        </div>
      </header>
      <main className="doctor-content" id="doctor-dashboard">
        <div className="doctor-heading">
          <div><p className="eyebrow">PATIENT CARE</p><h1>Symptom review</h1><p>Review patient-submitted updates and record your follow-up notes.</p></div>
          <button type="button" className="secondary-button" onClick={refreshDashboard} disabled={refreshing}>
            {refreshing ? 'Refreshing…' : '↻ Refresh reports'}
          </button>
        </div>
        <div className="dashboard-stats">
          <Stat label="Total reports" value={dashboard?.page.total ?? '—'} />
          <Stat label="Pending review" value={dashboard?.review_counts.pending ?? '—'} />
          <Stat label="Reviewed" value={dashboard?.review_counts.reviewed ?? '—'} />
        </div>
        <section className="panel doctor-reports-panel">
          <div className="doctor-toolbar">
            <div><span className="section-kicker">INCOMING UPDATES</span><h2>Patient symptom reports</h2></div>
            <label className="doctor-filter">Status <select value={filter} onChange={(event) => setFilter(event.target.value)}>
            <option value="all">All reports</option>
            <option value="pending">Pending</option>
            <option value="reviewed">Reviewed</option>
          </select></label>
        </div>
        <label className="search-field doctor-search">
          <span aria-hidden="true">⌕</span>
          <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search reports by symptom, note, or report number" aria-label="Search patient reports" />
          {search && <button type="button" onClick={() => setSearch('')} aria-label="Clear search">Clear</button>}
        </label>
        <p className="muted doctor-privacy-note">Clinical review notes are saved with the report and are not shown in the patient’s report history.</p>
        <div role="status" aria-live="polite" className="status">{message}</div>
        {!dashboard && !message && <p>Loading reports…</p>}
        {dashboard && displayed.length === 0 && <div className="doctor-empty"><strong>{search || filter !== 'all' ? 'No matching reports' : 'No reports have been submitted yet'}</strong><p>{search || filter !== 'all' ? 'Try another search or status filter.' : 'New patient updates will appear here.'}</p></div>}
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
              placeholder="Add clinical review notes" />
            <div className="button-row review-actions">
              <button type="button" disabled={busyId !== null} onClick={() => saveReview(report, 'reviewed')}>{busyId === report.id ? 'Saving…' : 'Mark reviewed & save'}</button>
              <button type="button" disabled={busyId !== null} className="secondary-button" onClick={() => saveReview(report, 'pending')}>Save as pending</button>
            </div>
          </article>
        ))}
        {dashboard && <div className="doctor-pagination">
          <span className="muted">Showing {dashboard.reports.length} of {dashboard.page.total} reports</span>
          {dashboard.reports.length < dashboard.page.total && (
            <button type="button" className="load-more-button" onClick={loadOlderReports} disabled={loadingMore}>
              {loadingMore ? 'Loading reports…' : 'Load older reports'}
            </button>
          )}
        </div>}
      </section>
      </main>
    </div>
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
      <DoctorDashboard user={user} onLogout={handleLogout} />
    );
  }

  return <main className="login-page">Your account role is not supported.</main>;
}

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <HealthwatchApp />
  </React.StrictMode>,
);
