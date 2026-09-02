/**
 * Personal AI Job Hunter — Client Application Logic
 */

let currentTab = "review";
let allJobsData = [];

// DOM Elements
const jobsContainer = document.getElementById("jobs-container");
const jobModal = document.getElementById("job-modal");
const modalBody = document.getElementById("modal-body");
const modalCloseBtn = document.getElementById("modal-close-btn");
const searchInput = document.getElementById("filter-search");
const recFilter = document.getElementById("filter-rec");
const modeFilter = document.getElementById("filter-mode");
const refreshBtn = document.getElementById("btn-refresh");
const runPipelineBtn = document.getElementById("btn-run-pipeline");

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  loadDashboardStats();
  loadTabData();
});

function setupEventListeners() {
  // Tabs
  document.querySelectorAll(".nav-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".nav-tab").forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      currentTab = tab.dataset.tab;
      loadTabData();
    });
  });

  // Filters
  searchInput.addEventListener("input", filterAndRenderJobs);
  recFilter.addEventListener("change", filterAndRenderJobs);
  modeFilter.addEventListener("change", filterAndRenderJobs);
  refreshBtn.addEventListener("click", () => {
    loadDashboardStats();
    loadTabData();
  });

  // Pipeline Run
  runPipelineBtn.addEventListener("click", triggerPipelineRun);

  // Modal Close
  modalCloseBtn.addEventListener("click", () => jobModal.classList.remove("open"));
  jobModal.addEventListener("click", (e) => {
    if (e.target === jobModal) jobModal.classList.remove("open");
  });
}

// Show Toast
function showToast(message) {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// Load High-Level Stats
async function loadDashboardStats() {
  try {
    const res = await fetch("/api/stats");
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById("stat-total-jobs").textContent = data.total_canonical_jobs || 0;
    document.getElementById("stat-apply").textContent = data.recommendations_breakdown?.APPLY || 0;
    document.getElementById("stat-stretch").textContent = data.recommendations_breakdown?.STRETCH || 0;

    const apps = data.applications_breakdown || {};
    document.getElementById("stat-pending").textContent = apps.PENDING_HUMAN_REVIEW || 0;
    document.getElementById("stat-ready").textContent = apps.READY_TO_APPLY || 0;
    document.getElementById("stat-applied").textContent = apps.APPLIED || 0;
    document.getElementById("stat-interviewing").textContent = apps.INTERVIEWING || 0;
    document.getElementById("stat-offers").textContent = apps.OFFER || 0;

    const navBadge = document.getElementById("nav-review-badge");
    navBadge.textContent = `(${apps.PENDING_HUMAN_REVIEW || 0})`;
  } catch (err) {
    console.error("Failed to load stats:", err);
  }
}

// Load Tab Data
async function loadTabData() {
  jobsContainer.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 3rem; color: var(--text-muted);">Loading opportunities...</div>`;

  try {
    if (currentTab === "review") {
      const res = await fetch("/api/jobs/review");
      allJobsData = await res.json();
    } else if (currentTab === "all") {
      const res = await fetch("/api/jobs?limit=100");
      allJobsData = await res.json();
    } else if (currentTab === "applications") {
      const res = await fetch("/api/jobs?limit=100");
      const jobs = await res.json();
      allJobsData = jobs.filter(j => j.application_status && j.application_status !== "PENDING_HUMAN_REVIEW");
    } else if (currentTab === "stats") {
      renderStatsTab();
      return;
    }
    filterAndRenderJobs();
  } catch (err) {
    jobsContainer.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; color: var(--accent-skip); padding: 2rem;">Error loading data: ${err.message}</div>`;
  }
}

// Filter & Render
function filterAndRenderJobs() {
  if (currentTab === "stats") return;

  const query = searchInput.value.toLowerCase();
  const selectedRec = recFilter.value;
  const selectedMode = modeFilter.value;

  const filtered = allJobsData.filter(job => {
    const titleMatch = job.title.toLowerCase().includes(query) || job.company.toLowerCase().includes(query) || job.location.toLowerCase().includes(query);
    const recMatch = !selectedRec || (job.match_score && job.match_score.recommendation === selectedRec);
    const modeMatch = !selectedMode || job.work_mode.toLowerCase().includes(selectedMode.toLowerCase());
    return titleMatch && recMatch && modeMatch;
  });

  if (filtered.length === 0) {
    jobsContainer.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 3rem; color: var(--text-muted);">No matching jobs found in this view.</div>`;
    return;
  }

  jobsContainer.innerHTML = filtered.map(job => renderJobCard(job)).join("");
}

// Render Job Card HTML
function renderJobCard(job) {
  const score = job.match_score;
  const rec = score ? score.recommendation : "UNKNOWN";
  const overallScore = score ? score.overall_score.toFixed(1) : "N/A";
  const detScore = score && score.deterministic_score != null ? score.deterministic_score.toFixed(1) : "N/A";
  const semScore = score && score.semantic_score != null ? score.semantic_score.toFixed(1) : "N/A";

  let badgeClass = "badge-skip";
  if (rec === "APPLY") badgeClass = "badge-apply";
  else if (rec === "STRETCH") badgeClass = "badge-stretch";

  const appStatus = job.application_status || "PENDING_HUMAN_REVIEW";
  const applyUrl = (job.application_urls && job.application_urls.length > 0) ? job.application_urls[0] : "#";

  const skillsHtml = (score?.matched_skills || []).slice(0, 4)
    .map(s => `<span class="skill-tag">${s}</span>`).join("");

  return `
    <div class="job-card">
      <div>
        <div class="job-card-header">
          <div>
            <h3 class="job-title">${job.title}</h3>
            <div class="job-company">${job.company}</div>
          </div>
          <div class="score-badge ${badgeClass}">
            <span>${rec}</span>
            <span>${overallScore}</span>
          </div>
        </div>

        <div class="job-meta">
          <span class="meta-chip">📍 ${job.location}</span>
          <span class="meta-chip">💼 ${job.work_mode}</span>
          <span class="meta-chip">🎯 Det: ${detScore} | Sem: ${semScore}</span>
          <span class="meta-chip" style="color: var(--accent-cyan);">📌 ${appStatus}</span>
        </div>

        <div class="skills-row">
          ${skillsHtml}
        </div>
      </div>

      <div class="card-actions">
        <button class="btn btn-outline" onclick="openJobDetails('${job.canonical_id}')">🔍 Details</button>
        ${renderCardActionButtons(job.canonical_id, appStatus, applyUrl)}
      </div>
    </div>
  `;
}

function renderCardActionButtons(canonicalId, status, applyUrl) {
  if (status === "PENDING_HUMAN_REVIEW") {
    return `
      <button class="btn btn-approve" onclick="handleAction('${canonicalId}', 'approve')">✓ Approve</button>
      <button class="btn btn-reject" onclick="handleAction('${canonicalId}', 'reject')">✗ Reject</button>
    `;
  }
  if (status === "READY_TO_APPLY") {
    return `
      <a href="${applyUrl}" target="_blank" class="btn btn-primary">🔗 Open Portal</a>
      <button class="btn btn-applied" onclick="handleAction('${canonicalId}', 'mark-applied')">Mark Applied</button>
    `;
  }
  if (status === "APPLIED") {
    return `
      <button class="btn btn-outline" onclick="handleAction('${canonicalId}', 'interview')">📅 Schedule Interview</button>
      <button class="btn btn-approve" onclick="handleAction('${canonicalId}', 'offer')">🏆 Got Offer</button>
    `;
  }
  return `<span style="font-size: 0.8rem; color: var(--text-subtle);">Status: ${status}</span>`;
}

// Handle HITL Actions
async function handleAction(canonicalId, action) {
  try {
    let endpoint = `/api/applications/${canonicalId}/${action}`;
    let body = {};

    if (action === "reject") {
      const reason = prompt("Optional reason for rejecting this job:") || "Skipped by candidate";
      body = { reason };
    } else if (action === "mark-applied") {
      const notes = prompt("Submission notes (e.g. customized resume used):") || "Applied via official portal";
      body = { notes };
    } else if (action === "interview") {
      const notes = prompt("Interview stage notes (e.g. Technical Round 1):") || "Interview scheduled";
      body = { notes };
    }

    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const err = await res.json();
      alert(`Action failed: ${err.detail || "Error"}`);
      return;
    }

    showToast(`Application status updated to: ${action.toUpperCase()}`);
    loadDashboardStats();
    loadTabData();
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
}

// Open Job Details Modal
async function openJobDetails(canonicalId) {
  modalBody.innerHTML = "<div style='text-align: center; padding: 2rem;'>Loading job intelligence...</div>";
  jobModal.classList.add("open");

  try {
    const res = await fetch(`/api/jobs/${canonicalId}`);
    if (!res.ok) throw new Error("Failed to load job details");
    const job = await res.json();

    const score = job.match_score;
    const enr = job.enrichment;
    const applyUrl = job.application_urls && job.application_urls[0] ? job.application_urls[0] : "#";

    let enrHtml = "";
    if (enr) {
      enrHtml = `
        <div class="section-title">🤖 LLM Enrichment & Ground Truth Analysis</div>
        <p class="detail-p"><strong>Stated Summary:</strong> ${enr.job_summary || "N/A"}</p>
        
        <div style="margin-top: 0.75rem;">
          <strong style="color: var(--accent-apply);">Candidate Strengths:</strong>
          <ul class="bullet-list">
            ${(enr.candidate_strengths || []).map(s => `<li>${s}</li>`).join("")}
          </ul>
        </div>

        ${enr.gap_analysis && enr.gap_analysis.length > 0 ? `
          <div style="margin-top: 0.75rem;">
            <strong style="color: var(--accent-stretch);">Identified Gaps / Stretch Areas:</strong>
            <ul class="bullet-list">
              ${enr.gap_analysis.map(g => `<li>${g}</li>`).join("")}
            </ul>
          </div>
        ` : ""}

        ${enr.interview_talking_points && enr.interview_talking_points.length > 0 ? `
          <div class="talking-point-box">
            <strong>AVASOFT Talking Point:</strong> ${enr.interview_talking_points[0]}
          </div>
        ` : ""}
      `;
    }

    modalBody.innerHTML = `
      <h2 style="font-size: 1.4rem; color: white;">${job.title}</h2>
      <div style="color: var(--accent-cyan); font-weight: 600; font-size: 1.1rem; margin-bottom: 0.5rem;">${job.company}</div>
      
      <div class="job-meta">
        <span class="meta-chip">📍 ${job.location}</span>
        <span class="meta-chip">💼 ${job.work_mode}</span>
        <span class="meta-chip">📊 Combined: ${score?.overall_score?.toFixed(1) || "N/A"}</span>
        <span class="meta-chip">🎯 Recommendation: ${score?.recommendation || "N/A"}</span>
      </div>

      <div class="section-title">Scoring Breakdown</div>
      <p class="detail-p">
        Role: ${score?.role_score} | Tech: ${score?.technical_score} | Exp: ${score?.experience_score} | Loc: ${score?.location_score}<br>
        Deterministic: ${score?.deterministic_score?.toFixed(1) || "N/A"} | Semantic Similarity: ${score?.semantic_similarity ? (score.semantic_similarity * 100).toFixed(1) + "%" : "N/A"}
      </p>

      ${enrHtml}

      <div class="section-title">Full Job Description</div>
      <div style="max-height: 250px; overflow-y: auto; background: rgba(0,0,0,0.3); padding: 1rem; border-radius: var(--radius-sm); font-size: 0.85rem; color: #cbd5e1; white-space: pre-wrap; line-height: 1.6;">
        ${job.description}
      </div>

      <div style="margin-top: 1.5rem; display: flex; gap: 0.75rem; justify-content: flex-end;">
        <a href="${applyUrl}" target="_blank" class="btn btn-primary">🔗 Open Official Application Portal</a>
        ${renderCardActionButtons(job.canonical_id, job.application_status, applyUrl)}
      </div>
    `;
  } catch (err) {
    modalBody.innerHTML = `<div style="color: var(--accent-skip); padding: 2rem;">Error: ${err.message}</div>`;
  }
}

// Trigger Pipeline Run
async function triggerPipelineRun() {
  runPipelineBtn.disabled = true;
  runPipelineBtn.textContent = "⏳ Running Pipeline...";
  showToast("Unified pipeline ingestion started in background...");

  try {
    const res = await fetch("/api/pipeline/run", { method: "POST" });
    const data = await res.json();
    if (data.status === "SUCCESS") {
      showToast(`Pipeline completed in ${data.duration_seconds}s! (${data.canonical_jobs_count} jobs)`);
    } else {
      showToast(`Pipeline status: ${data.status}`);
    }
    loadDashboardStats();
    loadTabData();
  } catch (err) {
    showToast(`Pipeline trigger failed: ${err.message}`);
  } finally {
    runPipelineBtn.disabled = false;
    runPipelineBtn.textContent = "⚡ Run Pipeline";
  }
}

// Render Stats Tab
function renderStatsTab() {
  jobsContainer.innerHTML = `
    <div style="grid-column: 1 / -1; background: var(--bg-surface); padding: 2rem; border-radius: var(--radius-lg); border: 1px solid var(--border-color);">
      <h2 style="color: white; margin-bottom: 1rem;">System Telemetry & Architecture</h2>
      <p style="color: var(--text-muted); margin-bottom: 1.5rem;">
        Multi-tier deterministic matching + FastEmbed pgvector semantic layer + Gated LLM insights + Human-in-the-Loop review.
      </p>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
        <div class="stat-card">
          <span class="stat-label">Embedding Model</span>
          <span style="font-size: 1.1rem; color: white; margin-top: 0.5rem;">BAAI/bge-small-en-v1.5 (FastEmbed ONNX)</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">LLM Provider</span>
          <span style="font-size: 1.1rem; color: white; margin-top: 0.5rem;">Google Gemini 1.5 Flash / Fast Mock</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">Persistence</span>
          <span style="font-size: 1.1rem; color: white; margin-top: 0.5rem;">PostgreSQL 16 + pgvector (SQLAlchemy 2.0)</span>
        </div>
      </div>
    </div>
  `;
}
