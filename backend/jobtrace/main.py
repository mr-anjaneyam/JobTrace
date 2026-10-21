"""JobTrace CLI and pipeline commands.

Commands:
  scan     crawl configured sources, diff against DB, score matching roles
  alert    check watched companies shortlist and send Telegram alert
  digest   send weekly ranked digest of new matches to Telegram
  run      scan + digest in one execution
  recap    re-apply seniority and relevance caps to existing scores (0 tokens)
  list     display recent finds in terminal
  test     verify Telegram Bot token and chat connection
  web      start local web dashboard (http://localhost:8765)
  daemon   run cross-platform background scheduler
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import json

import yaml

from . import telegram
from .pipeline import run_pipeline
from .relevance import apply_cap as apply_relevance_cap, apply_location_cap
from .seniority import apply_cap as apply_seniority_cap
from .store import Store

ROOT = Path(__file__).resolve().parent.parent
if ROOT.name == "backend" and (ROOT.parent / "config.yaml").exists():
    ROOT = ROOT.parent


def load_dotenv(env_path: Path | None = None) -> None:
    """Load key-value pairs from .env into os.environ if not already set."""
    path = env_path or (ROOT / ".env")
    if not path.exists():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip("'\"")
            if k:
                os.environ[k] = v
    except Exception:
        pass


load_dotenv()


def load_config(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"No config file found at {path.resolve()}.\nCopy config.example.yaml to config.yaml and edit it.")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def watched_names(cfg: dict) -> set[str]:
    names = cfg.get("alerts", {}).get("companies") or []
    if names:
        return set(names)
    return {e["name"] for e in cfg.get("companies", [])}


# ---------------------------------------------------------------------------
# CLI Command Implementations
# ---------------------------------------------------------------------------

def cmd_scan(cfg: dict, store: Store, quiet: bool = False) -> dict:
    return run_pipeline(cfg, store, root_dir=ROOT, quiet=quiet)


def cmd_alert(cfg: dict, store: Store, dry_run: bool = False) -> None:
    """Check shortlist companies and dispatch instant Telegram alerts."""
    watch = watched_names(cfg)
    narrow = dict(cfg)
    narrow["companies"] = [e for e in cfg.get("companies", []) if e["name"] in watch]
    narrow["discovery"] = {"enabled": False}

    # Ingest and score watched companies
    cmd_scan(narrow, store, quiet=True)

    baselined = store.baselined_companies()
    # BUG #1 FIX: Only query unalerted jobs for watched companies!
    pending = store.unalerted(companies=watch)

    min_score = int(cfg.get("alerts", {}).get("min_score", cfg.get("llm", {}).get("min_score", 6)))
    fresh_companies = {r["company"] for r in pending} - baselined

    if fresh_companies and not dry_run:
        print(f"Baselining {len(fresh_companies)} new company(ies): {', '.join(sorted(fresh_companies))[:80]}...")

    qualified: list = []
    for r in pending:
        if r["company"] not in baselined:
            continue  # Silent baseline on first run
        if r["score"] is None or r["score"] < min_score:
            continue
        qualified.append(r)

    # Baseline newly discovered companies so they don't alert retroactively
    if fresh_companies and not dry_run:
        store.mark_alerted([r["id"] for r in pending if r["company"] in fresh_companies])

    # Mark scored-below-threshold jobs so they don't sit in pending
    below_thresh_ids = [
        r["id"] for r in pending
        if r["company"] in baselined and r["score"] is not None and r["score"] < min_score
    ]

    if not qualified:
        print("Nothing new at watched companies.")
        if not dry_run and below_thresh_ids:
            store.mark_alerted(below_thresh_ids)
        return

    cap = int(cfg.get("alerts", {}).get("max_per_alert", 15))
    to_send = qualified[:cap]
    label = time.strftime("%d %b %Y, %H:%M")

    if dry_run:
        print(f"\n[DRY RUN] Would send {len(to_send)} alert(s) to Telegram:")
        for j in to_send:
            s_str = f"[{j['score']}/10]" if j["score"] is not None else "[--/10]"
            print(f"  {s_str} {j['title']} @ {j['company']} ({j['location']})")
        return

    telegram.send_alert(cfg, to_send, label)
    # Mark alerted only for sent jobs and scored-below-threshold jobs (unscored remain in queue)
    settled_ids = [r["id"] for r in to_send] + below_thresh_ids
    store.mark_alerted(settled_ids)
    print(f"Sent Telegram alert for {len(to_send)} opening(s) at watched companies.")


def cmd_digest(cfg: dict, store: Store, days: int = 7, dry_run: bool = False) -> None:
    """Send ranked weekly digest to Telegram."""
    llm_cfg = cfg.get("llm") or {}
    min_score = int(llm_cfg.get("min_score", 0))
    scoring_on = llm_cfg.get("provider", "none") not in ("none", "off", None, "")

    pending = store.unnotified(min_score=min_score, require_scored=scoring_on)
    closed = store.closed_since(days * 86400)

    cap = int(cfg.get("digest", {}).get("max_jobs", 35))
    shown_jobs = pending[:cap]
    overflow = len(pending) - len(shown_jobs)

    label = time.strftime("Week of %d %b %Y")
    notes = []
    if overflow > 0:
        notes.append(f"Top {len(shown_jobs)} of {len(pending)} matching openings shown. Later runs report new arrivals.")

    if dry_run:
        print(f"\n[DRY RUN] Telegram Digest Preview ({label}):")
        print(f"  {len(shown_jobs)} new matches to show ({len(pending)} total pending), {len(closed)} closed.")
        for j in shown_jobs[:10]:
            s_str = f"[{j['score']}/10]" if j["score"] is not None else "[--/10]"
            print(f"    {s_str} {j['title']} @ {j['company']}")
        return

    if not pending and not closed:
        print("Nothing new to report; no digest sent.")
        return

    telegram.send_digest(cfg, shown_jobs, closed, label, notes=notes)
    # Mark ONLY shown jobs as notified so remaining overflow rolls over to next digest
    store.mark_notified([r["id"] for r in shown_jobs])
    print(f"Telegram digest delivered: {len(shown_jobs)} shown of {len(pending)} matching, {len(closed)} closed.")


def cmd_recap(cfg: dict, store: Store, dry_run: bool = False) -> None:
    """Re-apply seniority, location, and relevance caps to existing database rows."""
    candidate_cfg = cfg.get("candidate") or {}
    target_seniority = candidate_cfg.get("seniority", "junior")
    target_locations = candidate_cfg.get("locations") or []

    candidate_years = None
    cache_path = ROOT / ".resume_details.json"
    if cache_path.exists():
        try:
            det = json.loads(cache_path.read_text(encoding="utf-8"))
            candidate_years = det.get("years_of_experience")
        except Exception:
            pass

    rows = store.db.execute(
        "SELECT id, title, location, score, reason, breakdown, description FROM jobs WHERE score IS NOT NULL"
    ).fetchall()

    changed = []
    for r in rows:
        try:
            bd = json.loads(r["breakdown"]) if r["breakdown"] else {}
        except Exception:
            bd = {}
        old_bd = dict(bd)

        new_score, new_reason = apply_seniority_cap(
            r["score"],
            r["title"],
            r["reason"] or "",
            target_seniority=target_seniority,
            description=r["description"] or "",
            candidate_years=candidate_years,
            breakdown=bd,
        )
        new_score, new_reason = apply_location_cap(
            new_score,
            r["location"] or "",
            target_locations=target_locations,
            breakdown=bd,
            reason=new_reason,
        )
        new_score, new_reason = apply_relevance_cap(new_score, bd, new_reason)

        if new_score != r["score"] or bd != old_bd:
            changed.append((r["id"], new_score, new_reason, json.dumps(bd), r["title"], r["score"]))

    if dry_run:
        print(f"[DRY RUN] {len(changed)} of {len(rows)} scores would change:")
        for _, ns, _, _, title, old in changed[:15]:
            print(f"  {old} -> {ns}  {title[:60]}")
        return

    for jid, ns, nr, nbd, _, _ in changed:
        store.db.execute("UPDATE jobs SET score = ?, reason = ?, breakdown = ? WHERE id = ?", (ns, nr, nbd, jid))
    store.db.commit()
    print(f"Successfully capped {len(changed)} scores. No tokens used.")


def cmd_list(store: Store, days: int = 7) -> None:
    rows = store.since(days * 86400)
    if not rows:
        print("No recent openings found.")
        return
    for r in rows:
        s = f"{r['score']}/10" if r["score"] is not None else "  - "
        print(f"[{s}] {r['title'][:55]:<55} {r['company'][:18]:<18} {r['url']}")


def cmd_test(cfg: dict) -> None:
    print("Testing Telegram Bot connection...")
    success, msg = telegram.test_telegram(cfg)
    if success:
        print(f"✓ {msg}")
    else:
        sys.exit(f"✗ Telegram verification failed: {msg}")


def cmd_web(port: int = 8000) -> None:
    import uvicorn
    print(f"Starting JobTrace Backend API at http://127.0.0.1:{port}")
    uvicorn.run("jobtrace.web.server:app", host="0.0.0.0", port=port, log_level="info", reload=True)


def cmd_daemon(cfg: dict, store: Store) -> None:
    from .scheduler import Scheduler
    scheduler = Scheduler(
        alert_fn=lambda: cmd_alert(cfg, store),
        digest_fn=lambda: cmd_digest(cfg, store),
    )
    scheduler.run_forever()


# ---------------------------------------------------------------------------
# CLI Argument Dispatcher
# ---------------------------------------------------------------------------

def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="jobtrace", description="JobTrace Career Intelligence Tracker")
    parser.add_argument("--config", default=str(ROOT / "config.yaml"), help="Path to config.yaml")

    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan", help="Fetch, diff, and score open jobs")

    al = sub.add_parser("alert", help="Check shortlist and send Telegram alert")
    al.add_argument("--dry-run", action="store_true", help="Preview alert without sending")

    dg = sub.add_parser("digest", help="Send weekly digest to Telegram")
    dg.add_argument("--days", type=int, default=7, help="Days to look back for closed jobs")
    dg.add_argument("--dry-run", action="store_true", help="Preview digest without sending")

    rn = sub.add_parser("run", help="Scan and send digest in one run")
    rn.add_argument("--days", type=int, default=7)
    rn.add_argument("--dry-run", action="store_true")

    rc = sub.add_parser("recap", help="Re-apply seniority and relevance caps (0 tokens)")
    rc.add_argument("--dry-run", action="store_true")

    ls = sub.add_parser("list", help="List recent openings in terminal")
    ls.add_argument("--days", type=int, default=7)

    sub.add_parser("test", help="Test Telegram Bot credentials and connection")

    wb = sub.add_parser("web", help="Start local web backend API")
    wb.add_argument("--port", type=int, default=8000)

    sub.add_parser("daemon", help="Run background scheduler service")

    args = parser.parse_args(argv)
    cfg_path = Path(args.config)
    cfg = load_config(cfg_path)
    store = Store(ROOT / "jobtrace.db")

    if args.cmd == "scan":
        cmd_scan(cfg, store)
    elif args.cmd == "alert":
        cmd_alert(cfg, store, dry_run=args.dry_run)
    elif args.cmd == "digest":
        cmd_digest(cfg, store, days=args.days, dry_run=args.dry_run)
    elif args.cmd == "run":
        cmd_scan(cfg, store)
        cmd_digest(cfg, store, days=args.days, dry_run=args.dry_run)
    elif args.cmd == "recap":
        cmd_recap(cfg, store, dry_run=args.dry_run)
    elif args.cmd == "list":
        cmd_list(store, days=args.days)
    elif args.cmd == "test":
        cmd_test(cfg)
    elif args.cmd == "web":
        cmd_web(port=args.port)
    elif args.cmd == "daemon":
        cmd_daemon(cfg, store)


if __name__ == "__main__":
    main()
