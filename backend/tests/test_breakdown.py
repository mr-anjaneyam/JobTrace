"""The UI draws a bar per criterion; those bars must come from the model, not
from anything invented client-side."""
import os, sys, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["OLLAMA_UNUSED"] = "1"
import jobtrace.llm as m
from jobtrace.llm import make_scorer
from jobtrace.store import Store

class R:
    def __init__(s, body): s.status_code, s._b, s.headers, s.text = 200, body, {}, ""
    def json(s): return s._b
def reply(obj):
    """The chat path batches, so a reply is a JSON array keyed by ref."""
    row = {"ref": 0, **obj}
    m.requests.post = lambda *a, **k: R(
        {"choices": [{"message": {"content": json.dumps([row])}}]})

sc = make_scorer("ollama", "m")
job = {"id":"j","company":"A","title":"T","location":"L","description":"d"}
KEYS = ("skills","seniority","location","domain","recency","reach")

reply({"score":8,"reason":"good","breakdown":{k:70 for k in KEYS}})
score, reason, bd = sc.score("p", job)
assert (score, reason) == (8, "good") and bd == {k:70 for k in KEYS}, bd

# a model that omits or mangles the breakdown must not crash the run
reply({"score":5,"reason":"ok"})
assert sc.score("p", job)[2] == {k:0 for k in KEYS}, "missing breakdown -> zeros"
reply({"score":5,"reason":"ok","breakdown":{"skills":"high","reach":None,"seniority":250,"domain":-4}})
bd = sc.score("p", job)[2]
assert bd["skills"] == 0 and bd["reach"] == 0, bd
assert bd["seniority"] == 100 and bd["domain"] == 0, "must clamp to 0-100"

# breakdown survives a round-trip through the database
st = Store(os.path.join(tempfile.mkdtemp(), "b.db"))
st.upsert([{"id":"j1","company":"A","title":"T","url":"u","location":"","posted_at":None,
            "source":"greenhouse","description":"","domain":"a.com"}])
st.save_score("j1", 8, "why", {k:60 for k in KEYS})
row = st.db.execute("SELECT breakdown FROM jobs WHERE id='j1'").fetchone()
assert json.loads(row["breakdown"]) == {k:60 for k in KEYS}
st.save_score("j1", 3, "why", None)
assert json.loads(st.db.execute("SELECT breakdown FROM jobs WHERE id='j1'").fetchone()["breakdown"]) == {}
print("breakdown tests PASS")

# --- dropped rows must never become invented scores -------------------------
from jobtrace import batch
jobs3 = [{"id": f"j{i}", "company": "C", "title": "T", "location": "L",
          "description": "d"} for i in range(3)]

# model returns only 2 of 3 rows
out = batch.parse(json.dumps([
    {"ref": 0, "score": 7, "reason": "a", "breakdown": {}},
    {"ref": 2, "score": 3, "reason": "b", "breakdown": {}},
]), jobs3)
assert set(out) == {"j0", "j2"}, out
assert "j1" not in out, "a skipped row must be absent, not scored 0"

# out-of-range and malformed refs are dropped, not mapped onto the wrong job
assert batch.parse(json.dumps([{"ref": 99, "score": 9}]), jobs3) == {}
assert batch.parse(json.dumps([{"ref": "x", "score": 9}]), jobs3) == {}
assert batch.parse(json.dumps(["not a dict"]), jobs3) == {}

# prose around the array is tolerated; no array at all is an error
assert len(batch.parse('Sure!\n[{"ref":1,"score":5}]\nDone', jobs3)) == 1
try:
    batch.parse("I cannot do that", jobs3); assert False
except ValueError as e:
    assert "no JSON array" in str(e)

# the prompt stays lean at a full batch
p = batch.build_prompt("p" * 5000, [{**j, "description": "d" * 4000} for j in jobs3])
assert len(p) < 4200, f"prompt ballooned to {len(p)}"
print("batch parsing tests PASS")

# --- a malformed reply must not cost the whole batch -----------------------
broken = '''[
 {"ref":0,"score":7,"reason":"he said "great" here","breakdown":{}},
 {"ref":1,"score":4,"reason":"fine","breakdown":{"skills":50}},
 {"ref":2,"score":9,"reason":"strong","breakdown":{}}
]'''
out = batch.parse(broken, jobs3)
assert set(out) == {"j1", "j2"}, out          # row 0 unsalvageable, others kept
assert out["j1"][0] == 4 and out["j2"][0] == 9
assert "j0" not in out, "an unparseable row must be dropped, not guessed"

# truncated output keeps the complete objects that arrived
truncated = '[{"ref":0,"score":6,"reason":"ok","breakdown":{}},{"ref":1,"sco'
assert set(batch.parse(truncated, jobs3)) == {"j0"}

# total garbage still raises so the caller can defer the chunk
try:
    batch.parse("[{{{{]", jobs3); assert False, "should raise"
except (ValueError, json.JSONDecodeError):
    pass
print("salvage tests PASS")
