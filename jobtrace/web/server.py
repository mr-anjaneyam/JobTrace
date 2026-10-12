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
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .. import telegram
from ..main import ROOT, load_config, load_dotenv
from ..pipeline import run_pipeline
from ..resume import build_details, extract_text, parse_details
from ..store import Store

load_dotenv()

STATIC_DIR = Path(__file__).parent / "static"
app = FastAPI(title="JobTrace")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_scan_lock = threading.Lock()
_scan_state = {"scanning": False, "started": 0.0}


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
            if k in updates:
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


def get_store() -> Store:
    return Store(ROOT / "jobtrace.db")


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/settings")
def get_settings():
    c = get_cfg()
    bot_token = telegram.get_bot_token(c)
    chat_ids = telegram.get_chat_ids(c)
    llm_cfg = c.get("llm") or {}
    cand_cfg = c.get("candidate") or {}

    return {
        "telegram": {
            "bot_token": bot_token,
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
        "api_keys": {
            "XKIRO_API_KEY": os.environ.get("XKIRO_API_KEY", ""),
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
            "OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY", ""),
            "CURSOR_API_KEY": os.environ.get("CURSOR_API_KEY", ""),
            "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
            "TYPESAFE_API_KEY": os.environ.get("TYPESAFE_API_KEY", ""),
        },
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
                env_updates[k_clean] = v_clean

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
    chat_ids = data.get("chat_ids")
    ok, msg = telegram.test_telegram(c, bot_token=token, chat_ids=chat_ids)
    return {"ok": ok, "message": msg}


@app.post("/api/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    if not file.filename:
        return {"ok": False, "error": "No file selected."}

    ext = Path(file.filename).suffix.lower()
    if ext not in (".pdf", ".txt", ".md", ".docx", ".rtf"):
        return {"ok": False, "error": f"Unsupported file type '{ext}'. Please upload PDF, TXT, or MD."}

    # Clean filename and save in workspace root
    safe_filename = Path(file.filename).name
    dest_path = ROOT / safe_filename

    content = await file.read()
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

        if details.get("name"):
            (ROOT / ".resume_details.json").write_text(json.dumps(details), encoding="utf-8")

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
            details["error"] = f"Model refinement failed: {e}"[:150]

    if details.get("name"):
        try:
            cache_path.write_text(json.dumps(details), encoding="utf-8")
        except Exception:
            pass

    return details


@app.get("/api/state")
def state():
    c, s = get_cfg(), get_store()
    rows = s.db.execute(
        """SELECT id, company, title, url, location, score, reason, domain, source,
                  breakdown, first_seen, closed_at
           FROM jobs
           WHERE closed_at IS NULL AND matches_filter = 1
           ORDER BY score DESC NULLS LAST, company, title"""
    ).fetchall()

    jobs_list = [dict(r) for r in rows]
    mosaic_jobs = _mosaic(jobs_list, limit=4000)
    scored = [j for j in mosaic_jobs if j.get("score") is not None]
    threshold = int(c.get("llm", {}).get("min_score", 6))

    avg_score = round(sum(j["score"] for j in scored) / len(scored) / 10, 2) if scored else 0.0

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
