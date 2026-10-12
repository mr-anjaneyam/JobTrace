"""Verify Jev score rescaling and penalties against a stubbed SDK, so the math
is proven without burning API calls."""
import os, sys, types
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- stub the typesafe_sdk package -----------------------------------------
sdk = types.ModuleType("typesafe_sdk")
class Score:
    def __init__(self, instructions, criteria): self.criteria = criteria
class Choice:
    def __init__(self, instructions, criteria): self.criteria = criteria
class _S:
    def __init__(self, score, confidence): self.score, self.confidence = score, confidence
class _C:
    def __init__(self, choice): self.choice = choice
class _U:
    input_tokens, output_tokens = 1200, 0
class _R:
    def __init__(self, fit, sen, loc, conf):
        self.scores = {"fit": _S(fit, conf)}
        self.choices = {"seniority": _C(sen), "location": _C(loc)}
        self.usage = _U()
NEXT = {}
class TypeSafeClient:
    def __init__(self, *a, **k): pass
    def system_one(self, state, questions):
        assert "CANDIDATE RESUME" in state and "JOB POSTING" in state
        assert set(questions) == {"fit", "seniority", "location"}
        return _R(**NEXT)
sdk.Score, sdk.Choice, sdk.TypeSafeClient = Score, Choice, TypeSafeClient
sys.modules["typesafe_sdk"] = sdk
os.environ["TYPESAFE_API_KEY"] = "test"

from jobtrace.jev import JevScorer, FIT_LEVELS
from jobtrace.llm import make_scorer

job = {"company": "Acme", "title": "Backend Engineer", "location": "Remote",
       "description": "Python, Go, distributed systems."}
s = JevScorer()

def check(fit, sen, loc, conf, expect):
    NEXT.clear(); NEXT.update(fit=fit, sen=sen, loc=loc, conf=conf)
    got, reason, bd = s.score("resume text", job)
    assert set(bd) == {"skills","seniority","location","domain","recency","reach"}, bd
    assert all(0 <= v <= 100 for v in bd.values()), bd
    assert got == expect, f"fit={fit} {sen}/{loc} -> {got}, expected {expect}"
    assert 0 <= got <= 10
    return reason

# top of scale (4.0 of 0..4) with everything matching -> 10
r = check(4.0, "match", "ok", 0.91, 10)
assert "confidence 91%" in r and "seniority match" in r, r
check(0.0, "match", "ok", 1.0, 0)          # bottom of scale -> 0
check(2.0, "match", "ok", 1.0, 5)          # midpoint -> 5
check(4.0, "match", "blocked", 1.0, 3)     # 10 * 0.3
check(4.0, "over", "ok", 1.0, 8)           # 10 * 0.75 -> 7.5 -> 8
check(4.0, "under", "blocked", 1.0, 2)     # 10 * 0.3 * 0.75 = 2.25 -> 2
check(2.86, "match", "ok", 0.6, 7)         # fractional score survives rescale

# an SDK failure must degrade, not crash the run
class Boom(TypeSafeClient):
    def system_one(self, *a, **k): raise RuntimeError("503")
s.client = Boom()
score, reason, bd = s.score("resume", job)
assert score == 0 and "scoring failed" in reason, reason
assert bd == {}, "a failed call reports no breakdown rather than inventing one"

# routing: provider name picks the right backend, "none" disables scoring
assert make_scorer("jev", "").provider == "jev"
assert make_scorer("none", "") is None
assert not hasattr(make_scorer("jev", ""), "complete"), \
    "Jev outputs no text, so it must not be used to summarize the resume"
# cost tracking: 7 successful scored calls above, 1200 input tokens each
assert s.input_tokens == 7 * 1200, s.input_tokens
expected = 7 * 1200 / 1_000_000 * 0.042
assert abs(s.cost_usd() - expected) < 1e-9, s.cost_usd()
print(f"cost for 7 jobs: ${s.cost_usd():.6f}  (~${s.cost_usd()/7*1000:.2f} per 1000 jobs)")
print("all jev tests PASS")
