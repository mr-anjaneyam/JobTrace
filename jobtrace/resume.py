"""Resume parsing and candidate profile extraction for JobTrace."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def extract_text(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Resume not found at: {p.resolve()}")

    if p.suffix.lower() == ".pdf":
        try:
            import pymupdf
            doc = pymupdf.open(str(p))
            return "\n".join(page.get_text() for page in doc)
        except ImportError:
            pass
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(p))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError as e:
            raise RuntimeError("Install pymupdf or pypdf to read PDF resumes (`pip install pymupdf`)") from e
    return p.read_text(encoding="utf-8", errors="replace")


PROFILE_PROMPT = """Summarize this resume into a concise candidate profile of at most 180 words.

Explicitly state:
1. Total years of paid technical experience, graduation status, and target seniority band.
2. Primary languages, frameworks, cloud stacks, and domain expertise.
3. Target locations and work authorization (if stated).

Write clear, objective prose without markdown headings.

RESUME:
{text}"""


def build_profile(text: str, llm: Any) -> str:
    if llm is None or not hasattr(llm, "complete"):
        return text[:2500]
    return llm.complete(PROFILE_PROMPT.format(text=text[:12000]), max_tokens=400).strip()


DETAILS_PROMPT = """Extract structured facts from this resume.
Reply with ONLY a JSON object:
{{"name": "...", "headline": "<role or headline, max 5 words>", "location": "<city, country>",
  "experience": [{{"org": "...", "role": "...", "years": "<e.g. 2023 - 2025>"}}]}}

RESUME:
{text}"""


def build_details(text: str, llm: Any) -> dict:
    fallback = {"name": "", "headline": "", "location": "", "experience": [], "error": ""}
    if llm is None or not hasattr(llm, "complete"):
        return {**fallback, "error": "No model configured"}

    raw = llm.complete(DETAILS_PROMPT.format(text=text[:12000]), max_tokens=650)
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        return {**fallback, "error": "Model returned no JSON"}
    try:
        data = json.loads(match.group(0))
        return {**fallback, **{k: data.get(k, fallback[k]) for k in fallback if k != "error"}}
    except json.JSONDecodeError:
        return {**fallback, "error": "Invalid JSON from model"}


# --------------------------------------------------------------------------
# Offline Heuristic Resume Parser
# --------------------------------------------------------------------------

_MONTHS = r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
_RANGE = re.compile(
    rf"((?:{_MONTHS})[a-z]*\.?\s*\d{{4}}|\d{{4}})\s*[-–—to]+\s*"
    rf"((?:{_MONTHS})[a-z]*\.?\s*\d{{4}}|\d{{4}}|Present|Current)",
    re.I,
)
_SECTION = re.compile(
    r"^\s*(EXPERIENCE|EDUCATION|WORK|EMPLOYMENT|PROJECTS|SKILLS|SUMMARY|PROFILE"
    r"|CERTIFICATIONS?|ACHIEVEMENTS?|AWARDS?|PUBLICATIONS?|INTERESTS?|CONTACT"
    r"|TECHNICAL SKILLS|ACTIVITIES|LANGUAGES)\s*:?\s*$",
    re.I,
)


def _unrun(s: str) -> str:
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)


def _name_from_handle(text: str) -> str:
    m = re.search(r"(?:linkedin\.com/in/|github\.com/)([A-Za-z][A-Za-z-]{2,40})", text)
    if not m:
        return ""
    parts = [p for p in re.split(r"[-_]", m.group(1)) if len(p) > 1]
    return " ".join(p.capitalize() for p in parts)


def parse_details(text: str) -> dict:
    """Offline heuristic extractor for resume name, location, and experience."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out: dict = {"name": "", "headline": "", "location": "", "experience": [], "error": ""}
    if not lines:
        return out

    out["name"] = _name_from_handle(text) or lines[0][:60].title()

    # Search location
    for ln in lines[1:8]:
        head = ln.split("|")[0].strip()
        if 2 <= head.count(",") + 1 <= 4 and "@" not in head and len(head) < 60:
            if not any(ch.isdigit() for ch in head):
                out["location"] = head
                break

    # Headline: the first substantive line of a SUMMARY/PROFILE section.
    for i, ln in enumerate(lines):
        if re.match(r"^\s*(SUMMARY|PROFILE|OBJECTIVE)\s*$", ln, re.I) and i + 1 < len(lines):
            words = re.split(r"[.;]", _unrun(lines[i + 1]))[0].split()
            out["summary_line"] = " ".join(words[:9])
            break

    # Experience entries
    seen = set()
    for i, ln in enumerate(lines):
        if _SECTION.match(ln):
            continue
        m = _RANGE.search(ln)
        if not m:
            continue
        years = f"{m.group(1)} - {m.group(2)}"
        role = _unrun(ln[: m.start()]).strip(" ,|·-–—")
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        org = "" if _SECTION.match(nxt) else nxt.split(",")[0].strip()
        if not role and org:
            role, org = org, ""
        if not role:
            continue
        key = (role[:40], years)
        if key in seen:
            continue
        seen.add(key)
        out["experience"].append({
            "org": org[:50] or role[:50],
            "role": role[:60] if org else "",
            "years": years,
        })
        if len(out["experience"]) >= 6:
            break

    for e in out["experience"]:
        if e["role"] and not re.match(
            r"^b\.?tech|^b\.?sc|^m\.?tech|^bachelor|^master|^diploma", e["role"], re.I
        ):
            out["headline"] = e["role"]
            break

    if not out["headline"]:
        out["headline"] = out.pop("summary_line", "")
    out.pop("summary_line", None)
    return out
