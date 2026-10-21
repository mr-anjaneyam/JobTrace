"""Unified scan and scoring orchestration pipeline for JobTrace.

Ensures the CLI, automated scheduler, and Web UI SSE engine run the EXACT same
pipeline with full budget enforcement, heuristic gates, and presence diffing.
"""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from . import sources
from .budget import Budget
from .cursor import CursorError
from .llm import RateLimited, make_scorer
from .localmatch import LocalScorer
from .relevance import apply_cap as apply_relevance_cap, apply_location_cap
from .resume import build_profile, extract_text
from .seniority import apply_cap as apply_seniority_cap
from .store import Store

PROFILE_CACHE_NAME = ".resume_profile.json"


def passes_filters(job: dict, filters_cfg: dict) -> bool:
    title = (job.get("title") or "").lower()
    where = (job.get("location") or "").lower()

    inc = [s.lower().strip() for s in (filters_cfg.get("title_include") or []) if s.strip()]
    exc = [s.lower().strip() for s in (filters_cfg.get("title_exclude") or []) if s.strip()]
    locs = [s.lower().strip() for s in (filters_cfg.get("locations") or []) if s.strip()]

    if inc and not any(s in title for s in inc):
        return False
    if any(s in title for s in exc):
        return False
    if locs and not any(s in where for s in locs):
        return False
    return True


def get_cached_profile(cfg: dict, scorer: Any, root_dir: Path, force: bool = False) -> str:
    resume_path_str = cfg.get("resume_path", "resume.pdf")
    resume_path = root_dir / resume_path_str if not Path(resume_path_str).is_absolute() else Path(resume_path_str)
    stamp = resume_path.stat().st_mtime if resume_path.exists() else 0
    cache_path = root_dir / PROFILE_CACHE_NAME

    has_summarizer = scorer is not None and hasattr(scorer, "complete")
    kind = "model" if has_summarizer else "raw"

    if cache_path.exists() and not force:
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("mtime") == stamp and cached.get("kind") == kind:
                return cached.get("profile", "")
        except Exception:
            pass

    text = extract_text(resume_path)
    try:
        profile = build_profile(text, scorer if has_summarizer else None)
    except Exception:
        profile = build_profile(text, None)

    try:
        cache_path.write_text(
            json.dumps({"mtime": stamp, "kind": kind, "profile": profile}),
            encoding="utf-8",
        )
    except Exception:
        pass
    return profile


def run_pipeline(
    cfg: dict,
    store: Store,
    root_dir: Path,
    quiet: bool = False,
    emit: Callable[[str, dict], None] | None = None,
    cancel_event: threading.Event | None = None,
    max_to_score: int | None = None,
) -> dict:
    """Execute complete ingestion, diffing, triage, and scoring pipeline."""
    started_at = time.time()
    errors: list[str] = []
    new_jobs: list[dict] = []
    closed_count = 0
    scored_count = 0

    def dispatch(kind: str, **kwargs):
        if emit:
            emit(kind, kwargs)

    # -----------------------------------------------------------------------
    # Step 1: Ingestion
    # -----------------------------------------------------------------------
    companies = cfg.get("companies") or []
    all_jobs: list[dict] = []
    healthy_companies: list[str] = []

    # Fetch companies concurrently with real-time SSE progress streaming
    workers = min(8, max(1, len(companies)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(sources.fetch_company, entry): entry for entry in companies}
        for fut in as_completed(future_map):
            if cancel_event and cancel_event.is_set():
                return {"cancelled": True}
            entry = future_map[fut]
            try:
                jobs, err = fut.result()
            except Exception as e:
                jobs, err = [], str(e)
            if err:
                errors.append(f"{entry['name']}: {err}")
            else:
                healthy_companies.append(entry["name"])
                all_jobs.extend(jobs)
            dispatch("fetch", company=entry["name"], count=len(jobs), error=err or "")
            if not quiet:
                flag = f"  ⚠ {err}" if err else ""
                print(f"  {entry['name']:<24} {len(jobs):>4} open{flag}", flush=True)

    # Aggregators / discovery
    disc_cfg = cfg.get("discovery") or {}
    if disc_cfg.get("enabled"):
        if cancel_event and cancel_event.is_set():
            return {"cancelled": True}
        disc_jobs, disc_errs = sources.discover(
            disc_cfg.get("queries") or [],
            disc_cfg.get("max_per_query", 40),
        )
        all_jobs.extend(disc_jobs)
        errors.extend(disc_errs)
        dispatch("fetch", company="discovery", count=len(disc_jobs), error="")
        if not quiet:
            print(f"  {'discovery':<24} {len(disc_jobs):>4} found", flush=True)

    # -----------------------------------------------------------------------
    # Step 2: Diffing & Presence Tracking (Bug #4 Fix)
    # -----------------------------------------------------------------------
    filters_cfg = cfg.get("filters") or {}
    # Mark filter matches on ALL fetched jobs so presence is preserved
    for j in all_jobs:
        j["matches_filter"] = passes_filters(j, filters_cfg)

    # Upsert all jobs; store will index and return those that are new & match filter
    run_timestamp = time.time()
    new_jobs = store.upsert(all_jobs, run_ts=run_timestamp)
    closed = store.mark_closed(healthy_companies, run_ts=run_timestamp)
    closed_count = len(closed)

    # Age-expire aggregators
    stale_days = int(disc_cfg.get("expire_after_days", 14))
    stale = store.close_stale(["remotive", "arbeitnow"], stale_days)
    closed_count += len(stale)

    matching_open = [j for j in all_jobs if j.get("matches_filter")]
    desc_map = {j["id"]: j.get("description", "") for j in matching_open}
    dispatch("fetched", new=len(new_jobs), closed=closed_count, total=len(matching_open))

    # -----------------------------------------------------------------------
    # Step 3: Scoring Pipeline
    # -----------------------------------------------------------------------
    llm_cfg = cfg.get("llm") or {}
    provider = llm_cfg.get("provider", "none")
    candidate_cfg = cfg.get("candidate") or {}
    target_seniority = candidate_cfg.get("seniority", "junior")
    target_locations = candidate_cfg.get("locations") or filters_cfg.get("locations") or []

    if provider not in ("none", "off", None, ""):
        score_limit = max_to_score or int(llm_cfg.get("max_to_score", 5000))
        pending_rows = store.unscored(score_limit)
        dispatch("scoring", count=len(pending_rows), backlog=store.unscored_count())

        if pending_rows:
            # Prepare scorer & resume profile
            resume_path_str = cfg.get("resume_path", "resume.pdf")
            resume_file = root_dir / resume_path_str if not Path(resume_path_str).is_absolute() else Path(resume_path_str)
            resume_text = extract_text(resume_file) if resume_file.exists() else ""

            scorer = make_scorer(
                provider=provider,
                model=llm_cfg.get("model", ""),
                params=llm_cfg.get("model_params"),
                resume_text=resume_text,
                target_locations=target_locations,
                target_seniority=target_seniority,
            )
            profile = get_cached_profile(cfg, scorer, root_dir)

            # Enrich Workday descriptions for pending jobs missing text
            workday_short = [
                r for r in pending_rows
                if (r["source"] == "workday" or "myworkdayjobs.com" in (r["url"] or ""))
                and len(desc_map.get(r["id"]) or r["description"] or "") < 50
            ]
            if workday_short:
                def _fetch_wd(r):
                    u = r["url"] or ""
                    if u:
                        d = sources.fetch_workday_description_by_url(u)
                        if d:
                            return r["id"], d
                    return r["id"], None

                with ThreadPoolExecutor(max_workers=min(8, len(workday_short))) as wd_pool:
                    for jid, full_d in wd_pool.map(_fetch_wd, workday_short):
                        if full_d:
                            desc_map[jid] = full_d
                            store.update_description(jid, full_d)

            # Stage 3A: Local Triage
            rows_to_score = []
            floor = int(llm_cfg.get("triage_floor", 3))
            use_triage = llm_cfg.get("triage", False) and not isinstance(scorer, LocalScorer)

            if use_triage:
                local_scorer = LocalScorer(
                    resume_text=resume_text,
                    target_locations=target_locations,
                    target_seniority=target_seniority,
                )
                settled_count = 0
                for row in pending_rows:
                    job_dict = dict(row)
                    job_dict["description"] = desc_map.get(row["id"]) or row["description"] or ""
                    # If description is too short, let the model read it
                    if len(job_dict["description"]) < 120:
                        rows_to_score.append(row)
                        continue

                    s_local, why, bd = local_scorer.score(profile, job_dict)
                    if s_local >= floor:
                        rows_to_score.append(row)
                    else:
                        store.save_score(row["id"], s_local, f"triage: {why}", bd)
                        settled_count += 1
                if not quiet and settled_count:
                    print(f"  triage: settled {settled_count} locally, {len(rows_to_score)} to model", flush=True)
            else:
                rows_to_score = list(pending_rows)

            # Stage 3B: Budget Ceiling
            budget = Budget(store.db, daily_limit=int(llm_cfg.get("daily_token_limit", 500_000)))
            batch_size = int(llm_cfg.get("batch_size", 25))
            per_batch = int(llm_cfg.get("tokens_per_batch", 3400))
            affordable = max(0, budget.remaining() // per_batch) * batch_size

            if len(rows_to_score) > affordable:
                if not quiet:
                    print(f"  budget: {budget.report()} -> capping at {affordable} jobs", flush=True)
                rows_to_score = rows_to_score[:affordable]
            elif not quiet:
                print(f"  budget: {budget.report()}", flush=True)

            titles_map = {r["id"]: r["title"] for r in pending_rows}
            locations_map = {r["id"]: r["location"] or "" for r in pending_rows}

            candidate_years = None
            if (root_dir / ".resume_details.json").exists():
                try:
                    c_det = json.loads((root_dir / ".resume_details.json").read_text(encoding="utf-8"))
                    candidate_years = c_det.get("years_of_experience")
                except Exception:
                    pass

            # Helper: Apply gates and save score
            def apply_and_persist(job_id: str, res: tuple[int, str, dict]):
                nonlocal scored_count
                score, reason, breakdown = res
                job_desc = desc_map.get(job_id) or ""
                # Algorithmic gates applied in code
                score, reason = apply_seniority_cap(
                    score,
                    titles_map.get(job_id, ""),
                    reason,
                    target_seniority=target_seniority,
                    description=job_desc,
                    candidate_years=candidate_years,
                    breakdown=breakdown,
                )
                score, reason = apply_location_cap(
                    score,
                    locations_map.get(job_id, ""),
                    target_locations=target_locations,
                    breakdown=breakdown,
                    reason=reason,
                )
                score, reason = apply_relevance_cap(score, breakdown, reason)
                store.save_score(job_id, score, reason, breakdown)
                scored_count += 1
                return score, reason, breakdown

            # Stage 3C: Scoring Loop
            try:
                if hasattr(scorer, "score_batch"):
                    spent_before = getattr(scorer, "tokens_used", 0)
                    for start in range(0, len(rows_to_score), batch_size):
                        if cancel_event and cancel_event.is_set():
                            return {"cancelled": True}
                        if not budget.can_afford(per_batch):
                            dispatch("throttled", message="Daily token budget reached", scored=scored_count)
                            break

                        chunk = rows_to_score[start : start + batch_size]
                        payload = []
                        for r in chunk:
                            jd = dict(r)
                            jd["description"] = desc_map.get(r["id"]) or r["description"] or ""
                            payload.append(jd)

                        dispatch(
                            "looking",
                            id=chunk[0]["id"],
                            company=chunk[0]["company"],
                            title=f"scoring batch of {len(chunk)}" if len(chunk) > 1 else chunk[0]["title"],
                            domain=chunk[0]["domain"] or "",
                        )

                        try:
                            results = scorer.score_batch(profile, payload)
                        except (RateLimited, CursorError) as e:
                            dispatch("throttled", message=str(e), scored=scored_count)
                            errors.append(f"Scorer rate-limited: {e}")
                            break
                        finally:
                            now_used = getattr(scorer, "tokens_used", 0)
                            if now_used > spent_before:
                                budget.record(now_used - spent_before)
                                spent_before = now_used

                        for row in chunk:
                            got = results.get(row["id"])
                            if got is not None:
                                sc, rsn, bd = apply_and_persist(row["id"], got)
                                dispatch(
                                    "scored",
                                    id=row["id"],
                                    score=sc,
                                    reason=rsn,
                                    breakdown=bd,
                                    company=row["company"],
                                    title=row["title"],
                                    domain=row["domain"] or "",
                                    url=row["url"] or "",
                                )

                else:
                    # Non-batched scorer (single-job scorer with runtime budget checks)
                    workers = int(llm_cfg.get("concurrency", 3))

                    def work(row):
                        if cancel_event and cancel_event.is_set():
                            return row["id"], None
                        jd = dict(row)
                        jd["description"] = desc_map.get(row["id"]) or row["description"] or ""
                        dispatch(
                            "looking",
                            id=row["id"],
                            company=row["company"],
                            title=row["title"],
                            domain=row["domain"] or "",
                        )
                        res = scorer.score(profile, jd)
                        return row["id"], res

                    with ThreadPoolExecutor(max_workers=workers) as pool:
                        for jid, res in pool.map(work, rows_to_score):
                            if cancel_event and cancel_event.is_set():
                                return {"cancelled": True}
                            if res is not None:
                                sc, rsn, bd = apply_and_persist(jid, res)
                                # Record tokens for non-batched if available
                                if hasattr(scorer, "input_tokens"):
                                    budget.record(getattr(scorer, "input_tokens", 0))
                                dispatch("scored", id=jid, score=sc, reason=rsn, breakdown=bd)

            except Exception as e:
                errors.append(f"Scoring error: {type(e).__name__}: {e}")

    store.log_run(len(new_jobs), closed_count, errors)
    elapsed = round(time.time() - started_at, 1)
    dispatch("done", scored=scored_count, elapsed=elapsed)

    if not quiet:
        print(
            f"\n{len(new_jobs)} new · {closed_count} closed · {scored_count} scored · {len(errors)} errors ({elapsed}s)",
            flush=True,
        )

    return {
        "new": len(new_jobs),
        "closed": closed_count,
        "scored": scored_count,
        "errors": errors,
        "elapsed": elapsed,
    }
