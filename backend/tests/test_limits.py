from jobtrace import limits


def test_limits_get_falls_back_and_clamps():
    assert limits.get({}, "llm", "batch_size") == 25
    assert limits.get({"llm": {"batch_size": "40"}}, "llm", "batch_size") == 40
    assert limits.get({"llm": {"batch_size": "junk"}}, "llm", "batch_size") == 25
    assert limits.get({"llm": {"batch_size": 9999}}, "llm", "batch_size") == 100
    assert limits.get({"storage": {"retention_days": 0}}, "storage", "retention_days") == 0
    assert limits.clamp("llm", "batch_size", None) is None
