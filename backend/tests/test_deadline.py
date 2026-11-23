from datetime import datetime

import pytest

from jobtrace.deadline import extract_deadline


@pytest.mark.parametrize("text,expected", [
    ("Apply by Nov 1, 2020", datetime(2020, 11, 1, 23, 59, 59)),
    ("Application deadline: 2020-11-01", datetime(2020, 11, 1, 23, 59, 59)),
    ("Last date to apply: 1st November 2020", datetime(2020, 11, 1, 23, 59, 59)),
])
def test_deadline_date_formats(text, expected):
    timestamp, _ = extract_deadline(text)
    assert timestamp == expected.timestamp()


def test_posting_and_graduation_dates_are_not_expiry_dates():
    assert extract_deadline("Posted on Nov 1, 2020. Graduation before June 2020.") == (None, "")
    assert extract_deadline("Deadline: 2020-02-31")[0] is None
