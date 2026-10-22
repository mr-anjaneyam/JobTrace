"""FastAPI web server for JobTrace with FTS5 search and live SSE streaming."""
from __future__ import annotations

import json
import os
import queue
import re
import threading
import time
from collections import OrderedDict, deque
from pathlib import Path

import yaml
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .. import sources, telegram
from ..main import ROOT, load_config, load_dotenv
from ..pipeline import run_pipeline
from ..resume import build_details, extract_text, parse_details
from ..store import Store

load_dotenv()

FRONTEND_DIR = ROOT / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"
app = FastAPI(title="JobTrace API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

API_KEY_NAMES = (
    "XKIRO_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "CURSOR_API_KEY",
    "ANTHROPIC_API_KEY",
    "TYPESAFE_API_KEY",
)
MASK_CHAR = "\u2022"
MAX_RESUME_BYTES = 5 * 1024 * 1024
RESUME_EXTENSIONS = (".pdf", ".txt", ".md", ".docx")


def mask_secret(value: str) -> str:
    """Hide a secret, keeping only its last 4 characters for recognition."""
    if not value:
        return ""
    tail = value[-4:] if len(value) > 8 else ""
    return MASK_CHAR * 8 + tail


def is_masked(value: str) -> bool:
    return MASK_CHAR in value

if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

_scan_lock = threading.Lock()
_scan_state = {"scanning": False, "started": 0.0}

_liveness_lock = threading.Lock()
_liveness_state = {"checking": False, "last_check": 0.0}


def _trigger_background_liveness_check() -> None:
    now = time.time()
    # Throttle automatic background check to run at most once every 60 seconds
    if now - _liveness_state["last_check"] < 60:
        return
    if not _liveness_lock.acquire(blocking=False):
        return

    def _worker():
        try:
            _liveness_state["checking"] = True
            _liveness_state["last_check"] = time.time()
            thread_store = get_store()
            from ..verifier import verify_and_discard_jobs
            res = verify_and_discard_jobs(thread_store, limit=120)
            if res.get("closed_count", 0) > 0:
                print(f"[Liveness] Discarded {res['closed_count']} archived/closed jobs on UI load.")
        except Exception as e:
            print(f"[Liveness] Error during background check: {e}")
        finally:
            _liveness_state["checking"] = False
            _liveness_lock.release()

    threading.Thread(target=_worker, daemon=True).start()


def get_cfg() -> dict:
    return load_config(ROOT / "config.yaml")


def save_config(cfg: dict) -> None:
    (ROOT / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")


def update_env_file(updates: dict[str, str]) -> None:
    """Safely update or insert environment variables in .env and live os.environ."""
    env_file = ROOT / ".env"
    existing_lines: list[str] = []
    if env_file.exists():
        existing_lines = env_file.read_text(encoding="utf-8").splitlines()

    updated_keys = set()
    new_lines = []
    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _ = stripped.split("=", 1)
            k = k.strip()
            if k in updates:  # values are pre-validated by _env_value_ok
                new_val = updates[k]
                new_lines.append(f'{k}="{new_val}"')
                updated_keys.add(k)
                os.environ[k] = new_val
                continue
        new_lines.append(line)

    for k, v in updates.items():
        if k not in updated_keys:
            new_lines.append(f'{k}="{v}"')
            os.environ[k] = v

    env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _env_value_ok(value: str) -> bool:
    return not any(ch in value for ch in '\r\n"\\')


def get_store() -> Store:
    return Store(ROOT / "jobtrace.db")


@app.get("/")
def index():
    if (FRONTEND_DIST / "index.html").exists():
        return FileResponse(str(FRONTEND_DIST / "index.html"))
    p = FRONTEND_DIR / "index.html"
    if p.exists():
        return FileResponse(str(p))
    return {"status": "JobTrace API is live", "docs": "/docs"}


@app.get("/userprofile")
def userprofile_page():
    if (FRONTEND_DIST / "index.html").exists():
        return FileResponse(str(FRONTEND_DIST / "index.html"))
    p = FRONTEND_DIR / "index.html"
    if p.exists():
        return FileResponse(str(p))
    return {"status": "userprofile"}


@app.get("/settings")
def settings_page():
    if (FRONTEND_DIST / "index.html").exists():
        return FileResponse(str(FRONTEND_DIST / "index.html"))
    p = FRONTEND_DIR / "index.html"
    if p.exists():
        return FileResponse(str(p))
    return {"status": "settings"}


@app.get("/api/settings")
def get_settings():
    c = get_cfg()
    bot_token = telegram.get_bot_token(c)
    chat_ids = telegram.get_chat_ids(c)
    llm_cfg = c.get("llm") or {}
    cand_cfg = c.get("candidate") or {}

    return {
        "telegram": {
            "bot_token": mask_secret(bot_token),
            "chat_ids": chat_ids,
            "chat_ids_raw": ", ".join(chat_ids),
        },
        "llm": {
            "provider": llm_cfg.get("provider", "xkiro"),
            "model": llm_cfg.get("model", "mistralai/mistral-large-2512"),
            "min_score": llm_cfg.get("min_score", 6),
            "triage": bool(llm_cfg.get("triage", False)),
        },
        "candidate": {
            "seniority": cand_cfg.get("seniority", "junior"),
            "locations": cand_cfg.get("locations", []),
        },
        "resume_path": c.get("resume_path", "resume.pdf"),
        "api_keys": {name: mask_secret(os.environ.get(name, "")) for name in API_KEY_NAMES},
    }


@app.post("/api/settings")
async def update_settings(request: Request):
    data = await request.json()
    c = get_cfg()
    env_updates: dict[str, str] = {}

    # 1. Telegram
    if "telegram" in data:
        t = data["telegram"]
        bot_token = str(t.get("bot_token", "")).strip()
        if is_masked(bot_token):
            bot_token = telegram.get_bot_token(c)
        raw_chat_ids = t.get("chat_ids")

        parsed_ids: list[str] = []
        if isinstance(raw_chat_ids, list):
            for x in raw_chat_ids:
                s = str(x).strip()
                if s and s not in parsed_ids:
                    parsed_ids.append(s)
        elif isinstance(raw_chat_ids, str):
            for part in re.split(r"[,;\n\s]+", raw_chat_ids):
                s = part.strip()
                if s and s not in parsed_ids:
                    parsed_ids.append(s)

        c.setdefault("telegram", {})
        c["telegram"]["bot_token"] = bot_token
        c["telegram"]["chat_ids"] = parsed_ids
        if "chat_id" in c["telegram"]:
            del c["telegram"]["chat_id"]

        env_updates["TELEGRAM_BOT_TOKEN"] = bot_token
        env_updates["TELEGRAM_CHAT_IDS"] = ", ".join(parsed_ids)
        if parsed_ids:
            env_updates["TELEGRAM_CHAT_ID"] = parsed_ids[0]

    # 2. LLM
    if "llm" in data:
        l = data["llm"]
        c.setdefault("llm", {})
        if "provider" in l:
            c["llm"]["provider"] = str(l["provider"]).strip()
        if "model" in l:
            c["llm"]["model"] = str(l["model"]).strip()
        if "min_score" in l:
            try:
                c["llm"]["min_score"] = int(l["min_score"])
            except (ValueError, TypeError):
                pass
        if "triage" in l:
            c["llm"]["triage"] = bool(l["triage"])

    # 3. Candidate
    if "candidate" in data:
        cand = data["candidate"]
        c.setdefault("candidate", {})
        if "seniority" in cand:
            c["candidate"]["seniority"] = str(cand["seniority"]).strip()
        if "locations" in cand:
            locs = cand["locations"]
            if isinstance(locs, str):
                locs = [x.strip() for x in locs.split(",") if x.strip()]
            c["candidate"]["locations"] = locs

    # 4. API Keys
    if "api_keys" in data:
        keys = data["api_keys"]
        if isinstance(keys, dict):
            for k, v in keys.items():
                k_clean = str(k).strip().upper()
                v_clean = str(v).strip()
                if k_clean in API_KEY_NAMES and not is_masked(v_clean):
                    env_updates[k_clean] = v_clean

    bad = [k for k, v in env_updates.items() if not _env_value_ok(v)]
    if bad:
        return {"ok": False, "message": f"Invalid characters in: {', '.join(bad)}"}

    if env_updates:
        update_env_file(env_updates)
    save_config(c)

    return {"ok": True, "message": "Settings saved successfully."}


@app.post("/api/test-telegram")
async def test_telegram_endpoint(request: Request):
    data = {}
    try:
        data = await request.json()
    except Exception:
        pass
    c = get_cfg()
    token = data.get("bot_token")
    if isinstance(token, str) and is_masked(token):
        token = None
    chat_ids = data.get("chat_ids")
    ok, msg = telegram.test_telegram(c, bot_token=token, chat_ids=chat_ids)
    return {"ok": ok, "message": msg}


@app.post("/api/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    if not file.filename:
        return {"ok": False, "error": "No file selected."}

    ext = Path(file.filename).suffix.lower()
    if ext not in RESUME_EXTENSIONS:
        return {"ok": False, "error": f"Unsupported file type '{ext}'. Please upload PDF, DOCX, TXT, or MD."}

    content = await file.read(MAX_RESUME_BYTES + 1)
    if len(content) > MAX_RESUME_BYTES:
        return {"ok": False, "error": "Resume is larger than 5 MB."}

    # Fixed name so an upload can never overwrite another project file
    safe_filename = f"resume{ext}"
    dest_path = ROOT / safe_filename
    for other_ext in RESUME_EXTENSIONS:
        old = ROOT / f"resume{other_ext}"
        if old != dest_path and old.exists():
            try:
                old.unlink()
            except OSError:
                pass
    dest_path.write_bytes(content)

    # Update config.yaml with the new resume path
    c = get_cfg()
    c["resume_path"] = safe_filename
    save_config(c)

    # Invalidate cache files
    for cache_name in (".resume_details.json", ".resume_profile.json"):
        cache_file = ROOT / cache_name
        if cache_file.exists():
            try:
                cache_file.unlink()
            except Exception:
                pass

    # Extract & parse profile
    try:
        text = extract_text(dest_path)
        details = parse_details(text)
        llm_cfg = c.get("llm") or {}
        provider = llm_cfg.get("provider", "none")

        if provider not in ("none", "off", None, ""):
            from ..llm import make_scorer
            try:
                scorer = make_scorer(provider, llm_cfg.get("model", ""), llm_cfg.get("model_params"))
                better = build_details(text, scorer)
                if better.get("name"):
                    details = better
            except Exception as e:
                details["error"] = f"Model refinement notice: {e}"[:150]

        # Dynamically set candidate seniority and locations from parsed resume
        if details.get("seniority"):
            c.setdefault("candidate", {})["seniority"] = details["seniority"]
        if details.get("target_locations"):
            c.setdefault("candidate", {})["locations"] = details["target_locations"]
        save_config(c)

        if details.get("name"):
            (ROOT / ".resume_details.json").write_text(json.dumps(details, indent=2), encoding="utf-8")

        return {"ok": True, "filename": safe_filename, "profile": details}
    except Exception as e:
        return {"ok": False, "error": f"Resume uploaded but extraction failed: {e}"}


@app.get("/api/profile")
def profile():
    c = get_cfg()
    cache_path = ROOT / ".resume_details.json"
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("name"):
                return cached
        except Exception:
            pass

    resume_path_str = c.get("resume_path", "resume.pdf")
    resume_file = ROOT / resume_path_str if not Path(resume_path_str).is_absolute() else Path(resume_path_str)

    try:
        text = extract_text(resume_file)
    except Exception as e:
        return {
            "name": "", "headline": "", "location": "", "experience": [],
            "error": f"Resume not loaded: {e}"[:180]
        }

    # Offline heuristic parse first
    details = parse_details(text)
    llm_cfg = c.get("llm") or {}
    provider = llm_cfg.get("provider", "none")

    # If LLM configured, attempt refined extraction
    if provider not in ("none", "off", None, ""):
        from ..llm import make_scorer
        try:
            scorer = make_scorer(provider, llm_cfg.get("model", ""), llm_cfg.get("model_params"))
            better = build_details(text, scorer)
            if better.get("name"):
                details = better
        except Exception as e:
            details["error"] = f"Model refinement notice: {e}"[:150]

    # Dynamically sync seniority if not manually overridden
    if details.get("seniority") and not c.get("candidate", {}).get("seniority"):
        c.setdefault("candidate", {})["seniority"] = details["seniority"]
        save_config(c)

    if details.get("name"):
        try:
            cache_path.write_text(json.dumps(details, indent=2), encoding="utf-8")
        except Exception:
            pass

    return details


@app.post("/api/profile")
async def update_profile(request: Request):
    """Endpoint for user to review, edit, and confirm their resume analysis."""
    data = await request.json()
    c = get_cfg()

    # Update candidate config with user-confirmed fields
    c.setdefault("candidate", {})
    if data.get("seniority"):
        c["candidate"]["seniority"] = str(data["seniority"]).strip().lower()
    if "target_locations" in data:
        locs = data["target_locations"]
        if isinstance(locs, str):
            locs = [x.strip() for x in locs.split(",") if x.strip()]
        elif isinstance(locs, list):
            locs = [str(x).strip() for x in locs if str(x).strip()]
        c["candidate"]["locations"] = locs
    save_config(c)

    # Persist confirmed profile details to cache
    cache_path = ROOT / ".resume_details.json"
    try:
        cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"Failed to persist confirmed profile: {e}"}

    return {"ok": True, "message": "Profile confirmed and saved successfully.", "profile": data}


@app.get("/api/state")
def state():
    c, s = get_cfg(), get_store()

    # 1. Instantly discard elapsed/stale aggregator postings at UI open time
    disc_cfg = c.get("discovery") or {}
    expire_days = int(disc_cfg.get("expire_after_days", 14))
    s.close_stale(["remotive", "arbeitnow"], max_age_days=expire_days)

    # 2. Trigger asynchronous background liveness verification
    _trigger_background_liveness_check()

    rows = s.db.execute(
        """SELECT id, company, title, url, location, score, reason, domain, source,
                  breakdown, first_seen, posted_at, substr(description, 1, 350) as description, closed_at
           FROM jobs
           WHERE closed_at IS NULL AND matches_filter = 1
           ORDER BY score DESC NULLS LAST, company, title"""
    ).fetchall()

    jobs_list = [dict(r) for r in rows]
    mosaic_jobs = _mosaic(jobs_list, limit=4000)
    scored = [j for j in mosaic_jobs if j.get("score") is not None]
    threshold = int(c.get("llm", {}).get("min_score", 6))

    avg_score = round(sum(j["score"] for j in scored) / len(scored), 1) if scored else 0.0

    return {
        "jobs": mosaic_jobs,
        "companies": [e["name"] for e in c.get("companies", [])],
        "stats": {
            "checked": len(scored),
            "total": len(mosaic_jobs),
            "closed": s.db.execute("SELECT COUNT(*) FROM jobs WHERE closed_at IS NOT NULL").fetchone()[0],
            "would_apply": len([j for j in scored if j["score"] >= threshold]),
            "avg": avg_score,
            "threshold": threshold,
        },
        "scanning": _scan_state["scanning"],
        "scoring": c.get("llm", {}).get("provider", "none") not in ("none", "off", None, ""),
    }


def _mosaic(jobs: list[dict], limit: int) -> list[dict]:
    """Round-robin deal jobs across companies to create balanced mosaic view."""
    buckets: OrderedDict[str, deque] = OrderedDict()
    sorted_jobs = sorted(jobs, key=lambda x: (x["score"] is None, -(x["score"] or 0)))
    for j in sorted_jobs:
        buckets.setdefault(j["company"], deque()).append(j)

    out: list[dict] = []
    while buckets and len(out) < limit:
        for company in list(buckets):
            if not buckets[company]:
                del buckets[company]
                continue
            out.append(buckets[company].popleft())
            if len(out) >= limit:
                break
    return out


@app.get("/api/search")
def search(q: str = "", limit: int = 4000):
    """Sub-millisecond FTS5 search query."""
    clean_q = q.strip()
    if not clean_q:
        return {"ids": None}

    s = get_store()
    matching_ids = s.search(clean_q, limit=limit)
    return {"ids": matching_ids}


@app.get("/api/jobs/{job_id}")
def get_job_detail(job_id: str):
    """Retrieve full detail and complete description for a single job on-demand."""
    s = get_store()
    row = s.db.execute(
        """SELECT id, company, title, url, location, score, reason, domain, source,
                  breakdown, first_seen, posted_at, description, closed_at
           FROM jobs WHERE id = ?""",
        (job_id,),
    ).fetchone()
    if not row:
        return {"error": "Job not found"}
    data = dict(row)
    # If description is just a short snippet/req-id and it's from Workday, fetch full description
    if (data.get("source") == "workday" or "myworkdayjobs.com" in (data.get("url") or "")) and len(data.get("description") or "") < 50:
        full_d = sources.fetch_workday_description_by_url(data.get("url") or "")
        if full_d:
            data["description"] = full_d
            s.update_description(job_id, full_d)
    return data


@app.get("/api/jobs/{job_id}/verify")
def verify_job_endpoint(job_id: str):
    """Verify live HTTP availability and archival status for a specific job."""
    s = get_store()
    row = s.db.execute(
        "SELECT id, company, title, url, closed_at, reason FROM jobs WHERE id = ?",
        (job_id,),
    ).fetchone()
    if not row:
        return {"ok": False, "error": "Job not found"}

    if row["closed_at"]:
        return {
            "ok": True,
            "active": False,
            "reason": row["reason"] or "Closed",
            "url": row["url"],
        }

    from ..verifier import check_url_liveness
    is_active, reason = check_url_liveness(row["url"] or "")
    if not is_active:
        s.mark_job_closed(job_id, reason=reason)
    return {"ok": True, "active": is_active, "reason": reason, "url": row["url"]}


@app.post("/api/jobs/{job_id}/discard")
def discard_job_endpoint(job_id: str):
    """Discard a single job immediately from the active matrix and mark as closed."""
    s = get_store()
    row = s.db.execute("SELECT id, company, title FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        return {"ok": False, "error": "Job not found"}
    s.mark_job_closed(job_id, reason="Discarded by user")
    return {"ok": True, "job_id": job_id, "message": "Job discarded successfully."}


@app.post("/api/jobs/discard-closed")
def discard_closed_endpoint():
    """Trigger on-demand sweep to discard elapsed postings and archived URLs."""
    c, s = get_cfg(), get_store()
    disc_cfg = c.get("discovery") or {}
    expire_days = int(disc_cfg.get("expire_after_days", 14))
    elapsed = s.close_stale(["remotive", "arbeitnow"], max_age_days=expire_days)

    from ..verifier import verify_and_discard_jobs
    res = verify_and_discard_jobs(s, limit=120)
    total_closed = len(elapsed) + res.get("closed_count", 0)
    return {
        "ok": True,
        "total_closed": total_closed,
        "elapsed_count": len(elapsed),
        "archived_count": res.get("closed_count", 0),
        "closed": res.get("closed", []),
    }



def _scan_stream_generator(limit: int):
    c = get_cfg()
    ev_queue: queue.Queue = queue.Queue()
    cancel_event = threading.Event()

    def event_emitter(kind: str, data: dict):
        ev_queue.put(f"data: {json.dumps({'type': kind, **data})}\n\n")

    def worker():
        store_inst = get_store()
        try:
            run_pipeline(
                cfg=c,
                store=store_inst,
                root_dir=ROOT,
                quiet=True,
                emit=event_emitter,
                cancel_event=cancel_event,
                max_to_score=limit,
            )
        except Exception as e:
            ev_queue.put(f"data: {json.dumps({'type': 'error', 'message': str(e)[:250]})}\n\n")
        finally:
            with _scan_lock:
                _scan_state["scanning"] = False
            ev_queue.put(None)

    with _scan_lock:
        if _scan_state["scanning"]:
            yield f"data: {json.dumps({'type': 'error', 'message': 'A scan is already in progress'})}\n\n"
            return
        _scan_state["scanning"] = True
        _scan_state["started"] = time.time()

    worker_thread = threading.Thread(target=worker, daemon=True)
    worker_thread.start()

    try:
        while True:
            msg = ev_queue.get()
            if msg is None:
                break
            yield msg
    finally:
        # Graceful worker cancellation if browser closes SSE stream
        cancel_event.set()
        with _scan_lock:
            _scan_state["scanning"] = False


@app.get("/api/scan")
def scan(limit: int = 3000):
    return StreamingResponse(
        _scan_stream_generator(limit),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
