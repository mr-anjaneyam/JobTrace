const $ = (id) => document.getElementById(id);
const tiles = new Map();
let jobs = [];
let scoringOn = true;
let t0 = 0, timer = null;

const CHECKS = [
  ["skills", "You know the stack"],
  ["seniority", "Level fits you"],
  ["location", "You can work there"],
  ["domain", "Industry / domain match"],
  ["recency", "Experience is current"],
  ["reach", "Realistic interview odds"],
];

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

function makeTile(job) {
  const el = document.createElement("div");
  el.className = "tile " + bucket(job.score);
  el.title = `${job.title} — ${job.company}` + (job.score !== null ? ` · ${job.score}/10` : "");
  attachLogo(el, job);
  el.onclick = () => { if (job.url) window.open(job.url, "_blank", "noopener"); };
  el.onmouseenter = () => inspectJob(job);
  return el;
}

function inspectJob(j) {
  $("lk-company").textContent = j.company;
  $("lk-title").textContent = j.title;
  $("lk-score").textContent = j.score !== null ? `${j.score}/10` : "—";
  renderChecks(j);
}

// --- Filtering & FTS Search ---
const WEEK = 7 * 24 * 3600;
let searchIds = null;

function currentFilter() {
  return {
    q: ($("q").value || "").trim().toLowerCase(),
    min: Number($("minscore").value || 0),
    company: $("co").value || "",
    newOnly: $("newonly").checked,
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
  const q = ($("q").value || "").trim();
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

function renderGrid() {
  const grid = $("grid");
  const f = currentFilter();
  grid.textContent = "";
  tiles.clear();
  let shown = 0;

  for (const j of jobs) {
    if (!matches(j, f)) continue;
    const el = makeTile(j);
    tiles.set(j.id, el);
    grid.appendChild(el);
    shown++;
  }

  const filtered = f.q || f.min || f.company || f.newOnly;
  if (!jobs.length) {
    $("gridnote").textContent = "No jobs yet — press Run Scan";
  } else if (!shown) {
    $("gridnote").textContent = "No roles match your filter";
  } else {
    $("gridnote").textContent =
      (filtered ? `${shown} of ${jobs.length} jobs shown` : `${jobs.length} jobs tracked`) +
      " · Click tile to open posting";
  }
}

function fillCompanies() {
  const sel = $("co");
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

let debounce = null;
function onFilterChange() {
  clearTimeout(debounce);
  debounce = setTimeout(runSearch, 200);
}

function renderStats(s) {
  $("s-checked").textContent = s.checked;
  $("s-total").textContent = s.total;
  $("s-hire").textContent = s.would_apply;
  $("s-avg").textContent = Number(s.avg).toFixed(2);
}

function renderTops() {
  const scored = jobs.filter((j) => j.score !== null && j.score !== undefined);
  scored.sort((a, b) => b.score - a.score);
  const top = scored.slice(0, 5);
  const box = $("tops");
  box.textContent = "";

  if (!top.length) {
    box.innerHTML = `<div class="muted">${scoringOn ? "No scored matches yet" : "Scoring is offline"}</div>`;
    return;
  }

  for (const j of top) {
    const a = document.createElement("a");
    a.className = "top"; a.href = j.url || "#"; a.target = "_blank"; a.rel = "noopener";
    a.title = `${j.title} — ${j.company}` + (j.reason ? `\n${j.reason}` : "");
    const mark = document.createElement("div");
    mark.className = "toplogo";
    attachLogo(mark, j, 20);
    a.appendChild(mark);
    const co = document.createElement("div");
    co.className = "co"; co.textContent = `${j.title.slice(0, 26)} (${j.company})`;
    const pct = document.createElement("div");
    pct.className = "pct"; pct.textContent = `${j.score * 10}%`;
    a.append(co, pct);
    box.appendChild(a);
  }
}

function renderChecks(job) {
  const ul = $("checks");
  ul.textContent = "";
  if (!scoringOn) {
    ul.innerHTML = '<li class="muted">Scoring is turned off in config.</li>';
    return;
  }

  let bd = {};
  if (job && job.breakdown) {
    bd = typeof job.breakdown === "string" ? safeParse(job.breakdown) : job.breakdown;
  }

  for (const [key, claim] of CHECKS) {
    const val = Math.max(0, Math.min(100, Number(bd[key]) || 0));
    const li = document.createElement("li");
    li.innerHTML = `<span class="k">${key}</span>
      <span class="claim">${claim}</span>
      <span class="bar"><i style="width:${val}%"></i></span>
      <span class="n">${val}</span>`;
    ul.appendChild(li);
  }
}

function safeParse(s) { try { return JSON.parse(s) || {}; } catch { return {}; } }

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function loadState() {
  const r = await fetch("/api/state");
  const d = await r.json();
  jobs = d.jobs;
  scoringOn = d.scoring !== false;
  fillCompanies();
  renderGrid();
  renderStats(d.stats);
  renderTops();
  renderChecks(jobs.find((j) => j.score !== null) || null);
}

async function loadProfile() {
  const d = await fetch("/api/profile").then((r) => r.json());
  if (d.name) {
    $("p-name").textContent = d.name;
    $("who").textContent = d.name.split(" ")[0];
    $("avatar").textContent = d.name.split(" ").map((w) => w[0]).slice(0, 2).join("");
  }
  $("p-headline").textContent = d.headline || "";
  $("p-location").textContent = d.location || "";
  const ul = $("exp");
  ul.textContent = "";

  if (!(d.experience || []).length) {
    ul.innerHTML = `<li class="muted">${escapeHtml(d.error || "No resume parsed")}</li>`;
    return;
  }
  for (const e of d.experience) {
    const li = document.createElement("li");
    li.innerHTML = `<div><div class="org">${escapeHtml(e.org)}</div>
                    <div class="role">${escapeHtml(e.role)}</div></div>
                    <div class="yr">${escapeHtml(e.years)}</div>`;
    ul.appendChild(li);
  }
}

// --- SSE Live Scan ---
let lit = [];
function clearLit() {
  for (const el of lit) el.classList.remove("active");
  lit = [];
}

function highlightCompany(company) {
  clearLit();
  let first = null;
  for (const j of jobs) {
    if (j.company !== company) continue;
    const el = tiles.get(j.id);
    if (!el) continue;
    el.classList.add("active");
    lit.push(el);
    if (!first) first = el;
    if (lit.length >= 40) break;
  }
  if (first) first.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function startScan() {
  const btn = $("scan");
  btn.disabled = true; btn.textContent = "Scanning…";
  t0 = Date.now();
  timer = setInterval(() => {
    $("s-time").textContent = ((Date.now() - t0) / 1000).toFixed(1);
  }, 100);

  const es = new EventSource("/api/scan?limit=3000");

  es.onmessage = (ev) => {
    const d = JSON.parse(ev.data);
    if (d.type === "fetch") {
      $("lk-company").textContent = d.company;
      $("lk-title").textContent = d.error ? "Fetch failed" : `${d.count} open`;
      $("lk-score").textContent = "";
      highlightCompany(d.company);
    } else if (d.type === "fetched") {
      loadState();
      $("gridnote").textContent = `${d.new} new · ${d.closed} closed · ${d.total} active`;
    } else if (d.type === "scoring") {
      $("gridnote").textContent = `Scoring ${d.count} of ${d.backlog} unscored`;
    } else if (d.type === "looking") {
      clearLit();
      const active = tiles.get(d.id);
      if (active) {
        active.classList.add("active");
        lit.push(active);
        active.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
      $("lk-company").textContent = d.company;
      $("lk-title").textContent = d.title;
      $("lk-score").textContent = "…";
    } else if (d.type === "scored") {
      const el = tiles.get(d.id);
      if (el) {
        el.className = "tile " + bucket(d.score);
        el.title = `${d.title} — ${d.company} · ${d.score}/10 — ${d.reason || ""}`;
      }
      const j = jobs.find((x) => x.id === d.id);
      if (j) {
        j.score = d.score; j.reason = d.reason; j.breakdown = d.breakdown || {};
        inspectJob(j);
      }
      renderTops();
    } else if (d.type === "throttled") {
      $("gridnote").textContent = `Rate limited: ${d.message}`;
    } else if (d.type === "error") {
      $("gridnote").textContent = `Error: ${d.message}`;
    } else if (d.type === "done") {
      loadState().then(showMatchMade);
      $("s-time").textContent = d.elapsed.toFixed(1);
      clearLit();
      es.close(); clearInterval(timer);
      btn.disabled = false; btn.textContent = "⚡ Run Scan";
    }
  };

  es.onerror = () => {
    clearLit();
    es.close(); clearInterval(timer);
    btn.disabled = false; btn.textContent = "⚡ Run Scan";
  };
}

function showMatchMade() {
  const scored = jobs.filter((j) => j.score !== null && j.score !== undefined);
  if (!scored.length) return;
  scored.sort((a, b) => b.score - a.score);
  const top = scored.slice(0, 5);

  const name = $("p-name").textContent;
  const initials = $("avatar").textContent;
  const cards = top.map((j) => `
    <a class="mm-card" href="${escapeHtml(j.url || "#")}" target="_blank" rel="noopener"
       title="${escapeHtml(j.title)} — ${escapeHtml(j.reason || "")}">
      <div class="mm-pct">${j.score * 10}%</div>
      <div class="mm-co">${escapeHtml(j.company)}</div>
    </a>`).join("");

  const ov = document.createElement("div");
  ov.className = "overlay";
  ov.innerHTML = `
    <div class="mm">
      <div class="kicker">Match Made</div>
      <h2 class="mm-head">Top Recommendations for ${escapeHtml(name)}</h2>
      <div class="mm-cards">${cards}</div>
      <button class="mm-close">Back to Grid</button>
    </div>`;
  document.body.appendChild(ov);
  requestAnimationFrame(() => ov.classList.add("show"));

  const close = () => ov.remove();
  ov.querySelector(".mm-close").onclick = close;
  ov.onclick = (e) => { if (e.target === ov) close(); };
  document.addEventListener("keydown", function esc(e) {
    if (e.key === "Escape") { close(); document.removeEventListener("keydown", esc); }
  });
}

// ==============================================================================
// Toast Notifications
// ==============================================================================
let toastTimer = null;
function showToast(message, type = "success") {
  const el = $("toast");
  if (!el) return;
  clearTimeout(toastTimer);
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${type === "success" ? "✅" : "⚠️"}</span> <span>${escapeHtml(message)}</span>`;
  el.style.display = "flex";
  toastTimer = setTimeout(() => {
    el.style.display = "none";
  }, 4000);
}

// ==============================================================================
// Resume Upload & Drag-and-Drop
// ==============================================================================
const fileInput = $("resume-file-input");
const dropzone = $("resume-dropzone");

async function uploadResumeFile(file) {
  if (!file) return;
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (![".pdf", ".txt", ".md", ".docx", ".rtf"].includes(ext)) {
    showToast(`Unsupported file type: ${ext}. Please upload a PDF or TXT file.`, "error");
    return;
  }

  const uploadBtn = $("btn-upload-resume");
  if (uploadBtn) { uploadBtn.disabled = true; uploadBtn.textContent = "Uploading…"; }
  const modalUploadBtn = $("btn-modal-upload-resume");
  if (modalUploadBtn) { modalUploadBtn.disabled = true; modalUploadBtn.textContent = "Uploading…"; }

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
      showToast(`Resume uploaded & parsed: ${data.filename}`, "success");
      await loadProfile();
    } else {
      showToast(data.error || "Failed to upload resume", "error");
    }
  } catch (err) {
    showToast(`Network error uploading resume: ${err.message}`, "error");
  } finally {
    if (uploadBtn) { uploadBtn.disabled = false; uploadBtn.textContent = "Upload Resume"; }
    if (modalUploadBtn) { modalUploadBtn.disabled = false; modalUploadBtn.textContent = "Upload New Resume"; }
    if (fileInput) fileInput.value = "";
  }
}

if ($("btn-upload-resume")) {
  $("btn-upload-resume").onclick = () => fileInput && fileInput.click();
}
if ($("btn-modal-upload-resume")) {
  $("btn-modal-upload-resume").onclick = () => fileInput && fileInput.click();
}
if (fileInput) {
  fileInput.onchange = (e) => {
    if (e.target.files && e.target.files[0]) {
      uploadResumeFile(e.target.files[0]);
    }
  };
}

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

// ==============================================================================
// Admin Settings Modal Logic
// ==============================================================================
const modal = $("settings-modal");
const settingsBtn = $("btn-settings");
const settingsCloseBtn = $("settings-close");
const settingsCancelBtn = $("btn-settings-cancel");
const settingsSaveBtn = $("btn-settings-save");
const testTgBtn = $("btn-test-telegram");
const testTgResult = $("telegram-test-result");

function openSettingsModal() {
  if (!modal) return;
  modal.style.display = "flex";
  loadSettings();
}

function closeSettingsModal() {
  if (!modal) return;
  modal.style.display = "none";
  if (testTgResult) {
    testTgResult.style.display = "none";
    testTgResult.textContent = "";
  }
}

async function loadSettings() {
  try {
    const res = await fetch("/api/settings");
    const d = await res.json();

    // Telegram
    if ($("cfg-bot-token")) $("cfg-bot-token").value = d.telegram.bot_token || "";
    if ($("cfg-chat-ids")) $("cfg-chat-ids").value = d.telegram.chat_ids_raw || (d.telegram.chat_ids || []).join(", ");

    // LLM
    if ($("cfg-llm-provider")) $("cfg-llm-provider").value = d.llm.provider || "xkiro";
    if ($("cfg-llm-model")) $("cfg-llm-model").value = d.llm.model || "";
    if ($("cfg-min-score")) $("cfg-min-score").value = d.llm.min_score !== undefined ? d.llm.min_score : 6;
    if ($("cfg-llm-triage")) $("cfg-llm-triage").checked = !!d.llm.triage;

    // API Keys
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
  if (!settingsSaveBtn) return;
  settingsSaveBtn.disabled = true;
  settingsSaveBtn.textContent = "Saving…";

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
      showToast("Settings and API keys saved successfully!", "success");
      closeSettingsModal();
      loadState();
    } else {
      showToast(d.message || "Failed to save settings", "error");
    }
  } catch (err) {
    showToast(`Error saving settings: ${err.message}`, "error");
  } finally {
    settingsSaveBtn.disabled = false;
    settingsSaveBtn.textContent = "Save Settings";
  }
}

async function testTelegramConnection() {
  if (!testTgBtn) return;
  testTgBtn.disabled = true;
  testTgBtn.textContent = "Sending Ping…";
  testTgResult.style.display = "block";
  testTgResult.className = "test-result";
  testTgResult.textContent = "Connecting to Telegram Bot API…";

  const bot_token = $("cfg-bot-token") ? $("cfg-bot-token").value.trim() : "";
  const chat_ids = $("cfg-chat-ids") ? $("cfg-chat-ids").value.trim() : "";

  try {
    const res = await fetch("/api/test-telegram", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bot_token, chat_ids }),
    });
    const d = await res.json();
    if (d.ok) {
      testTgResult.className = "test-result success";
      testTgResult.textContent = d.message;
    } else {
      testTgResult.className = "test-result error";
      testTgResult.textContent = d.message;
    }
  } catch (err) {
    testTgResult.className = "test-result error";
    testTgResult.textContent = `Request failed: ${err.message}`;
  } finally {
    testTgBtn.disabled = false;
    testTgBtn.textContent = "🔔 Send Test Ping";
  }
}

// Tabs in Settings Modal
document.querySelectorAll(".modal-tab").forEach((tab) => {
  tab.onclick = () => {
    document.querySelectorAll(".modal-tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    const target = $(tab.dataset.tab);
    if (target) target.classList.add("active");
  };
});

// Toggle password visibility
document.querySelectorAll(".btn-toggle-vis").forEach((btn) => {
  btn.onclick = () => {
    const targetId = btn.dataset.for;
    const input = $(targetId);
    if (input) {
      if (input.type === "password") {
        input.type = "text";
        btn.textContent = "🙈";
      } else {
        input.type = "password";
        btn.textContent = "👁️";
      }
    }
  };
});

if (settingsBtn) settingsBtn.onclick = openSettingsModal;
if (settingsCloseBtn) settingsCloseBtn.onclick = closeSettingsModal;
if (settingsCancelBtn) settingsCancelBtn.onclick = closeSettingsModal;
if (settingsSaveBtn) settingsSaveBtn.onclick = saveSettings;
if (testTgBtn) testTgBtn.onclick = testTelegramConnection;

if (modal) {
  modal.onclick = (e) => {
    if (e.target === modal) closeSettingsModal();
  };
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && modal && modal.style.display !== "none") {
    closeSettingsModal();
  }
});

$("scan").onclick = startScan;
$("q").addEventListener("input", onFilterChange);
$("minscore").addEventListener("change", renderGrid);
$("co").addEventListener("change", renderGrid);
$("newonly").addEventListener("change", renderGrid);
$("q").addEventListener("keydown", (e) => {
  if (e.key === "Escape") { $("q").value = ""; searchIds = null; renderGrid(); }
});

// Initial load
loadProfile();
loadState();
// Populate initial resume filename on badge
fetch("/api/settings").then(r => r.json()).then(d => {
  if (d && d.resume_path && $("resume-filename")) {
    $("resume-filename").textContent = d.resume_path;
  }
}).catch(() => {});

