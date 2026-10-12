"""Cursor backend: batching, parsing, and the account-setting errors that are
the most likely thing to go wrong. No network - the HTTP layer is stubbed."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CURSOR_API_KEY"] = "crsr_test"

import jobtrace.cursor as cur
from jobtrace.cursor import CursorError, CursorScorer

KEYS = ("skills","seniority","location","domain","recency","reach")
class R:
    def __init__(s, code, body): s.status_code, s._b, s.text = code, body, json.dumps(body)
    def json(s): return s._b

def stub(create, run):
    cur.requests.post = lambda *a, **k: create
    cur.requests.get = lambda *a, **k: run
cur.time.sleep = lambda s: None

jobs = [{"id": f"j{i}", "company": f"C{i}", "title": f"T{i}",
         "location": "Remote", "description": "python"} for i in range(3)]

def agent_ok(text):
    return (R(200, {"id": "a1", "latestRunId": "r1"}),
            R(200, {"status": "FINISHED", "result": text}))

# 1. a well-formed batch maps back onto the right job ids, by ref not position
stub(*agent_ok(json.dumps([
    {"ref": 2, "score": 9, "reason": "great", "breakdown": {k: 80 for k in KEYS}},
    {"ref": 0, "score": 3, "reason": "weak",  "breakdown": {k: 20 for k in KEYS}},
])))
sc = CursorScorer()
out = sc.score_batch("profile", jobs)
assert out["j2"][0] == 9 and out["j0"][0] == 3, out
assert "j1" not in out, "a job the model skipped must not be invented"
assert out["j2"][2] == {k: 80 for k in KEYS}

# 2. one agent run per batch, not one per job
calls = {"n": 0}
def counting_post(*a, **k):
    calls["n"] += 1
    return R(200, {"id": "a1", "latestRunId": "r1"})
cur.requests.post = counting_post
cur.requests.get = lambda *a, **k: R(200, {"status": "FINISHED", "result": json.dumps(
    [{"ref": i, "score": 5, "reason": "x", "breakdown": {}} for i in range(3)])})
sc.score_batch("p", jobs)
assert calls["n"] == 1, f"batch of 3 must be ONE agent run, was {calls['n']}"

# 3. junk inside a row degrades that row, not the batch
stub(*agent_ok(json.dumps([
    {"ref": 0, "score": "high", "reason": "x", "breakdown": {"skills": 900}},
    {"ref": 1, "score": 7, "reason": "ok", "breakdown": {"skills": 50}},
])))
out = CursorScorer().score_batch("p", jobs)
assert out["j0"][0] == 0, "unparseable score -> 0"
assert out["j0"][2]["skills"] == 100, "must clamp"
assert out["j1"][0] == 7

# 4. out-of-range refs are dropped rather than crashing
stub(*agent_ok(json.dumps([{"ref": 99, "score": 9, "reason": "x", "breakdown": {}}])))
assert CursorScorer().score_batch("p", jobs) == {}

# 5. the two account settings produce actionable messages
for body, needle in (
    ({"error": {"message": "Storage mode is disabled."}}, "storage"),
    ({"error": {"message": "Cloud agent is not supported in Privacy Mode (Legacy)."}}, "Privacy Mode"),
):
    cur.requests.post = lambda *a, _b=body, **k: R(400, _b)
    try:
        CursorScorer().score_batch("p", jobs); assert False, "should raise"
    except CursorError as e:
        assert needle.lower() in str(e).lower(), e

# 6. a failed run and a non-JSON reply are both loud, not silently zero
stub(R(200, {"id":"a1","latestRunId":"r1"}), R(200, {"status":"FAILED","error":"boom"}))
try: CursorScorer().score_batch("p", jobs); assert False
except CursorError as e: assert "FAILED" in str(e)
stub(*agent_ok("I could not do that."))
try: CursorScorer().score_batch("p", jobs); assert False
except CursorError as e: assert "no JSON array" in str(e)

# 7. a missing key is caught before any request goes out
os.environ["CURSOR_API_KEY"] = "paste-your-cursor-key-here"
try: CursorScorer(); assert False
except CursorError as e: assert "placeholder" in str(e)
os.environ["CURSOR_API_KEY"] = "crsr_test"

# 8. empty input costs nothing
assert CursorScorer().score_batch("p", []) == {}
print("all cursor tests PASS")

# --- model selection and token discipline ----------------------------------
os.environ["CURSOR_API_KEY"] = "crsr_test"
sc = CursorScorer()
assert sc.model == "gemini-3.8-flash", sc.model
sel = sc._model_selection()
assert sel == {"id": "gemini-3.8-flash",
               "params": [{"id": "reasoning_effort", "value": "low"}]}, sel
# params must actually reach the request body, not just sit on the object
sent = {}
def capture(url, **kw):
    sent.update(kw.get("json") or {})
    return R(200, {"id": "a1", "latestRunId": "r1"})
cur.requests.post = capture
cur.requests.get = lambda *a, **k: R(200, {"status": "FINISHED", "result": "[]"})
sc.score_batch("p", jobs)
assert sent["model"] == sel, sent.get("model")

# an explicit override wins, and empty params send no params key
sc2 = CursorScorer("claude-haiku-4-5", {"thinking": "false"})
assert sc2._model_selection()["params"] == [{"id": "thinking", "value": "false"}]
assert "params" not in CursorScorer("composer-2.5", {})._model_selection()

# the prompt must stay lean: descriptions clipped, profile clipped
sent.clear()
cur.requests.post = capture
big = [{"id": "x", "company": "C", "title": "T", "location": "L", "description": "d" * 5000}]
CursorScorer().score_batch("p" * 9000, big)
text = sent["prompt"]["text"]
# Budget: ~1200 profile + ~400/job + preamble. The preamble grew deliberately
# when seniority became a hard gate; that instruction earns its tokens.
assert len(text) < 2600, f"prompt ballooned to {len(text)} chars"
assert "Seniority is a hard gate" in text, "the seniority rule must reach the model"
assert "d" * 300 not in text, "description was not clipped"
assert "p" * 1500 not in text, "profile was not clipped"
print("model-selection + prompt-size tests PASS")
