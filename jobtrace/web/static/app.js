// ═══════════════════════════════════════════════════════════════════════════════
// JOBTRACE — Frontend Application
// Warm Minimal · Notion / Stripe / Apple Inspired
// ═══════════════════════════════════════════════════════════════════════════════

const $ = (id) => document.getElementById(id);
const cards = new Map();
let jobs = [];
let scoringOn = true;
let t0 = 0, scanTimer = null;
let currentView = "cards"; // 'cards' | 'table'
let selectedJobId = null;
let searchIds = null;
let currentProfile = {};

const CHECKS = [
  ["skills", "Tech Stack Fit"],
  ["seniority", "Experience Band"],
  ["location", "Location / Remote"],
  ["domain", "Industry / Domain"],
  ["recency", "Posting Currency"],
  ["reach", "Interview Odds"],
];

// ─── UTILITIES ───────────────────────────────────────────────────────────────

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function safeParse(s) {
  try { return typeof s === "object" ? s : JSON.parse(s) || {}; } catch { return {}; }
}

function bucket(score) {
  if (score === null || score === undefined) return "";
  return "s" + Math.min(5, Math.max(1, Math.ceil(score / 2)));
}

function logo(domain) {
  return domain ? `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=64` : "";
}

function attachLogo(el, job, px) {
  const src = logo(job.domain);
  if (!src) { addInitial(el, job.company); return; }
  const img = new Image();
  img.src = src;
  img.alt = "";
  if (px) { img.width = px; img.height = px; }
  img.onerror = () => { img.remove(); addInitial(el, job.company); };
  el.appendChild(img);
}

function addInitial(el, company) {
  const s = document.createElement("span");
  s.className = "init";
  s.textContent = (company || "?").slice(0, 2).toUpperCase();
  el.appendChild(s);
}

function formatRelativeTime(epoch) {
  if (!epoch) return "";
  const sec = Math.max(0, Math.floor(Date.now() / 1000 - epoch));
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  const days = Math.floor(sec / 86400);
  if (days < 30) return `${days}d ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

// ─── TOAST NOTIFICATIONS ───────────────────────────────────────────────────

let toastTimer = null;
function showToast(message, type = "success") {
  const el = $("toast");
  if (!el) return;
  clearTimeout(toastTimer);
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${type === "success" ? "✓" : "⚠"}</span> <span>${escapeHtml(message)}</span>`;
  el.style.display = "flex";
  toastTimer = setTimeout(() => {
    el.style.display = "none";
  }, 4000);
}

// ─── CARDS & TABLE RENDERING ───────────────────────────────────────────────

function makeCard(job) {
  const card = document.createElement("div");
  const b = bucket(job.score);
  card.className = `job-card ${b} ${job.id === selectedJobId ? "active" : ""}`;
  card.dataset.id = job.id;

  // Header: Logo + Company/Location info + Score Badge
  const header = document.createElement("div");
  header.className = "job-card-header";

  const logoWrap = document.createElement("div");
  logoWrap.className = "job-card-logo";
  attachLogo(logoWrap, job, 24);

  const meta = document.createElement("div");
  meta.className = "job-card-header-info";

  const co = document.createElement("div");
  co.className = "job-card-company";
  co.textContent = job.company;

  const loc = document.createElement("div");
  loc.className = "job-card-location";
  loc.textContent = job.location || "Remote";

  meta.append(co, loc);

  header.append(logoWrap, meta);

  // Score badge on top right
  if (job.score !== null && job.score !== undefined) {
    const badge = document.createElement("div");
    const badgeClass = job.score >= 7 ? "high" : job.score >= 5 ? "med" : "low";
    badge.className = `job-card-badge ${badgeClass}`;
    badge.textContent = `${job.score}/10`;
    header.appendChild(badge);
  }

  // Job Title (full & prominent)
  const title = document.createElement("div");
  title.className = "job-card-title";
  title.textContent = job.title;

  // Matching reason excerpt
  const reason = document.createElement("div");
  reason.className = "job-card-reason";
  reason.textContent = job.reason || (scoringOn ? "Candidate scoring queued" : "Scoring is offline");

  // Footer: Score Bar + Percentage + Open link
  const footer = document.createElement("div");
  footer.className = "job-card-footer";

  const barWrap = document.createElement("div");
  barWrap.className = "job-card-score-bar-wrap";

  if (job.score !== null && job.score !== undefined) {
    const pct = Math.round(job.score * 10);
    const bar = document.createElement("div");
    bar.className = "job-card-bar";
    const fill = document.createElement("div");
    const fillClass = job.score >= 7 ? "high" : job.score >= 5 ? "med" : "";
    fill.className = `job-card-bar-fill ${fillClass}`;
    fill.style.width = `${pct}%`;
    bar.appendChild(fill);

    const pctText = document.createElement("span");
    pctText.className = "job-card-pct";
    pctText.textContent = `${pct}% match`;

    barWrap.append(bar, pctText);
  } else {
    const unscored = document.createElement("span");
    unscored.className = "job-card-pct";
    unscored.textContent = "Unscored";
    barWrap.appendChild(unscored);
  }

  const openLink = document.createElement("span");
  openLink.className = "job-card-open-link";
  openLink.textContent = "View posting ↗";

  footer.append(barWrap, openLink);

  card.append(header, title, reason, footer);

  card.onclick = () => {
    inspectJob(job);
  };

  card.ondblclick = () => {
    if (job.url) window.open(job.url, "_blank", "noopener");
  };

  return card;
}

function makeTableRow(job) {
  const tr = document.createElement("tr");
  if (job.id === selectedJobId) tr.className = "active";
  tr.dataset.id = job.id;

  const scoreBadgeClass =
    job.score >= 7 ? "high" :
    job.score >= 5 ? "med" : "low";

  const scoreText = job.score !== null && job.score !== undefined ? `${job.score}/10` : "—";

  tr.innerHTML = `
    <td>
      <div class="tbl-co-cell">
        <div class="tbl-logo" id="tbl-logo-${job.id}"></div>
        <span>${escapeHtml(job.company)}</span>
      </div>
    </td>
    <td><span class="tbl-title">${escapeHtml(job.title)}</span></td>
    <td><span class="tbl-loc">${escapeHtml(job.location || "Remote")}</span></td>
    <td><span class="tbl-score-badge ${scoreBadgeClass}">${scoreText}</span></td>
    <td><span class="tbl-reason" title="${escapeHtml(job.reason || "")}">${escapeHtml(job.reason || "Awaiting score")}</span></td>
    <td style="text-align: right;">
      <button class="tbl-btn btn-row-open" type="button">Apply ↗</button>
    </td>
  `;

  // Attach logo
  const logoEl = tr.querySelector(`#tbl-logo-${job.id}`);
  if (logoEl) attachLogo(logoEl, job, 16);

  // Row click -> inspect
  tr.onclick = (e) => {
    if (e.target.classList.contains("btn-row-open")) {
      if (job.url) window.open(job.url, "_blank", "noopener");
      return;
    }
    inspectJob(job);
  };

  return tr;
}

// ─── FILTERING & SEARCH ────────────────────────────────────────────────────

const WEEK = 7 * 24 * 3600;

function currentFilter() {
  return {
    q: ($("q") ? $("q").value : "").trim().toLowerCase(),
    min: Number($("minscore") ? $("minscore").value : 0),
    company: $("co") ? $("co").value : "",
    newOnly: $("newonly") ? $("newonly").checked : false,
  };
}

function matches(job, f) {
  if (f.company && job.company !== f.company) return false;
  if (f.min && (job.score === null || job.score === undefined || job.score < f.min)) return false;
  if (f.newOnly && (!job.first_seen || Date.now() / 1000 - job.first_seen > WEEK)) return false;
  if (f.q && searchIds && !searchIds.has(job.id)) return false;
  return true;
}

async function runSearch() {
  const q = ($("q") ? $("q").value : "").trim();
  if (!q) { searchIds = null; renderGrid(); return; }
  try {
    const r = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
    const d = await r.json();
    searchIds = d.ids === null ? null : new Set(d.ids);
  } catch {
    searchIds = null;
  }
  renderGrid();
}

let debounce = null;
function onFilterChange() {
  clearTimeout(debounce);
  debounce = setTimeout(runSearch, 200);
}

function renderGrid() {
  const grid = $("grid");
  const tableBody = $("job-table-body");
  const tableWrap = $("job-table-wrap");
  const f = currentFilter();

  if (grid) grid.textContent = "";
  if (tableBody) tableBody.textContent = "";
  cards.clear();

  let shown = 0;

  for (const j of jobs) {
    if (!matches(j, f)) continue;

    if (currentView === "cards" && grid) {
      const el = makeCard(j);
      cards.set(j.id, el);
      grid.appendChild(el);
    } else if (currentView === "table" && tableBody) {
      const tr = makeTableRow(j);
      cards.set(j.id, tr);
      tableBody.appendChild(tr);
    }
    shown++;
  }

  // Toggle wrap visibility
  if (grid) grid.style.display = currentView === "cards" ? "grid" : "none";
  if (tableWrap) tableWrap.style.display = currentView === "table" ? "block" : "none";

  // Update status bar note
  const filtered = f.q || f.min || f.company || f.newOnly;
  const gridNote = $("gridnote");
  if (gridNote) {
    if (!jobs.length) {
      gridNote.textContent = "No jobs yet — click Run Scan to fetch from ATS job boards";
    } else if (!shown) {
      gridNote.textContent = "No roles match your current filter";
    } else {
      gridNote.textContent = filtered
        ? `Showing ${shown} of ${jobs.length} jobs`
        : `${jobs.length} roles monitored · Click any card to inspect`;
    }
  }
}

function fillCompanies() {
  const sel = $("co");
  if (!sel) return;
  const chosen = sel.value;
  const names = [...new Set(jobs.map((j) => j.company))].sort();
  sel.textContent = "";
  const all = document.createElement("option");
  all.value = ""; all.textContent = "All Companies";
  sel.appendChild(all);
  for (const n of names) {
    const o = document.createElement("option");
    o.value = n; o.textContent = n;
    sel.appendChild(o);
  }
  sel.value = chosen;
}

// ─── INSPECTOR ─────────────────────────────────────────────────────────────

function inspectJob(job) {
  if (!job) {
    if ($("inspector-idle")) $("inspector-idle").style.display = "flex";
    if ($("inspector-body")) $("inspector-body").style.display = "none";
    return;
  }

  selectedJobId = job.id;

  // Active state styling on cards/table
  document.querySelectorAll(".job-card.active, .job-table tr.active").forEach((el) => {
    el.classList.remove("active");
  });
  const activeEl = cards.get(job.id);
  if (activeEl) activeEl.classList.add("active");

  // Show body
  if ($("inspector-idle")) $("inspector-idle").style.display = "none";
  if ($("inspector-body")) $("inspector-body").style.display = "flex";

  // Logo
  const logoBox = $("insp-logo");
  if (logoBox) {
    logoBox.textContent = "";
    attachLogo(logoBox, job, 32);
  }

  // Text
  if ($("insp-company")) $("insp-company").textContent = job.company;
  if ($("insp-title")) $("insp-title").textContent = job.title;

  // Score
  if ($("insp-score")) {
    $("insp-score").textContent = job.score !== null && job.score !== undefined ? job.score : "—";
  }
  if ($("insp-pct")) {
    $("insp-pct").textContent = job.score !== null && job.score !== undefined ? `${job.score * 10}% match` : "unscored";
  }

  // Reason
  if ($("insp-reason")) {
    $("insp-reason").textContent = job.reason || (scoringOn ? "Candidate scoring in queue" : "Scoring is offline");
  }

  // External link
  if ($("insp-open")) {
    $("insp-open").href = job.url || "#";
    $("insp-open").style.display = job.url ? "flex" : "none";
  }

  // Breakdown bars
  renderBreakdowns(job);
}

function renderBreakdowns(job) {
  const container = $("insp-breakdown");
  const sidebarChecks = $("checks");
  if (container) container.textContent = "";
  if (sidebarChecks) sidebarChecks.textContent = "";

  let bd = {};
  if (job && job.breakdown) {
    bd = safeParse(job.breakdown);
  }

  for (const [key, label] of CHECKS) {
    const val = Math.max(0, Math.min(100, Number(bd[key]) || 0));
    const colorClass = val >= 80 ? "high" : val >= 50 ? "med" : "";

    // Inspector Breakdown row
    if (container) {
      const row = document.createElement("div");
      row.className = "insp-breakdown-row";
      row.innerHTML = `
        <span class="insp-bd-key">${escapeHtml(label)}</span>
        <div class="insp-bd-bar"><i class="${colorClass}" style="width:${val}%"></i></div>
        <span class="insp-bd-val">${val}%</span>
      `;
      container.appendChild(row);
    }

    // Sidebar breakdown list item
    if (sidebarChecks) {
      const li = document.createElement("li");
      li.className = "breakdown-item";
      li.innerHTML = `
        <div class="breakdown-meta">
          <span class="breakdown-name">${escapeHtml(label)}</span>
          <span class="breakdown-score">${val}%</span>
        </div>
        <div class="breakdown-track"><div class="breakdown-bar ${colorClass}" style="width:${val}%"></div></div>
      `;
      sidebarChecks.appendChild(li);
    }
  }
}

// ─── TOP MATCHES & STATS ───────────────────────────────────────────────────

function renderStats(s) {
  if (!s) return;
  if ($("s-checked")) $("s-checked").textContent = s.checked;
  if ($("s-total")) $("s-total").textContent = s.total;
  if ($("s-hire")) $("s-hire").textContent = s.would_apply;
  if ($("s-avg")) $("s-avg").textContent = Number(s.avg).toFixed(1);
}

function renderTops() {
  const scored = jobs.filter((j) => j.score !== null && j.score !== undefined);
  scored.sort((a, b) => b.score - a.score);
  const top = scored.slice(0, 5);
  const box = $("tops");
  if (!box) return;
  box.textContent = "";

  if (!top.length) {
    box.innerHTML = `<div class="tops-empty">${scoringOn ? "No scored roles yet" : "Scoring is offline"}</div>`;
    return;
  }

  for (const j of top) {
    const a = document.createElement("a");
    a.className = "top-item";
    a.href = j.url || "#";
    a.target = "_blank";
    a.rel = "noopener";
    a.title = `${j.title} — ${j.company} (${j.score}/10)`;

    const mark = document.createElement("div");
    mark.className = "top-logo";
    attachLogo(mark, j, 18);

    const info = document.createElement("div");
    info.className = "top-info";
    info.innerHTML = `<div class="top-title">${escapeHtml(j.title)}</div><div class="top-co">${escapeHtml(j.company)}</div>`;

    const pct = document.createElement("div");
    pct.className = "top-pct";
    pct.textContent = `${j.score * 10}%`;

    a.append(mark, info, pct);
    box.appendChild(a);
  }
}

// ─── STATE & PROFILE LOADING ───────────────────────────────────────────────

async function loadState() {
  try {
    const r = await fetch("/api/state");
    const d = await r.json();
    jobs = d.jobs || [];
    scoringOn = d.scoring !== false;
    fillCompanies();
    renderGrid();
    renderStats(d.stats);
    renderTops();

    // Auto-inspect best match if none selected
    if (!selectedJobId && jobs.length) {
      const best = jobs.find((j) => j.score !== null) || jobs[0];
      inspectJob(best);
    } else if (selectedJobId) {
      const curr = jobs.find((j) => j.id === selectedJobId);
      if (curr) inspectJob(curr);
    }
  } catch (err) {
    console.error("Failed to load state:", err);
  }
}

async function loadProfile() {
  try {
    const d = await fetch("/api/profile").then((r) => r.json());
    currentProfile = d;

    if (d.name) {
      if ($("p-name")) $("p-name").textContent = d.name;
      if ($("avatar")) {
        const initials = d.name.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();
        $("avatar").textContent = initials || "JT";
      }
    }
    if ($("p-headline")) $("p-headline").textContent = d.headline || "Job Seeker";
    if ($("p-location-text")) $("p-location-text").textContent = d.location || "Remote";

    // Seniority Tag
    const sTag = $("p-seniority-tag");
    if (sTag) {
      const band = (d.seniority || "junior").toLowerCase();
      sTag.textContent = band.toUpperCase();
      sTag.className = `seniority-band band-${band}`;
      sTag.title = d.seniority_reason || `Derived seniority: ${band}`;
    }

    // Experience list
    const expUl = $("exp");
    if (expUl) {
      expUl.textContent = "";
      const exps = d.experience || [];
      if (!exps.length) {
        expUl.innerHTML = `<li class="exp-empty">${escapeHtml(d.error || "Drop resume to parse")}</li>`;
      } else {
        for (const e of exps) {
          const li = document.createElement("li");
          li.className = "exp-item";
          li.innerHTML = `
            <div class="exp-role-title">${escapeHtml(e.role || "Role")}</div>
            <div class="exp-org-row">
              <span class="exp-org">${escapeHtml(e.org || "")}</span>
              <span class="exp-yr">${escapeHtml(e.years || "")}</span>
            </div>
          `;
          expUl.appendChild(li);
        }
      }
    }

    // Skills chips
    const skillsBox = $("profile-skills");
    if (skillsBox) {
      skillsBox.textContent = "";
      const skills = d.skills || [];
      if (skills.length) {
        const INITIAL_LIMIT = 8;
        let isExpanded = false;

        skills.forEach((s, idx) => {
          const chip = document.createElement("span");
          chip.className = `chip ${idx >= INITIAL_LIMIT ? "chip-extra" : ""}`;
          if (idx >= INITIAL_LIMIT) chip.style.display = "none";
          chip.textContent = s;
          skillsBox.appendChild(chip);
        });

        if (skills.length > INITIAL_LIMIT) {
          const toggleBtn = document.createElement("button");
          toggleBtn.className = "chip chip-toggle";
          toggleBtn.type = "button";
          toggleBtn.textContent = `+${skills.length - INITIAL_LIMIT} more`;
          toggleBtn.onclick = (e) => {
            e.stopPropagation();
            isExpanded = !isExpanded;
            skillsBox.querySelectorAll(".chip-extra").forEach((el) => {
              el.style.display = isExpanded ? "inline-flex" : "none";
            });
            toggleBtn.textContent = isExpanded ? "Show less" : `+${skills.length - INITIAL_LIMIT} more`;
          };
          skillsBox.appendChild(toggleBtn);
        }
      } else {
        skillsBox.innerHTML = '<span class="chip chip-muted">No skills detected</span>';
      }
    }
  } catch (err) {
    console.error("Failed to load profile:", err);
  }
}

// ─── LIVE SSE SCAN STREAM ──────────────────────────────────────────────────

function addScanChip(company, count, error) {
  const container = $("scan-chips");
  if (!container) return;
  const chip = document.createElement("div");
  chip.className = "scan-live-chip";
  if (error) {
    chip.innerHTML = `<span class="chip-dot" style="background:var(--red)"></span> <span>${escapeHtml(company)}: failed</span>`;
  } else {
    chip.innerHTML = `<span class="chip-dot"></span> <span>${escapeHtml(company)}: <strong>${count}</strong></span>`;
  }
  container.prepend(chip);
}

function startScan() {
  const btn = $("scan");
  const banner = $("scan-live-banner");
  const chips = $("scan-chips");
  const phase = $("scan-phase-text");
  const timerTag = $("scan-timer");

  if (btn) {
    btn.disabled = true;
    btn.classList.add("scanning");
    if ($("scan-label")) $("scan-label").textContent = "Scanning…";
  }

  if (banner) banner.style.display = "flex";
  if (chips) chips.textContent = "";
  if (phase) phase.textContent = "Connecting to Live ATS APIs…";

  t0 = Date.now();
  scanTimer = setInterval(() => {
    if (timerTag) timerTag.textContent = `${((Date.now() - t0) / 1000).toFixed(1)}s`;
  }, 100);

  const es = new EventSource("/api/scan?limit=3000");

  es.onmessage = (ev) => {
    try {
      const d = JSON.parse(ev.data);

      if (d.type === "fetch") {
        if (phase) phase.textContent = `Querying: ${d.company}`;
        addScanChip(d.company, d.count, d.error);
      } else if (d.type === "fetched") {
        if (phase) phase.textContent = `Diffing complete (${d.total} active) — Scoring against resume…`;
        loadState();
      } else if (d.type === "scoring") {
        if (phase) phase.textContent = `Scoring ${d.count} roles with AI model…`;
      } else if (d.type === "looking") {
        if (phase) phase.textContent = `Evaluating: ${d.company} — ${d.title}`;
      } else if (d.type === "scored") {
        const j = jobs.find((x) => x.id === d.id);
        if (j) {
          j.score = d.score;
          j.reason = d.reason;
          j.breakdown = d.breakdown || {};
          if (j.id === selectedJobId) inspectJob(j);
        }
        renderTops();
      } else if (d.type === "throttled") {
        showToast(d.message || "Scorer rate limited", "error");
      } else if (d.type === "error") {
        showToast(d.message || "Scan error encountered", "error");
      } else if (d.type === "done") {
        es.close();
        clearInterval(scanTimer);
        if (btn) {
          btn.disabled = false;
          btn.classList.remove("scanning");
          if ($("scan-label")) $("scan-label").textContent = "Run Scan";
        }
        if (phase) phase.textContent = `✓ Scan complete: ${d.scored} scored (${d.elapsed}s)`;
        showToast(`Scan complete: ${d.scored} roles scored in ${d.elapsed}s!`, "success");
        loadState();
        setTimeout(() => {
          if (banner) banner.style.display = "none";
        }, 8000);
      }
    } catch (err) {
      console.error("SSE parse error:", err);
    }
  };

  es.onerror = () => {
    es.close();
    clearInterval(scanTimer);
    if (btn) {
      btn.disabled = false;
      btn.classList.remove("scanning");
      if ($("scan-label")) $("scan-label").textContent = "Run Scan";
    }
    showToast("Scan connection finished", "info");
    loadState();
  };
}

// ─── RESUME UPLOAD & ANALYSIS MODAL ────────────────────────────────────────

const fileInput = $("resume-file-input");
const dropzone = $("resume-dropzone");
const profileModal = $("profile-modal");

async function uploadResumeFile(file) {
  if (!file) return;
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (![".pdf", ".txt", ".md", ".docx", ".rtf"].includes(ext)) {
    showToast(`Unsupported file type: ${ext}. Please upload a PDF or TXT.`, "error");
    return;
  }

  showToast(`Uploading and extracting: ${file.name}…`, "info");
  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/upload-resume", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (data.ok) {
      if ($("resume-filename")) $("resume-filename").textContent = data.filename;
      if ($("modal-resume-name")) $("modal-resume-name").textContent = data.filename;
      showToast(`Resume parsed successfully: ${data.filename}`, "success");
      await loadProfile();
      openProfileModal(data.profile || currentProfile);
    } else {
      showToast(data.error || "Failed to upload resume", "error");
    }
  } catch (err) {
    showToast(`Upload failed: ${err.message}`, "error");
  } finally {
    if (fileInput) fileInput.value = "";
  }
}

function addExperienceCard(e = { org: "", role: "", years: "", highlights: "" }) {
  const container = $("conf-experience-list");
  if (!container) return;
  const card = document.createElement("div");
  card.className = "exp-editor-card";
  card.style.cssText = "background:var(--surface-2); border:1px solid var(--border); border-radius:var(--radius-sm); padding:10px; margin-bottom:8px;";
  card.innerHTML = `
    <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
      <strong style="font-size:12px; color:var(--accent);">Position</strong>
      <button type="button" class="btn-del-pos" style="background:transparent; color:var(--red); font-size:11px;">✕ Remove</button>
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:6px; margin-bottom:6px;">
      <input type="text" class="field-input conf-exp-org" style="background:var(--surface); padding:6px;" value="${escapeHtml(e.org || "")}" placeholder="Company Name">
      <input type="text" class="field-input conf-exp-role" style="background:var(--surface); padding:6px;" value="${escapeHtml(e.role || "")}" placeholder="Job Title / Role">
    </div>
    <input type="text" class="field-input conf-exp-years" style="background:var(--surface); padding:6px; margin-bottom:6px;" value="${escapeHtml(e.years || "")}" placeholder="Dates / Duration (e.g. 2022 - Present)">
    <input type="text" class="field-input conf-exp-highlights" style="background:var(--surface); padding:6px;" value="${escapeHtml(e.highlights || "")}" placeholder="Key highlights / tech stack">
  `;
  card.querySelector(".btn-del-pos").onclick = () => card.remove();
  container.appendChild(card);
}

function openProfileModal(data = null) {
  const p = data || currentProfile || {};
  if (!profileModal) return;

  const band = (p.seniority || "junior").toLowerCase();
  if ($("analysis-band-tag")) {
    $("analysis-band-tag").textContent = band.toUpperCase();
    $("analysis-band-tag").className = `band-badge band-${band}`;
  }
  if ($("analysis-years-label")) {
    $("analysis-years-label").textContent = `${p.years_of_experience !== undefined ? p.years_of_experience : "1.0"} yr`;
  }
  if ($("analysis-reason-text")) {
    $("analysis-reason-text").textContent = p.seniority_reason || `Derived seniority band based on resume history.`;
  }
  if ($("conf-seniority")) $("conf-seniority").value = band;

  if ($("conf-name")) $("conf-name").value = p.name || "";
  if ($("conf-headline")) $("conf-headline").value = p.headline || "";
  if ($("conf-location")) $("conf-location").value = p.location || "";
  if ($("conf-target-locations")) {
    const locs = p.target_locations || (p.location ? ["Remote", p.location] : ["Remote"]);
    $("conf-target-locations").value = Array.isArray(locs) ? locs.join(", ") : String(locs);
  }
  if ($("conf-summary")) $("conf-summary").value = p.summary || "";
  if ($("conf-skills")) {
    const skills = p.skills || [];
    $("conf-skills").value = Array.isArray(skills) ? skills.join(", ") : String(skills);
  }

  const expList = $("conf-experience-list");
  if (expList) {
    expList.textContent = "";
    const exps = p.experience || [];
    if (exps.length) {
      exps.forEach((e) => addExperienceCard(e));
    } else {
      addExperienceCard({ org: "", role: "", years: "", highlights: "" });
    }
  }

  if ($("conf-education")) {
    if (Array.isArray(p.education) && p.education.length) {
      $("conf-education").value = p.education.map((ed) =>
        [ed.degree, ed.institution, ed.year].filter(Boolean).join(" — ")
      ).join("; ");
    } else {
      $("conf-education").value = typeof p.education === "string" ? p.education : "";
    }
  }

  profileModal.style.display = "flex";
}

function closeProfileModal() {
  if (profileModal) profileModal.style.display = "none";
}

async function saveConfirmedProfile() {
  const btn = $("btn-profile-confirm");
  if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }

  const exps = [];
  document.querySelectorAll("#conf-experience-list .exp-editor-card").forEach((card) => {
    const org = (card.querySelector(".conf-exp-org")?.value || "").trim();
    const role = (card.querySelector(".conf-exp-role")?.value || "").trim();
    const years = (card.querySelector(".conf-exp-years")?.value || "").trim();
    const highlights = (card.querySelector(".conf-exp-highlights")?.value || "").trim();
    if (org || role) {
      exps.push({ org, role, years, highlights });
    }
  });

  const rawSkills = ($("conf-skills")?.value || "").split(",");
  const cleanSkills = rawSkills.map((s) => s.trim()).filter(Boolean);

  const rawLocs = ($("conf-target-locations")?.value || "").split(",");
  const cleanLocs = rawLocs.map((l) => l.trim()).filter(Boolean);

  const eduStr = ($("conf-education")?.value || "").trim();

  const payload = {
    name: ($("conf-name")?.value || "").trim(),
    headline: ($("conf-headline")?.value || "").trim(),
    location: ($("conf-location")?.value || "").trim(),
    target_locations: cleanLocs,
    seniority: $("conf-seniority")?.value || "junior",
    years_of_experience: currentProfile.years_of_experience || 1.0,
    seniority_reason: ($("analysis-reason-text")?.textContent || "").trim(),
    summary: ($("conf-summary")?.value || "").trim(),
    skills: cleanSkills,
    experience: exps,
    education: eduStr ? [{ degree: eduStr, institution: "", year: "" }] : [],
  };

  try {
    const res = await fetch("/api/profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const d = await res.json();
    if (d.ok) {
      showToast("Profile & seniority analysis confirmed!", "success");
      closeProfileModal();
      await loadProfile();
      await loadState();
    } else {
      showToast(d.error || "Failed to save profile", "error");
    }
  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "Confirm & save"; }
  }
}

// ─── ADMIN SETTINGS MODAL ──────────────────────────────────────────────────

const settingsModal = $("settings-modal");

function openSettingsModal() {
  if (!settingsModal) return;
  settingsModal.style.display = "flex";
  loadSettings();
}

function closeSettingsModal() {
  if (!settingsModal) return;
  settingsModal.style.display = "none";
}

async function loadSettings() {
  try {
    const res = await fetch("/api/settings");
    const d = await res.json();

    // Telegram
    if ($("cfg-bot-token")) $("cfg-bot-token").value = d.telegram.bot_token || "";
    if ($("cfg-chat-ids")) $("cfg-chat-ids").value = d.telegram.chat_ids_raw || (d.telegram.chat_ids || []).join(", ");

    // AI
    if ($("cfg-llm-provider")) $("cfg-llm-provider").value = d.llm.provider || "xkiro";
    if ($("cfg-llm-model")) $("cfg-llm-model").value = d.llm.model || "";
    if ($("cfg-min-score")) $("cfg-min-score").value = d.llm.min_score !== undefined ? d.llm.min_score : 6;
    if ($("cfg-llm-triage")) $("cfg-llm-triage").checked = !!d.llm.triage;

    // Keys
    const keys = d.api_keys || {};
    if ($("key-xkiro")) $("key-xkiro").value = keys.XKIRO_API_KEY || "";
    if ($("key-openai")) $("key-openai").value = keys.OPENAI_API_KEY || "";
    if ($("key-openrouter")) $("key-openrouter").value = keys.OPENROUTER_API_KEY || "";
    if ($("key-cursor")) $("key-cursor").value = keys.CURSOR_API_KEY || "";
    if ($("key-anthropic")) $("key-anthropic").value = keys.ANTHROPIC_API_KEY || "";

    // Candidate
    if ($("cfg-seniority")) $("cfg-seniority").value = d.candidate.seniority || "junior";
    if ($("cfg-locations")) $("cfg-locations").value = (d.candidate.locations || []).join(", ");
    if ($("modal-resume-name")) $("modal-resume-name").textContent = d.resume_path || "resume.pdf";
    if ($("resume-filename")) $("resume-filename").textContent = d.resume_path || "resume.pdf";
  } catch (err) {
    showToast(`Failed to load settings: ${err.message}`, "error");
  }
}

async function saveSettings() {
  const btn = $("btn-settings-save");
  if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }

  const payload = {
    telegram: {
      bot_token: $("cfg-bot-token") ? $("cfg-bot-token").value.trim() : "",
      chat_ids: $("cfg-chat-ids") ? $("cfg-chat-ids").value.trim() : "",
    },
    llm: {
      provider: $("cfg-llm-provider") ? $("cfg-llm-provider").value : "xkiro",
      model: $("cfg-llm-model") ? $("cfg-llm-model").value.trim() : "",
      min_score: $("cfg-min-score") ? Number($("cfg-min-score").value) : 6,
      triage: $("cfg-llm-triage") ? $("cfg-llm-triage").checked : false,
    },
    candidate: {
      seniority: $("cfg-seniority") ? $("cfg-seniority").value : "junior",
      locations: $("cfg-locations") ? $("cfg-locations").value : "",
    },
    api_keys: {
      XKIRO_API_KEY: $("key-xkiro") ? $("key-xkiro").value.trim() : "",
      OPENAI_API_KEY: $("key-openai") ? $("key-openai").value.trim() : "",
      OPENROUTER_API_KEY: $("key-openrouter") ? $("key-openrouter").value.trim() : "",
      CURSOR_API_KEY: $("key-cursor") ? $("key-cursor").value.trim() : "",
      ANTHROPIC_API_KEY: $("key-anthropic") ? $("key-anthropic").value.trim() : "",
    },
  };

  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const d = await res.json();
    if (d.ok) {
      showToast("Settings and credentials saved successfully!", "success");
      closeSettingsModal();
      loadState();
    } else {
      showToast(d.message || "Failed to save settings", "error");
    }
  } catch (err) {
    showToast(`Error saving settings: ${err.message}`, "error");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "Save changes"; }
  }
}

async function testTelegramConnection() {
  const btn = $("btn-test-telegram");
  const result = $("telegram-test-result");
  if (btn) { btn.disabled = true; btn.textContent = "Pinging…"; }
  if (result) {
    result.style.display = "block";
    result.className = "test-feedback";
    result.textContent = "Connecting to Telegram Bot API…";
  }

  const bot_token = $("cfg-bot-token") ? $("cfg-bot-token").value.trim() : "";
  const chat_ids = $("cfg-chat-ids") ? $("cfg-chat-ids").value.trim() : "";

  try {
    const res = await fetch("/api/test-telegram", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bot_token, chat_ids }),
    });
    const d = await res.json();
    if (result) {
      result.className = `test-feedback ${d.ok ? "success" : "error"}`;
      result.textContent = d.message;
    }
    showToast(d.message, d.ok ? "success" : "error");
  } catch (err) {
    if (result) {
      result.className = "test-feedback error";
      result.textContent = `Ping failed: ${err.message}`;
    }
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "Send ping"; }
  }
}

// ─── INITIALIZATION & EVENT LISTENERS ──────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  // View Switcher (Cards vs Table)
  const btnCards = $("btn-view-cards");
  const btnTable = $("btn-view-table");

  if (btnCards && btnTable) {
    btnCards.onclick = () => {
      currentView = "cards";
      btnCards.classList.add("active");
      btnTable.classList.remove("active");
      renderGrid();
    };
    btnTable.onclick = () => {
      currentView = "table";
      btnTable.classList.add("active");
      btnCards.classList.remove("active");
      renderGrid();
    };
  }

  // Scan button
  if ($("scan")) $("scan").onclick = startScan;

  // Search & Filters
  if ($("q")) {
    $("q").addEventListener("input", onFilterChange);
    $("q").addEventListener("keydown", (e) => {
      if (e.key === "Escape") { $("q").value = ""; searchIds = null; renderGrid(); }
    });
  }
  if ($("minscore")) $("minscore").addEventListener("change", renderGrid);
  if ($("co")) $("co").addEventListener("change", renderGrid);
  if ($("newonly")) $("newonly").addEventListener("change", renderGrid);

  // Settings Modal triggers
  if ($("btn-settings")) $("btn-settings").onclick = openSettingsModal;
  if ($("settings-close")) $("settings-close").onclick = closeSettingsModal;
  if ($("btn-settings-cancel")) $("btn-settings-cancel").onclick = closeSettingsModal;
  if ($("btn-settings-save")) $("btn-settings-save").onclick = saveSettings;
  if ($("btn-test-telegram")) $("btn-test-telegram").onclick = testTelegramConnection;

  // Tabs inside Settings Modal
  document.querySelectorAll(".modal-tab").forEach((tab) => {
    tab.onclick = () => {
      document.querySelectorAll(".modal-tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      const pane = $(tab.dataset.tab);
      if (pane) pane.classList.add("active");
    };
  });

  // Password eye visibility toggles
  document.querySelectorAll(".vis-btn").forEach((btn) => {
    btn.onclick = () => {
      const input = $(btn.dataset.for);
      if (input) {
        input.type = input.type === "password" ? "text" : "password";
      }
    };
  });

  // Profile Modal triggers
  if ($("btn-edit-profile")) $("btn-edit-profile").onclick = () => openProfileModal(currentProfile);
  if ($("profile-modal-close")) $("profile-modal-close").onclick = closeProfileModal;
  if ($("btn-profile-cancel")) $("btn-profile-cancel").onclick = closeProfileModal;
  if ($("btn-profile-confirm")) $("btn-profile-confirm").onclick = saveConfirmedProfile;
  if ($("btn-add-experience")) $("btn-add-experience").onclick = () => addExperienceCard();

  if ($("conf-seniority")) {
    $("conf-seniority").onchange = (e) => {
      const val = (e.target.value || "junior").toLowerCase();
      const tag = $("analysis-band-tag");
      if (tag) {
        tag.textContent = val.toUpperCase();
        tag.className = `band-badge band-${val}`;
      }
    };
  }

  // Resume Upload button triggers
  if ($("btn-upload-resume")) $("btn-upload-resume").onclick = () => fileInput && fileInput.click();
  if ($("btn-modal-upload-resume")) $("btn-modal-upload-resume").onclick = () => fileInput && fileInput.click();
  if (fileInput) {
    fileInput.onchange = (e) => {
      if (e.target.files && e.target.files[0]) {
        uploadResumeFile(e.target.files[0]);
      }
    };
  }

  // Resume Drag & Drop
  if (dropzone) {
    ["dragenter", "dragover"].forEach((evt) => {
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add("dragover");
      });
    });
    ["dragleave", "drop"].forEach((evt) => {
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove("dragover");
      });
    });
    dropzone.addEventListener("drop", (e) => {
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
        uploadResumeFile(e.dataTransfer.files[0]);
      }
    });
  }

  // Modal backdrop click to close
  if (settingsModal) {
    settingsModal.onclick = (e) => { if (e.target === settingsModal) closeSettingsModal(); };
  }
  if (profileModal) {
    profileModal.onclick = (e) => { if (e.target === profileModal) closeProfileModal(); };
  }

  // Escape key closes modals
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (settingsModal && settingsModal.style.display !== "none") closeSettingsModal();
      if (profileModal && profileModal.style.display !== "none") closeProfileModal();
    }
  });

  // Load Initial Data
  loadProfile();
  loadState();
});
