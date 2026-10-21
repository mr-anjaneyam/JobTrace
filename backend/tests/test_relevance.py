"""The relevance gate: a wrong-field role must not ride a strong seniority
match. Mirror of the seniority gate, which stops the opposite failure."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jobtrace.relevance import apply_cap, is_irrelevant, CAP

def bd(skills, domain, **kw):
    base = {"skills": skills, "seniority": 100, "location": 80,
            "domain": domain, "recency": 100, "reach": 90}
    base.update(kw)
    return base

# the real case: a branch internship scoring 8/10 for a full-stack developer
investor = bd(30, 50)
assert apply_cap(8, investor, "junior fit")[0] == CAP
assert "wrong field" in apply_cap(8, investor, "junior fit")[1]
assert "junior fit" in apply_cap(8, investor, "junior fit")[1], "keeps the original reason"

# a genuine match is untouched
assert apply_cap(9, bd(95, 100), "strong") == (9, "strong")

# BOTH axes must be weak - one strong axis is enough to survive
assert apply_cap(8, bd(30, 90))[0] == 8, "unfamiliar domain, strong skills: keep"
assert apply_cap(8, bd(90, 30))[0] == 8, "unfamiliar skills, strong domain: keep"
assert apply_cap(8, bd(59, 59))[0] == CAP, "both below floor: cap"
assert apply_cap(8, bd(60, 59))[0] == 8, "exactly at the floor is not below it"

# already low scores are left alone
assert apply_cap(2, investor, "weak") == (2, "weak")
assert apply_cap(CAP, investor, "x") == (CAP, "x")

# missing or unusable data must never trigger a cap
assert apply_cap(9, None, "x") == (9, "x")
assert apply_cap(9, {}, "x") == (9, "x")
assert apply_cap(9, {k: 0 for k in
                     ("skills","seniority","location","domain","recency","reach")}, "x")[0] == 9, \
    "an all-zero breakdown means no data, not a bad fit"
assert apply_cap(9, {"skills": "high", "domain": None}, "x") == (9, "x"), "junk is not a verdict"
assert not is_irrelevant(None) and not is_irrelevant({})

# both gates compose: a senior wrong-field role is capped once, and the second
# gate leaves an already-capped score alone rather than stacking penalties
from jobtrace.seniority import apply_cap as sen_cap
s, r = sen_cap(9, "Senior Sales Manager", "great")
assert s == CAP and "senior title" in r
s2, r2 = apply_cap(s, investor, r)
assert s2 == CAP, "no double penalty"
assert r2 == r, "the second gate adds no note to an already-capped score"

# order does not matter: relevance first still lands at the cap
s3, r3 = apply_cap(9, investor, "great")
s3, r3 = sen_cap(s3, "Senior Sales Manager", r3)
assert s3 == CAP and "wrong field" in r3
print("relevance gate tests PASS")
