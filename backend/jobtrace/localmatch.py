"""Configurable offline keyword & location matcher for JobTrace.

Evaluates resume skill overlap, location compatibility, and recency without
requiring an LLM or network connection.
"""
from __future__ import annotations

import re
import time

from . import geo

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
        self.target_locations = [loc.strip() for loc in (target_locations or []) if loc.strip()]
        self.target_seniority = (target_seniority or "junior").lower()

    def score(self, profile: str, job: dict) -> tuple[int, str, dict]:
        title = (job.get("title") or "").lower()
        desc = (job.get("description") or "").lower()
        blob = f"{title} {desc}"
        where = (job.get("location") or "").lower()

        hits = sorted(s for s in self.skills if _mentions(blob, s))
        # 6 skill hits represents a high match
        skills = min(100, round(len(hits) / 6 * 100)) if self.skills else 40

        from .seniority import extract_required_years, is_senior_title, is_mid_title, is_fresher_only

        req_years = extract_required_years(desc, title=title)
        senior_role = is_senior_title(title)
        junior_role = any(k in title for k in JUNIOR)
        mid_role = is_mid_title(title)

        fresher_role = is_fresher_only(title, desc)
        if self.target_seniority in ("intern", "junior", "entry"):
            if fresher_role:
                seniority = 15
            elif req_years is not None and req_years >= 4.0:
                seniority = 15
            elif req_years is not None and req_years >= 3.0:
                seniority = 25
            elif senior_role:
                seniority = 20
            elif mid_role:
                seniority = 45
            elif junior_role:
                seniority = 90
            else:
                seniority = 70
        elif self.target_seniority in ("senior", "lead", "staff"):
            seniority = 30 if (junior_role or (req_years is not None and req_years <= 1.0)) else (95 if senior_role else 80)
        else:  # mid or any
            seniority = 70 if (senior_role or junior_role) else 85

        # Location scoring
        is_remote = any(k in where for k in REMOTE_KEYWORDS) or geo.is_unknown_location(where)
        if is_remote:
            location = 90
        elif self.target_locations:
            matched_loc = any(geo.matches_target(loc, job.get("location") or "") for loc in self.target_locations)
            location = 100 if matched_loc else 15
        else:
            location = 75

        # Recency scoring
        recency = 60
        posted = job.get("posted_at")
        if posted:
            days = (time.time() - posted) / 86400
            recency = 100 if days <= 7 else 80 if days <= 30 else 50 if days <= 90 else 25

        domain = min(100, round(len(hits) / 4 * 100)) if len(hits) >= 2 else 0
        reach = round(skills * 0.5 + seniority * 0.35 + location * 0.15)
        blended = skills * 0.45 + seniority * 0.25 + location * 0.15 + domain * 0.15
        final_score = max(0, min(10, round(blended / 10)))

        # Seniority gates
        if self.target_seniority in ("intern", "junior", "entry"):
            if fresher_role:
                final_score = min(final_score, 2)
            elif req_years is not None and req_years >= 4.0:
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


# ---------------------------------------------------------------------------
# Pass 1: Fast Deterministic Triage (0 AI Tokens)
# ---------------------------------------------------------------------------
DISQUALIFIED_NON_TECH_PATTERNS = [
    re.compile(r"\b(?:receptionist|telecaller|telecalling|bpo|call\s*center|customer\s*support|customer\s*service)\b", re.I),
    re.compile(r"\b(?:investigation\s+representative|insurance\s+advisor|accounting\s+apprentice|accountant)\b", re.I),
    re.compile(r"\b(?:medical\s+officer|health\s+inspector|nurse|lab\s+technician|technician\s*\(\d+\))\b", re.I),
    re.compile(r"\b(?:office\s+assistant|sales\s+executive|sales\s+representative|business\s+development\s+associate)\b", re.I),
]


def triage_job(
    job: dict,
    candidate_years: float | None = None,
    candidate_seniority: str = "junior",
    candidate_skills: set[str] | list[str] | None = None,
    target_locations: list[str] | None = None,
) -> tuple[int, str, dict] | None:
    """Pass 1: Deterministic Triage (0 AI Tokens).

    Returns (score, reason, breakdown) if definitely disqualified by rule,
    or None if the job is eligible for Pass 2 (Deep Semantic Evaluation with LLM).
    All evaluations are strictly relative to the candidate's verified profile.
    """
    title = (job.get("title") or "").strip()
    desc = (job.get("description") or "").strip()
    title_lower = title.lower()

    from .seniority import extract_required_years, is_senior_title, is_junior_title, is_fresher_only
    from .salary import extract_salary
    from .deadline import extract_deadline

    # Parse salary and deadline if present
    sal_min, sal_max, sal_curr, sal_text = extract_salary(f"{title} {desc}")
    dead_at, dead_text = extract_deadline(f"{title} {desc}")

    # 1. Non-technical disqualifiers (unless title also contains software/engineer/developer/architect/scientist)
    is_eng = any(k in title_lower for k in ("software", "developer", "engineer", "programmer", "architect", "data scientist"))
    if not is_eng:
        for pat in DISQUALIFIED_NON_TECH_PATTERNS:
            if pat.search(title_lower):
                return (
                    1,
                    "triage: non-technical role",
                    {
                        "skills": 0, "seniority": 10, "location": 100, "domain": 0, "recency": 100, "reach": 100,
                        "matched_skills": [],
                        "missing_skills": ["Software Engineering"],
                        "seniority_fit": "Non-technical position",
                        "advice": "Role does not match technical engineering qualifications.",
                        "salary_min": sal_min, "salary_max": sal_max, "salary_currency": sal_curr, "salary_text": sal_text,
                        "deadline_at": dead_at, "deadline_text": dead_text,
                    }
                )

    # 2. Seniority & Experience alignment based entirely on candidate's verified background
    req_years = extract_required_years(desc, title=title_lower)
    mode = (candidate_seniority or "junior").lower().strip()
    cand_is_junior = mode in ("intern", "junior", "entry") or (candidate_years is not None and candidate_years <= 2.5)
    cand_is_senior = mode in ("senior", "lead", "staff", "principal") or (candidate_years is not None and candidate_years >= 5.0)

    if cand_is_junior:
        # For junior profiles: Disqualify roles requiring >= 5 years or senior leadership titles
        if is_senior_title(title_lower) or (req_years is not None and req_years >= 5.0):
            cand_str = f"candidate profile has {candidate_years:g} yrs" if candidate_years is not None else "junior profile"
            return (
                2,
                f"triage: requires {req_years:g}+ yrs exp" if req_years else "triage: senior/lead title",
                {
                    "skills": 35, "seniority": 15, "location": 100, "domain": 40, "recency": 100, "reach": 30,
                    "matched_skills": [],
                    "missing_skills": [f"{req_years:g}+ years of experience" if req_years else "Senior experience"],
                    "seniority_fit": f"Seniority gap (requires {req_years:g}+ yrs; {cand_str})" if req_years else f"Senior title exceeds {cand_str}",
                    "advice": "Senior/Lead role requiring significantly more years of experience.",
                    "salary_min": sal_min, "salary_max": sal_max, "salary_currency": sal_curr, "salary_text": sal_text,
                    "deadline_at": dead_at, "deadline_text": dead_text,
                }
            )

        # Strictly campus / student drives if candidate already has verified full-time industry experience
        if (candidate_years is not None and candidate_years >= 0.5) and is_fresher_only(title_lower, desc):
            return (
                2,
                "triage: campus/student drive only",
                {
                    "skills": 40, "seniority": 20, "location": 100, "domain": 50, "recency": 100, "reach": 100,
                    "matched_skills": [],
                    "missing_skills": ["Enrolled student status"],
                    "seniority_fit": "Role strictly reserved for campus/student batches",
                    "advice": "Candidate has industry experience; position is restricted to students.",
                    "salary_min": sal_min, "salary_max": sal_max, "salary_currency": sal_curr, "salary_text": sal_text,
                    "deadline_at": dead_at, "deadline_text": dead_text,
                }
            )

    elif cand_is_senior:
        # For senior engineers: Disqualify low-level internships or student trainee roles
        if is_junior_title(title_lower) or is_fresher_only(title_lower, desc) or (req_years is not None and req_years <= 1.0):
            return (
                2,
                "triage: entry/intern role for senior profile",
                {
                    "skills": 50, "seniority": 20, "location": 100, "domain": 50, "recency": 100, "reach": 100,
                    "matched_skills": [],
                    "missing_skills": ["Entry-level career stage"],
                    "seniority_fit": "Entry-level/intern role unsuitable for senior engineer profile",
                    "advice": "Role seniority is below candidate's experienced career level.",
                    "salary_min": sal_min, "salary_max": sal_max, "salary_currency": sal_curr, "salary_text": sal_text,
                    "deadline_at": dead_at, "deadline_text": dead_text,
                }
            )

    return None
