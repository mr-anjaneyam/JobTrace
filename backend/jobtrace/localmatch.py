"""Configurable offline keyword & location matcher for JobTrace.

Evaluates resume skill overlap, location compatibility, and recency without
requiring an LLM or network connection.
"""
from __future__ import annotations

import re
import time

VOCAB = {
    "javascript", "typescript", "python", "java", "golang", "go", "rust", "ruby",
    "php", "swift", "kotlin", "scala", "c", "c++", "c#", "sql", "bash",
    "react", "angular", "vue", "svelte", "next.js", "nextjs", "node", "node.js",
    "express", "django", "flask", "fastapi", "rails", "spring", "laravel",
    "react native", "flutter", "android", "ios",
    "mongodb", "postgresql", "postgres", "mysql", "redis", "sqlite", "dynamodb",
    "elasticsearch", "kafka", "rabbitmq", "graphql", "rest", "grpc",
    "docker", "kubernetes", "aws", "gcp", "azure", "terraform", "jenkins",
    "ci/cd", "git", "github", "gitlab", "linux", "nginx",
    "tensorflow", "pytorch", "keras", "pandas", "numpy", "scikit-learn",
    "llm", "rag", "nlp", "machine learning", "deep learning", "computer vision",
    "jest", "pytest", "cypress", "playwright", "selenium",
    "html", "css", "tailwind", "sass", "webpack", "vite", "figma",
    "jwt", "oauth", "websocket", "socket.io", "microservices", "api",
}

_LABELS = {
    "languages", "frontend", "backend", "databases", "tools", "ai", "ml",
    "ai / ml", "frameworks", "other", "technologies", "concepts"
}

JUNIOR = (
    "intern", "internship", "junior", "jr.", "entry level", "entry-level",
    "graduate", "new grad", "associate", "trainee", "apprentice", "fresher"
)
REMOTE_KEYWORDS = ("remote", "anywhere", "work from home", "distributed", "telecommute")


def _mentions(haystack: str, needle: str) -> bool:
    """Word boundary search that preserves punctuation like C++ or Node.js."""
    return re.search(rf"(?<![\w.+#]){re.escape(needle)}(?![\w.+#])", haystack) is not None


def extract_skills(resume_text: str) -> set[str]:
    text = resume_text.lower()
    found = {v for v in VOCAB if _mentions(text, v)}

    m = re.search(
        r"^\s*(?:technical\s+)?skills\s*:?\s*$(.*?)(?=^\s*[A-Z][A-Z ]{3,}\s*$|\Z)",
        resume_text,
        re.I | re.M | re.S,
    )
    if m:
        for chunk in re.split(r"[,;:|\n]", m.group(1)):
            tok = chunk.strip().lower()
            tok = re.sub(r"^(languages|frontend|backend|databases|tools|ai\s*/\s*ml)\s*", "", tok)
            if not re.search(r"[a-z]{2}", tok):
                continue
            tok = tok.strip(" /-&.")
            if 2 <= len(tok) <= 24 and tok not in _LABELS:
                found.add(tok)
    return {s for s in found if s}


class LocalScorer:
    """Offline keyword and heuristic matcher."""

    provider = "local"

    def __init__(
        self,
        resume_text: str = "",
        target_locations: list[str] | None = None,
        target_seniority: str = "junior",
    ):
        self.skills = extract_skills(resume_text)
        self.target_locations = [loc.strip().lower() for loc in (target_locations or []) if loc.strip()]
        self.target_seniority = (target_seniority or "junior").lower()

    def score(self, profile: str, job: dict) -> tuple[int, str, dict]:
        title = (job.get("title") or "").lower()
        desc = (job.get("description") or "").lower()
        blob = f"{title} {desc}"
        where = (job.get("location") or "").lower()

        hits = sorted(s for s in self.skills if _mentions(blob, s))
        # 6 skill hits represents a high match
        skills = min(100, round(len(hits) / 6 * 100)) if self.skills else 40

        from .seniority import extract_required_years, is_senior_title, is_mid_title

        req_years = extract_required_years(desc, title=title)
        senior_role = is_senior_title(title)
        junior_role = any(k in title for k in JUNIOR)
        mid_role = is_mid_title(title)

        if self.target_seniority in ("intern", "junior", "entry"):
            if req_years is not None and req_years >= 4.0:
                seniority = 15
            elif req_years is not None and req_years >= 3.0:
                seniority = 25
            elif senior_role:
                seniority = 20
            elif mid_role:
                seniority = 45
            elif junior_role:
                seniority = 100
            else:
                seniority = 70
        elif self.target_seniority in ("senior", "lead", "staff"):
            seniority = 30 if (junior_role or (req_years is not None and req_years <= 1.0)) else (95 if senior_role else 80)
        else:  # mid or any
            seniority = 70 if (senior_role or junior_role) else 85

        # Location scoring
        is_remote = any(k in where for k in REMOTE_KEYWORDS) or not where
        if is_remote:
            location = 90
        elif self.target_locations:
            matched_loc = any(re.search(rf"\b{re.escape(loc)}\b", where) for loc in self.target_locations)
            location = 100 if matched_loc else 15
        else:
            location = 75

        # Recency scoring
        recency = 60
        posted = job.get("posted_at")
        if posted:
            days = (time.time() - posted) / 86400
            recency = 100 if days <= 7 else 80 if days <= 30 else 50 if days <= 90 else 25

        domain = min(100, round(len(hits) / 4 * 100)) if hits else 30
        reach = round(skills * 0.5 + seniority * 0.35 + location * 0.15)
        blended = skills * 0.45 + seniority * 0.25 + location * 0.15 + domain * 0.15
        final_score = max(0, min(10, round(blended / 10)))

        # Seniority gates
        if self.target_seniority in ("intern", "junior", "entry"):
            if req_years is not None and req_years >= 4.0:
                final_score = min(final_score, 2)
            elif req_years is not None and req_years >= 3.0:
                final_score = min(final_score, 3)
            elif senior_role:
                final_score = min(final_score, 3)
            elif mid_role:
                final_score = min(final_score, 5)

        # Location gate: confirmed onsite location mismatch capped at 3
        if self.target_locations and not is_remote and location <= 20:
            final_score = min(final_score, 3)

        if hits:
            shown = ", ".join(hits[:4])
            reason = f"keyword match: {shown}" + (f" +{len(hits) - 4} more" if len(hits) > 4 else "")
        else:
            reason = "keyword match: no overlapping skills found"

        if self.target_seniority in ("intern", "junior", "entry"):
            if req_years is not None and req_years >= 3.0:
                reason += f"; requires {req_years:g}+ yrs exp"
            elif senior_role:
                reason += "; senior title"
            elif mid_role:
                reason += "; mid-level II role"
        if location <= 20:
            reason += f"; location mismatch (onsite in {job.get('location') or 'outside target'})"

        breakdown = {
            "skills": skills,
            "seniority": seniority,
            "location": location,
            "domain": domain,
            "recency": recency,
            "reach": reach,
        }
        return final_score, reason[:200], breakdown
