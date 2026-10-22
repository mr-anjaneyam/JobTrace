import json

import pytest

from jobtrace import batch

JOBS = [
    {"id": "a", "company": "Acme", "title": "Engineer", "location": "Remote", "description": "Requirements: Python and 3+ years of experience building APIs."},
    {"id": "b", "company": "Globex", "title": "Developer", "location": "", "description": ""},
]


def test_build_messages_references_every_job():
    msgs = batch.build_messages("Candidate profile", JOBS)
    assert msgs[0]["role"] == "system" and "Candidate profile" in msgs[0]["content"]
    body = msgs[1]["content"]
    assert "0|Acme|Engineer|Remote|" in body
    assert "1|Globex|Developer|?|" in body


def test_clean_breakdown_clamps_and_pads():
    out = batch.clean_breakdown([150, -5, "x", 40])
    assert out == {"skills": 100, "seniority": 0, "location": 0, "domain": 40, "recency": 0, "reach": 0}


def test_parse_positional_arrays():
    text = json.dumps([[0, 8, 90, 80, 70, 60, 50, 40, "great fit"], [1, 3, 10, 10, 10, 10, 10, 10, "meh"]])
    out = batch.parse(text, JOBS)
    assert out["a"][0] == 8 and out["a"][1] == "great fit"
    assert out["a"][2]["skills"] == 90
    assert out["b"][0] == 3


def test_parse_tolerates_markdown_fence_and_dicts():
    text = '```json\n[{"ref": 1, "score": 12, "reason": "x"}]\n```'
    out = batch.parse(text, JOBS)
    assert out["b"][0] == 10  # clamped


def test_parse_salvages_truncated_output():
    text = '[[0, 7, 1, 2, 3, 4, 5, 6, "ok"], [1, 5, 1, 2, 3, 4, 5, 6, "cut off'
    out = batch.parse(text, JOBS)
    assert out["a"][0] == 7
    assert "b" not in out


def test_parse_ignores_out_of_range_refs():
    out = batch.parse("[[9, 5, 1, 1, 1, 1, 1, 1, \"x\"]]", JOBS)
    assert out == {}


def test_parse_rejects_garbage():
    with pytest.raises(ValueError):
        batch.parse("no json here", JOBS)
