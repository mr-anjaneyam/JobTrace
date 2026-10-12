"""FastAPI web server for JobTrace with FTS5 search and live SSE streaming."""
from __future__ import annotations

import json
import queue
import threading
import time
from collections import OrderedDict, deque
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

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


def get_store() -> Store:
    return Store(ROOT / "jobtrace.db")


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


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
