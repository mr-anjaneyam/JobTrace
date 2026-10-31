"""File logging for JobTrace.

Two files are written side by side under <data folder>/logs:
  jobtrace.log                     continuous; when it passes 25 MB the old content moves to jobtrace.log.1
  daily/jobtrace-YYYY-MM-DD.log    one file per day, old days deleted after `logging.retention_days`

Calls to job portals and AI models go through `traced`, which logs the request, the status, the time
taken and (optionally) the request and response text. Secrets are removed before anything is written.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

import requests

from . import limits

LOGGER_NAME = "jobtrace"
FORMAT = "%(asctime)s %(levelname)-7s [%(process)d] %(name)s: %(message)s"
CONTINUOUS_NAME = "jobtrace.log"
CONTINUOUS_MAX_BYTES = 25 * 1024 * 1024
DEFAULTS = {"level": "INFO", "log_bodies": True}
LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")

SECRET_ENV_NAMES = (
    "XKIRO_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "CURSOR_API_KEY",
    "ANTHROPIC_API_KEY", "TYPESAFE_API_KEY", "TELEGRAM_BOT_TOKEN",
)
_SECRET_PATTERNS = (
    (re.compile(r"bot\d+:[^/\s?\"']+"), "bot***"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{8,}"), "Bearer ***"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"), "sk-***"),
)
_SENSITIVE_PARAM = re.compile(r"(?i)key|token|secret|password|auth|signature|sig$")

_lock = threading.Lock()
_state: dict[str, Any] = {"dir": None, "handlers": [], "log_bodies": True, "max_body_chars": 4000}


class ContinuousHandler(logging.FileHandler):
    """Appends forever to one file; past the size cap the old content moves to <file>.1."""

    def __init__(self, path: Path, max_bytes: int = CONTINUOUS_MAX_BYTES):
        super().__init__(path, encoding="utf-8", delay=True)
        self.max_bytes = max_bytes
        self._writes = 0

    def emit(self, record: logging.LogRecord) -> None:
        self._writes += 1
        if self._writes % 100 == 0:
            self._roll_if_big()
        super().emit(record)

    def _roll_if_big(self) -> None:
        try:
            if os.path.getsize(self.baseFilename) < self.max_bytes:
                return
            if self.stream:
                self.stream.close()
                self.stream = None
            os.replace(self.baseFilename, self.baseFilename + ".1")
        except OSError:
            pass  # another process holds the file; try again later


class DailyHandler(logging.FileHandler):
    """Writes to jobtrace-YYYY-MM-DD.log and switches file at midnight."""

    def __init__(self, directory: Path, retention_days: int):
        directory.mkdir(parents=True, exist_ok=True)
        self.directory = directory
        self.retention_days = retention_days
        self._day = date.today()
        super().__init__(self._path(self._day), encoding="utf-8", delay=True)
        self.prune()

    def _path(self, day: date) -> str:
        return str(self.directory / f"jobtrace-{day.isoformat()}.log")

    def emit(self, record: logging.LogRecord) -> None:
        today = date.today()
        if today != self._day:
            self._day = today
            if self.stream:
                self.stream.close()
                self.stream = None
            self.baseFilename = os.path.abspath(self._path(today))
            self.prune()
        super().emit(record)

    def prune(self) -> None:
        for f in self.directory.glob("jobtrace-*.log"):
            try:
                day = date.fromisoformat(f.stem.removeprefix("jobtrace-"))
                if (date.today() - day).days > self.retention_days:
                    f.unlink()
            except (ValueError, OSError):
                continue


def settings(cfg: dict | None) -> dict:
    cfg = cfg or {}
    raw = cfg.get("logging") or {}
    level = str(raw.get("level", DEFAULTS["level"])).upper()
    return {
        "level": level if level in LEVELS else DEFAULTS["level"],
        "log_bodies": bool(raw.get("log_bodies", DEFAULTS["log_bodies"])),
        "retention_days": limits.get(cfg, "logging", "retention_days"),
        "max_body_chars": limits.get(cfg, "logging", "max_body_chars"),
    }


def configure(cfg: dict | None, root: Path) -> Path:
    """Attach the file handlers for `root`/logs and apply the current settings. Safe to call often."""
    s = settings(cfg)
    log_dir = Path(root) / "logs"
    with _lock:
        if _state["dir"] != log_dir:
            _detach()
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
                handlers: list[logging.Handler] = [
                    ContinuousHandler(log_dir / CONTINUOUS_NAME),
                    DailyHandler(log_dir / "daily", s["retention_days"]),
                ]
            except OSError:
                handlers = []  # read-only folder: keep running without file logs
            fmt = logging.Formatter(FORMAT)
            for h in handlers:
                h.setFormatter(fmt)
            _state["handlers"] = handlers
            _state["dir"] = log_dir
            _attach(logging.getLogger(LOGGER_NAME))
        for h in _state["handlers"]:
            if isinstance(h, DailyHandler) and h.retention_days != s["retention_days"]:
                h.retention_days = s["retention_days"]
                h.prune()
        logging.getLogger(LOGGER_NAME).setLevel(s["level"])
        _state["log_bodies"] = s["log_bodies"]
        _state["max_body_chars"] = s["max_body_chars"]
    return log_dir


def attach_uvicorn() -> None:
    """uvicorn does not propagate to our logger, so give its loggers the same files."""
    with _lock:
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            _attach(logging.getLogger(name))


def _attach(logger: logging.Logger) -> None:
    for h in _state["handlers"]:
        if h not in logger.handlers:
            logger.addHandler(h)


def _detach() -> None:
    names = [LOGGER_NAME, "uvicorn", "uvicorn.error", "uvicorn.access"]
    for h in _state["handlers"]:
        for name in names:
            logging.getLogger(name).removeHandler(h)
        h.close()
    _state["handlers"] = []
    _state["dir"] = None


def reset() -> None:
    """Close the files and forget the folder (used by tests)."""
    with _lock:
        _detach()


# ---- redaction ----------------------------------------------------------------

def scrub(text: str) -> str:
    """Remove API keys, bot tokens and bearer tokens from text headed for a log file."""
    for name in SECRET_ENV_NAMES:
        value = os.environ.get(name, "")
        if len(value) >= 8:
            text = text.replace(value, "***")
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def safe_url(url: str) -> str:
    try:
        p = urlparse(url)
        host = p.hostname or ""
        netloc = f"{host}:{p.port}" if p.port else host
        query = urlencode([(k, "***" if _SENSITIVE_PARAM.search(k) else v) for k, v in parse_qsl(p.query, keep_blank_values=True)])
        url = urlunparse((p.scheme, netloc, p.path, p.params, query, ""))
    except ValueError:
        pass
    return scrub(url)


def clip(value: Any, total: int | None = None) -> str:
    """One-line, secret-free, length-limited text for a log record (`total` = size of the full text, if cut earlier)."""
    limit = _state["max_body_chars"]
    if value is None or value == "":
        return "-"
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = scrub(text).replace("\r", "").replace("\n", "\\n")
    size = total if total is not None else len(text)
    return text if size <= limit else f"{text[:limit]}...(truncated, {size} chars)"


# ---- traced requests ----------------------------------------------------------

def traced(kind: str, fn: Callable[..., Any], url: str, *, bodies: bool = True, **kwargs: Any) -> Any:
    """Call `fn(url, **kwargs)` (requests.get or requests.post) and log it under jobtrace.<kind>.

    Logging never changes the outcome: the response or the exception is passed through untouched.
    """
    log = logging.getLogger(f"{LOGGER_NAME}.{kind}")
    method = getattr(fn, "__name__", "request").upper()
    started = time.monotonic()
    try:
        resp = fn(url, **kwargs)
    except requests.RequestException as e:
        _safely(_log_failure, log, method, url, kwargs, started, e, bodies)
        raise
    _safely(_log_response, log, method, url, kwargs, started, resp, bodies)
    return resp


def _safely(fn: Callable[..., None], *args: Any) -> None:
    try:
        fn(*args)
    except Exception:
        pass


def _full_url(url: str, kwargs: dict) -> str:
    params = kwargs.get("params")
    if params:
        return safe_url(requests.Request("GET", url, params=params).prepare().url or url)
    return safe_url(url)


def _request_text(kwargs: dict) -> str:
    body = kwargs.get("json") if kwargs.get("json") is not None else kwargs.get("data")
    return clip(body)


def _wants_bodies(bodies: bool) -> bool:
    return bodies and _state["log_bodies"] and _state["max_body_chars"] > 0


def _log_response(log: logging.Logger, method: str, url: str, kwargs: dict, started: float, resp: Any, bodies: bool) -> None:
    ms = int((time.monotonic() - started) * 1000)
    status = getattr(resp, "status_code", 0)
    line = f"{method} {_full_url(url, kwargs)} -> {status} {ms}ms"
    streamed = bool(kwargs.get("stream"))
    if not streamed:
        text = getattr(resp, "text", "") or ""
        line += f" {len(text)} chars"
        if _wants_bodies(bodies):
            line += f" req={_request_text(kwargs)} resp={clip(text[: _state['max_body_chars'] + 1], total=len(text))}"
    log.log(logging.WARNING if status >= 400 else logging.INFO, line)


def _log_failure(log: logging.Logger, method: str, url: str, kwargs: dict, started: float, err: Exception, bodies: bool) -> None:
    ms = int((time.monotonic() - started) * 1000)
    line = f"{method} {_full_url(url, kwargs)} FAILED after {ms}ms: {clip(str(err))}"
    if _wants_bodies(bodies):
        line += f" req={_request_text(kwargs)}"
    log.warning(line)
