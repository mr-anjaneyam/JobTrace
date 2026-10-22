import pytest

from jobtrace import llm


class FakeResp:
    def __init__(self, status=200, payload=None, headers=None, text=""):
        self.status_code = status
        self._payload = payload or {}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._payload


def ok(content="hello", prompt=10, completion=5):
    return FakeResp(200, {"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": prompt, "completion_tokens": completion}})


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)


def test_unknown_provider():
    with pytest.raises(ValueError):
        llm.LLM("nope", "m")


def test_complete_strips_think_and_counts_tokens(monkeypatch):
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: ok("<think>hmm</think>answer"))
    client = llm.LLM("ollama", "m")
    assert client.complete("hi") == "answer"
    assert client.input_tokens == 10 and client.output_tokens == 5


def test_retries_on_429_then_succeeds(monkeypatch):
    replies = iter([FakeResp(429, headers={"retry-after": "1"}), ok("fine")])
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: next(replies))
    assert llm.LLM("ollama", "m").complete("hi") == "fine"


def test_rate_limited_after_retries(monkeypatch):
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: FakeResp(429))
    with pytest.raises(llm.RateLimited):
        llm.LLM("ollama", "m").complete("hi", retries=2)


@pytest.mark.parametrize("status,needle", [(401, "rejected the API key"), (404, "not found"), (500, "HTTP 500")])
def test_http_errors(monkeypatch, status, needle):
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: FakeResp(status, text="boom"))
    with pytest.raises(RuntimeError, match=needle):
        llm.LLM("ollama", "m").complete("hi")


def test_connection_failure(monkeypatch):
    def fail(*a, **k):
        raise llm.requests.ConnectionError("offline")

    monkeypatch.setattr(llm.requests, "post", fail)
    with pytest.raises(RuntimeError, match="connection failed"):
        llm.LLM("ollama", "m").complete("hi", retries=2)


def test_bearer_header_uses_env_key(monkeypatch):
    seen = {}

    def post(url, headers, **k):
        seen.update(headers)
        return ok()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(llm.requests, "post", post)
    llm.LLM("openai", "m").complete("hi")
    assert seen["Authorization"] == "Bearer sk-test"


def test_make_scorer_dispatch():
    assert llm.make_scorer("none") is None
    assert llm.make_scorer("local", resume_text="python").__class__.__name__ == "LocalScorer"
    assert llm.make_scorer("ollama", "m").__class__.__name__ == "ChatScorer"


def test_chat_scorer_scores_batch(monkeypatch):
    reply = '[[0, 8, 90, 80, 70, 60, 50, 40, "good"]]'
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: ok(reply))
    scorer = llm.ChatScorer("ollama", "m")
    job = {"id": "j1", "company": "Acme", "title": "Engineer", "location": "Remote", "description": "x"}
    res = scorer.score("profile", job)
    assert res[0] == 8
    assert scorer.tokens_used == 15
