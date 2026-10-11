const symptomList = document.getElementById('symptom-list');
const reportList = document.getElementById('report-list');
const form = document.getElementById('symptom-form');
const formStatus = document.getElementById('form-status');
const patientCard = document.getElementById('patient-card');
const summaryCard = document.getElementById('summary-card');
const patientIdField = document.getElementById('patient-id');
const reportNotesField = document.getElementById('report-notes');
const clearDatabaseButton = document.getElementById('clear-database');
const clearHistoryButton = document.getElementById('clear-history');

async function loadPatientProfile() {
  const response = await fetch('/api/patient');
  if (!response.ok) {
    throw new Error('Unable to load patient profile.');
  }

  const result = await response.json();
  const patient = result.patient;

  patientIdField.textContent = patient.id;
  patientCard.innerHTML = `
    <div class="stat-box">
      <strong>${patient.name}</strong>
      <span>Patient</span>
    </div>
    <div class="stat-box">
      <strong>${patient.age}</strong>
      <span>Age</span>
    </div>
    <div class="stat-box">
      <strong>${patient.gender}</strong>
      <span>Gender</span>
    </div>
    <div class="stat-box">
      <strong>${patient.condition}</strong>
      <span>Condition</span>
    </div>
    <div class="stat-box">
      <strong>${patient.care_team}</strong>
      <span>Care team</span>
    </div>
  `;
}

async function loadSymptoms() {
  const response = await fetch('/api/symptoms');
  if (!response.ok) {
    throw new Error('Unable to load symptoms.');
  }

  const data = await response.json();
  symptomList.innerHTML = '';

  data.symptoms.forEach((symptom) => {
    const wrapper = document.createElement('label');
    wrapper.className = 'checkbox-item';

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.name = 'symptom';
    checkbox.value = symptom;

    const labelText = document.createElement('span');
    labelText.textContent = symptom;

    wrapper.appendChild(checkbox);
    wrapper.appendChild(labelText);
    symptomList.appendChild(wrapper);
  });
}

function renderReports(reports) {
  if (!reports.length) {
    reportList.innerHTML = '<p>No symptom reports saved yet.</p>';
    return;
  }

  reportList.innerHTML = reports
    .map((report) => {
      const symptomTags = report.symptoms
        .map((symptom) => `<span class="pill">${symptom}</span>`)
        .join('');
      const notes = report.notes
        ? `<p class="report-notes">${escapeHtml(report.notes)}</p>`
        : '';

      return `
        <article class="history-item">
          <h3>Report #${report.id}</h3>
          <div class="meta">Submitted: ${new Date(report.submitted_at).toLocaleString()}</div>
          <div class="pill-list">${symptomTags}</div>
          ${notes}
        </article>
      `;
    })
    .join('');
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[character]);
}

async function loadReportSummary() {
  const response = await fetch('/api/symptom_report/summary');
  if (!response.ok) {
    throw new Error('Unable to load report summary.');
  }

  const result = await response.json();
  const summary = result.summary;

  summaryCard.innerHTML = `
    <div class="stat-box">
      <strong>${summary.total_reports}</strong>
      <span>Total reports</span>
    </div>
    <div class="stat-box">
      <strong>${summary.total_symptom_entries}</strong>
      <span>Logged symptoms</span>
    </div>
  `;
}

async function loadReports() {
  const response = await fetch('/api/symptom_report?limit=20&offset=0');
  if (!response.ok) {
    throw new Error('Unable to load symptom history.');
  }

  const data = await response.json();
  renderReports(data.reports || []);
}

async function submitReport(event) {
  event.preventDefault();

  const selectedSymptoms = [...document.querySelectorAll('input[name="symptom"]:checked')].map(
    (checkbox) => checkbox.value,
  );

  if (!selectedSymptoms.length) {
    showStatus('Please select at least one symptom.', true);
    return;
  }

  try {
    const response = await fetch('/api/symptom_report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symptoms: selectedSymptoms,
        notes: reportNotesField.value,
      }),
    });

    const result = await response.json();
    if (!response.ok) {
      const detail = Array.isArray(result.detail)
        ? result.detail[0]?.msg
        : result.detail;
      throw new Error(detail || 'Unable to save report.');
    }

    form.reset();
    showStatus('Symptom report saved.', false);
    await loadReports();
    await loadReportSummary();
  } catch (error) {
    showStatus(error.message, true);
  }
}

async function clearReportHistory() {
  try {
    const response = await fetch('/api/symptom_report', {
      method: 'DELETE',
    });

    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.detail || 'Unable to clear the database.');
    }

    showStatus(`Cleared ${result.deleted_rows} saved report(s).`, false);
    await loadReports();
    await loadReportSummary();
  } catch (error) {
    showStatus(error.message, true);
  }
}

function showStatus(message, isError) {
  formStatus.textContent = message;
  formStatus.classList.toggle('error', isError);
  formStatus.classList.toggle('success', !isError);
}

async function initializeDemo() {
  try {
    await loadPatientProfile();
    await loadSymptoms();
    await loadReports();
    await loadReportSummary();
  } catch (error) {
    showStatus(error.message, true);
  }
}

form.addEventListener('submit', submitReport);
clearDatabaseButton.addEventListener('click', clearReportHistory);
clearHistoryButton.addEventListener('click', clearReportHistory);
initializeDemo();
