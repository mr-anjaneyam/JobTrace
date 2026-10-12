"""The scan must stop short of the daily cap, not discover it by hitting it."""
import os, sqlite3, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jobtrace.budget import Budget

db = sqlite3.connect(os.path.join(tempfile.mkdtemp(), "b.db"))
b = Budget(db, daily_limit=500_000, reserve=40_000)

assert b.used() == 0
assert b.remaining() == 460_000, b.remaining()      # limit minus reserve
b.record(100_000)
assert b.used() == 100_000 and b.remaining() == 360_000

# the reserve is never spendable, so a digest can still run after a big scan
b.record(360_000)
assert b.used() == 460_000
assert b.remaining() == 0, "reserve must stay protected"
assert not b.can_afford(1), "nothing spendable once the reserve is all that is left"
assert b.used() < 500_000, "the hard cap itself is never reached"

# negative or junk spend cannot credit the account back
b.record(-5000)
assert b.used() == 460_000

# affordability is checked against a real batch size
b2 = Budget(sqlite3.connect(":memory:"), daily_limit=500_000, reserve=40_000)
b2.record(455_000)
assert b2.remaining() == 5_000
assert b2.can_afford(2_000) is True,  "a batch that fits must be allowed"
assert b2.can_afford(6_000) is False, "a batch that overruns must be refused"
b2r = Budget(sqlite3.connect(":memory:"), daily_limit=500_000, reserve=0)
assert b2r.can_afford(500_000) is True

# spend is per calendar day, so yesterday's usage never blocks today
db.execute("INSERT INTO spend (day, tokens) VALUES ('2000-01-01', 499999)")
db.commit()
assert b.used() == 460_000, "an old day must not count against today"
assert "tokens today" in b.report()
print("budget tests PASS")
