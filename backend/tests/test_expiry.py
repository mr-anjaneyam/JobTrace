"""Every source must have a working expiry path. Company boards expire by
absence; aggregators have no presence signal, so they expire by age."""
import os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jobtrace.store import Store

def job(i, company, source, desc=""):
    return {"id": i, "company": company, "title": f"Engineer {i}", "url": "u",
            "location": "Remote", "posted_at": None, "source": source,
            "description": desc, "domain": ""}

s = Store(os.path.join(tempfile.mkdtemp(), "e.db"))
s.upsert([job("board", "Acme", "greenhouse"),
          job("agg1", "Randomco", "remotive"),
          job("agg2", "Otherco", "arbeitnow")])

# absence from a clean board fetch closes a tracked company's job
time.sleep(0.02)
s.upsert([job("agg1", "Randomco", "remotive")])
assert [r["id"] for r in s.mark_closed(["Acme"])] == ["board"]

# aggregators are untouched by absence - a query simply may not have hit them
assert s.mark_closed(["Acme"]) == []
assert len(s.db.execute(
    "SELECT 1 FROM jobs WHERE source='arbeitnow' AND closed_at IS NULL").fetchall()) == 1

# ...and untouched by age until they cross the window
assert s.close_stale(["remotive", "arbeitnow"], max_age_days=14) == []

# age them past the window
old = time.time() - 20 * 86400
s.db.execute("UPDATE jobs SET last_seen = ? WHERE id = 'agg2'", (old,))
s.db.commit()
closed = s.close_stale(["remotive", "arbeitnow"], max_age_days=14)
assert [r["id"] for r in closed] == ["agg2"], closed
assert s.close_stale(["remotive", "arbeitnow"], 14) == [], "already closed, not repeated"

# a stale job that reappears in a later run reopens
s.upsert([job("agg2", "Otherco", "arbeitnow")])
assert s.db.execute("SELECT closed_at FROM jobs WHERE id='agg2'").fetchone()["closed_at"] is None

# an empty source list is a no-op, not a mass closure
assert s.close_stale([], 1) == []
assert s.db.execute("SELECT COUNT(*) FROM jobs WHERE closed_at IS NULL").fetchone()[0] == 2

# nothing expired ever reaches a caller
assert all(r["closed_at"] is None for r in s.unnotified(0))
assert all(r["closed_at"] is None for r in s.unalerted())
print("expiry tests PASS")
