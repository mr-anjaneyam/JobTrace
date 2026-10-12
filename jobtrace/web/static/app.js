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

$("scan").onclick = startScan;
$("q").addEventListener("input", onFilterChange);
$("minscore").addEventListener("change", renderGrid);
$("co").addEventListener("change", renderGrid);
$("newonly").addEventListener("change", renderGrid);
$("q").addEventListener("keydown", (e) => {
  if (e.key === "Escape") { $("q").value = ""; searchIds = null; renderGrid(); }
});

loadProfile();
loadState();
