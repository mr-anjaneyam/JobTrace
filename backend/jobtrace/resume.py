"""Resume parsing and candidate profile extraction for JobTrace."""
from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any

COMMON_TECH_SKILLS = [
    "Python", "JavaScript", "TypeScript", "Go", "Golang", "Java", "C++", "C#", "Rust", "Ruby", "PHP", "Swift", "Kotlin",
    "React", "React Native", "Next.js", "Vue", "Angular", "Svelte", "Node.js", "Express", "FastAPI", "Django", "Flask",
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "Cassandra", "SQLite", "DynamoDB",
    "Docker", "Kubernetes", "AWS", "GCP", "Azure", "Terraform", "CI/CD", "GitHub Actions", "Linux", "Git",
    "GraphQL", "REST", "REST APIs", "gRPC", "Kafka", "RabbitMQ", "Microservices", "System Design",
    "PyTorch", "TensorFlow", "Pandas", "NumPy", "Scikit-Learn", "LLM", "NLP", "SQL",
]


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
    if p.suffix.lower() == ".docx":
        return _docx_text(p)
    return p.read_text(encoding="utf-8", errors="replace")


def _docx_text(p: Path) -> str:
    import html
    import zipfile

    try:
        with zipfile.ZipFile(p) as z:
            xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    except (zipfile.BadZipFile, KeyError) as e:
        raise RuntimeError(f"Not a valid .docx file: {p.name}") from e
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:(tab|br)\s*/>", " ", xml)
    return html.unescape(re.sub(r"<[^>]+>", "", xml)).strip()


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


DETAILS_PROMPT = """Extract structured candidate facts from this resume.
Reply with ONLY a valid JSON object matching this schema:
{{
  "name": "Candidate Full Name",
  "headline": "Role or professional headline, max 6 words",
  "location": "Primary location (e.g. San Francisco, CA or Remote)",
  "target_locations": ["Remote", "San Francisco"],
  "years_of_experience": 3.5,
  "seniority": "mid",
  "seniority_reason": "Explanation of detected seniority band based on years and roles",
  "skills": ["Python", "FastAPI", "React", "Docker", "PostgreSQL"],
  "summary": "2-3 sentence executive profile summary",
  "experience": [
    {{"org": "Company Name", "role": "Job Title", "years": "2023 - Present", "highlights": "Key achievements or technologies"}}
  ],
  "education": [
    {{"institution": "University Name", "degree": "B.S. in Computer Science", "year": "2021"}}
  ]
}}

Valid values for 'seniority': "intern", "junior", "mid", "senior", "lead", "any".

RESUME:
{text}"""


def build_details(text: str, llm: Any) -> dict:
    fallback = parse_details(text)
    if llm is None or not hasattr(llm, "complete"):
        return fallback

    try:
        raw = llm.complete(DETAILS_PROMPT.format(text=text[:12000]), max_tokens=900)
        match = re.search(r"\{.*\}", raw, re.S)
        if not match:
            return fallback
        data = json.loads(match.group(0))
        # Merge LLM findings over heuristic fallback
        for k in ("name", "headline", "location", "seniority", "seniority_reason", "summary"):
            if data.get(k):
                fallback[k] = data[k]
        if isinstance(data.get("years_of_experience"), (int, float)) and data["years_of_experience"] > 0:
            fallback["years_of_experience"] = round(float(data["years_of_experience"]), 1)
        if data.get("skills") and isinstance(data["skills"], list):
            fallback["skills"] = [str(s).strip() for s in data["skills"] if str(s).strip()]
        if data.get("target_locations") and isinstance(data["target_locations"], list):
            fallback["target_locations"] = [str(l).strip() for l in data["target_locations"] if str(l).strip()]
        if data.get("experience") and isinstance(data["experience"], list) and len(data["experience"]) > 0:
            fallback["experience"] = data["experience"]
        if data.get("education") and isinstance(data["education"], list) and len(data["education"]) > 0:
            fallback["education"] = data["education"]
        return fallback
    except Exception as e:
        fallback["error"] = f"Model refinement notice: {e}"[:150]
        return fallback


# --------------------------------------------------------------------------
# Offline Dynamic Parser & Seniority Derivation
# --------------------------------------------------------------------------

_MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTHS = r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
_RANGE = re.compile(
    rf"((?:{_MONTHS})[a-z]*\.?\s*\d{{4}}|\d{{4}})\s*[-to\u2013\u2014\ufffd\?~]+\s*"
    rf"((?:{_MONTHS})[a-z]*\.?\s*\d{{4}}|\d{{4}}|Present|Current|Now)",
    re.I,
)
_SECTION = re.compile(
    r"^\s*(EXPERIENCE|WORK EXPERIENCE|PROFESSIONAL EXPERIENCE|EMPLOYMENT|EDUCATION|"
    r"PROJECTS|TECHNICAL SKILLS|SKILLS|SUMMARY|PROFILE|OBJECTIVE|"
    r"CERTIFICATIONS?|ACHIEVEMENTS?|PUBLICATIONS?|LANGUAGES)\s*:?\s*$",
    re.I,
)


def _parse_date_bound(raw: str, current_year: int) -> float:
    s = raw.strip().lower()
    if re.search(r"present|current|now", s):
        return float(current_year) + (datetime.datetime.now().month / 12.0)

    # Check for month + year
    m_yr = re.search(r"\b(19\d\d|20\d\d)\b", s)
    if not m_yr:
        return 0.0
    yr = int(m_yr.group(1))

    m_mon = re.search(r"\b(" + "|".join(_MONTH_NAMES.keys()) + r")\b", s)
    if m_mon:
        month_num = _MONTH_NAMES.get(m_mon.group(1)[:3], 6)
        return yr + ((month_num - 1) / 12.0)
    return float(yr)


def calc_experience_years(ranges: list[str]) -> float:
    """Calculate non-overlapping total years of experience across all roles."""
    now_yr = datetime.datetime.now().year
    intervals: list[tuple[float, float]] = []

    for r in ranges:
        m = _RANGE.search(r)
        if not m:
            continue
        start = _parse_date_bound(m.group(1), now_yr)
        end = _parse_date_bound(m.group(2), now_yr)
        if start > 0 and end >= start:
            intervals.append((start, end))

    if not intervals:
        return 0.0

    # Merge overlapping intervals so concurrent roles aren't double counted
    intervals.sort()
    merged = [intervals[0]]
    for s, e in intervals[1:]:
        last_s, last_e = merged[-1]
        if s <= last_e:
            merged[-1] = (last_s, max(last_e, e))
        else:
            merged.append((s, e))

    total = sum(e - s for s, e in merged)
    return round(float(total), 1)


def determine_seniority(years: float, titles: list[str], full_text: str = "") -> tuple[str, str]:
    """Derive target seniority band dynamically from years of experience and titles."""
    titles_joined = " ".join(titles).lower()

    if re.search(r"\b(staff|principal|director|head of|vp|chief|architect)\b", titles_joined) or years >= 8.0:
        band = "lead"
        reason = f"Detected {years} yrs experience with lead/staff roles ({', '.join(titles[:2]) or 'leadership level'})."
    elif re.search(r"\b(senior|sr\.?)\b", titles_joined) or years >= 4.5:
        band = "senior"
        reason = f"Detected {years} yrs experience with senior roles ({', '.join(titles[:2])})."
    elif years >= 2.0:
        band = "mid"
        reason = f"Detected {years} yrs professional experience ({', '.join(titles[:2])}) in mid-level band."
    elif any(re.search(r"\b(engineer|developer|analyst|associate|consultant|specialist)\b", t, re.I) and not re.search(r"\b(intern|internship)\b", t, re.I) for t in titles) or years >= 0.8:
        band = "junior"
        reason = f"Detected {years} yrs experience ({', '.join(titles[:2])}) in early-career / junior band."
    else:
        band = "intern"
        reason = f"Detected student / internship background with {years} yrs experience."

    return band, reason


def _unrun(s: str) -> str:
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)


def _name_from_handle(text: str) -> str:
    m = re.search(r"(?:linkedin\.com/in/|github\.com/)([A-Za-z][A-Za-z-]{2,40})", text)
    if not m:
        return ""
    parts = [p for p in re.split(r"[-_]", m.group(1)) if len(p) > 1]
    return " ".join(p.capitalize() for p in parts)


def extract_skills_heuristic(text: str) -> list[str]:
    """Extract known technical skills and programming tools found in resume."""
    found: list[str] = []
    text_lower = text.lower()
    for skill in COMMON_TECH_SKILLS:
        pattern = rf"\b{re.escape(skill.lower())}\b"
        if re.search(pattern, text_lower):
            found.append(skill)
    return found


def _is_bullet_or_text(s: str) -> bool:
    s = s.strip()
    if not s:
        return True
    if any(s.startswith(ch) for ch in ("-", "•", "*", "\u2013", "\u2014", "\ufffd", "\u2022", "·", "\x87", "\x8c")):
        return True
    if s.endswith((".", ";")):
        return True
    words = s.split()
    if len(words) > 8:
        return True
    first_word = re.sub(r"[^a-zA-Z]", "", words[0]).lower()
    bullet_verbs = {
        "engineered", "developed", "built", "led", "contributed", "designed",
        "implemented", "maintained", "created", "worked", "managed", "conducted",
        "optimized", "automated", "collaborated", "spearheaded", "authored", "assisted",
        "delivered", "resolved", "improved", "architected", "integrated", "programmed",
        "analyzed", "tested", "deployed", "supported", "migrated"
    }
    if first_word in bullet_verbs:
        return True
    return False


def _clean_org(s: str, cand_name: str = "") -> str:
    s = s.strip(" ,|·-\u2013\u2014\ufffd\x87\x8c?\"'()")
    if not s or len(s) > 60:
        return ""
    if cand_name and s.lower() == cand_name.lower():
        return ""
    if _is_bullet_or_text(s):
        return ""
    if re.search(r"\b(b\.?s|b\.?tech|m\.?s|m\.?tech|bachelor|master|ph\.?d|degree|diploma|gpa|cgpa)\b", s, re.I):
        return ""
    if re.search(r"^[A-Za-z\s]+,\s*(?:[A-Z]{2}|IN|US|UK|CA|India|USA|Remote)$", s, re.I):
        return ""
    return s[:60]


def extract_education_heuristic(lines: list[str]) -> list[dict]:
    """Extract degrees, university names, and graduation years."""
    edu: list[dict] = []
    in_edu = False
    deg_pattern = re.compile(r"\b(b\.?s|b\.?tech|m\.?s|m\.?tech|bachelor|master|ph\.?d|degree|diploma)\b", re.I)
    inst_pattern = re.compile(r"\b(institute|university|college|academy|school)\b", re.I)

    pending_inst = ""
    for i, ln in enumerate(lines):
        if re.match(r"^\s*EDUCATION\b", ln, re.I):
            in_edu = True
            continue
        elif in_edu and _SECTION.match(ln):
            break

        if in_edu:
            if inst_pattern.search(ln):
                pending_inst = ln.split("|")[0].strip()
                continue
            if deg_pattern.search(ln):
                parts = [p.strip() for p in ln.split("|")]
                search_text = f"{ln} {lines[i + 1] if i + 1 < len(lines) else ''}"
                all_yrs = re.findall(r"\b(19\d\d|20\d\d)\b", search_text)
                grad_yr = all_yrs[-1] if all_yrs else ""
                institution = parts[1] if len(parts) > 1 else pending_inst
                if not institution and i > 0 and inst_pattern.search(lines[i - 1]):
                    institution = lines[i - 1].strip()
                if not institution and i > 1 and inst_pattern.search(lines[i - 2]):
                    institution = lines[i - 2].strip()

                edu.append({
                    "degree": parts[0] if parts else ln[:60],
                    "institution": institution[:60],
                    "year": grad_yr,
                })
    return edu


def parse_details(text: str) -> dict:
    """Offline heuristic extractor for resume name, location, seniority, and experience."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out: dict = {
        "name": "",
        "headline": "",
        "location": "",
        "target_locations": [],
        "years_of_experience": 0.0,
        "seniority": "mid",
        "seniority_reason": "",
        "skills": [],
        "summary": "",
        "experience": [],
        "education": [],
        "error": "",
    }
    if not lines:
        return out

    out["name"] = _name_from_handle(text) or lines[0][:60].title()

    # Search location in header
    for ln in lines[1:8]:
        head = ln.split("|")[0].strip()
        if 2 <= head.count(",") + 1 <= 4 and "@" not in head and len(head) < 60:
            if not any(ch.isdigit() for ch in head):
                out["location"] = head
                break

    if out["location"]:
        out["target_locations"] = ["Remote", out["location"].split(",")[0].strip()]
    else:
        out["target_locations"] = ["Remote"]

    # Summary section detection
    for i, ln in enumerate(lines):
        if re.match(r"^\s*(SUMMARY|PROFILE|OBJECTIVE)\s*:?\s*$", ln, re.I) and i + 1 < len(lines):
            summary_lines = []
            for j in range(i + 1, min(i + 6, len(lines))):
                if _SECTION.match(lines[j]):
                    break
                summary_lines.append(lines[j])
            out["summary"] = " ".join(summary_lines)[:350]
            words = re.split(r"[.;]", _unrun(lines[i + 1]))[0].split()
            out["summary_line"] = " ".join(words[:9])
            break

    # Experience entries
    seen = set()
    role_titles: list[str] = []
    date_ranges: list[str] = []
    current_section = ""
    sec_start_idx = -1
    last_known_org = ""

    for i, ln in enumerate(lines):
        sec_m = _SECTION.match(ln)
        if sec_m:
            current_section = sec_m.group(1).upper()
            sec_start_idx = i
            last_known_org = ""
            continue

        if "EDUCATION" in current_section or "PROJECT" in current_section or "SKILL" in current_section:
            continue

        m = _RANGE.search(ln)
        if not m:
            continue
        years = f"{m.group(1)} - {m.group(2)}"

        # Role and Org parsing
        role_part = _unrun(ln[: m.start()]).strip(" ,|·-\u2013\u2014\ufffd?")
        if not role_part and i > 0:
            prev_line = lines[i - 1].strip(" ,|·-\u2013\u2014\ufffd?")
            if not _SECTION.match(prev_line) and not _is_bullet_or_text(prev_line):
                role_part = prev_line

        org = ""
        role = ""

        if "|" in role_part:
            parts = [p.strip() for p in role_part.split("|")]
            role, org = parts[0], _clean_org(parts[1], out["name"])
        elif re.search(r"\b(?:at|@)\b", role_part, re.I):
            parts = re.split(r"\s+(?:at|@)\s+", role_part, maxsplit=1, flags=re.I)
            role, org = parts[0].strip(), _clean_org(parts[1], out["name"])
        else:
            role = role_part

        # If org not found yet, check preceding lines within current experience section
        if not org and i - 2 > sec_start_idx:
            candidate_loc = lines[i - 2].strip()
            if ("," in candidate_loc or re.search(r"\b(in|ca|ny|tx|wa|uk|usa|remote)\b", candidate_loc, re.I)):
                if not out["location"]:
                    out["location"] = candidate_loc
                city = candidate_loc.split(",")[0].strip()
                if city and city not in out["target_locations"]:
                    out["target_locations"].append(city)
                if i - 3 > sec_start_idx:
                    cand_org = _clean_org(lines[i - 3], out["name"])
                    if cand_org and not _SECTION.match(cand_org):
                        org = cand_org
            else:
                cand_org = _clean_org(candidate_loc, out["name"])
                if cand_org and not _SECTION.match(cand_org):
                    org = cand_org

        # Check following line if valid company name
        if not org and i + 1 < len(lines):
            cand_nxt = _clean_org(lines[i + 1], out["name"])
            if cand_nxt and not _SECTION.match(cand_nxt):
                org = cand_nxt

        # If role is empty but org was extracted
        if not role and org:
            role, org = org, ""

        # Fallback to last known company within same section (e.g. multi-role at same employer)
        if not org and last_known_org:
            org = last_known_org

        if org:
            last_known_org = org

        if not role:
            continue

        # Skip academic degrees and schools from being treated as jobs
        if re.search(r"\b(b\.?s|b\.?tech|m\.?s|m\.?tech|bachelor|master|ph\.?d|degree|diploma|university|college|school)\b", f"{role} {org}", re.I):
            continue

        key = (role[:40], years)
        if key in seen:
            continue
        seen.add(key)
        date_ranges.append(years)
        role_titles.append(role)

        # Look for bullet points/highlights
        highlights: list[str] = []
        for h_idx in range(i + 1, min(i + 6, len(lines))):
            h_line = lines[h_idx]
            if _RANGE.search(h_line) or _SECTION.match(h_line):
                break
            if h_line.startswith(("-", "•", "*", "\u2013", "\u2014", "\ufffd", "\u2022")):
                highlights.append(h_line.lstrip("-•*\u2013\u2014\ufffd\u2022 ").strip())
            elif len(highlights) == 0 and len(h_line) > 30 and not h_line.startswith("http"):
                highlights.append(h_line)

        out["experience"].append({
            "org": org[:50] or role[:50],
            "role": role[:60] if org else "",
            "years": years,
            "highlights": " • ".join(highlights[:3]),
        })
        if len(out["experience"]) >= 8:
            break

    # Headline determination
    for e in out["experience"]:
        if e["role"] and not re.match(
            r"^b\.?tech|^b\.?sc|^m\.?tech|^bachelor|^master|^diploma", e["role"], re.I
        ):
            out["headline"] = e["role"]
            break

    if not out["headline"]:
        out["headline"] = out.pop("summary_line", "")
    out.pop("summary_line", None)

    # Dynamic Seniority Band & Years Calculation
    calc_years = calc_experience_years(date_ranges)
    stated_m = re.search(r"(\d+(?:\.\d+)?)\+?\s*years?\s+of\s+(?:production\s+|professional\s+|relevant\s+|industry\s+|technical\s+)?experience", text, re.I)
    if stated_m:
        try:
            stated_val = float(stated_m.group(1))
            out["years_of_experience"] = stated_val if (calc_years == 0 or abs(stated_val - calc_years) <= 3.0) else calc_years
        except ValueError:
            out["years_of_experience"] = calc_years
    else:
        out["years_of_experience"] = calc_years

    band, reason = determine_seniority(out["years_of_experience"], role_titles, text)
    out["seniority"] = band
    out["seniority_reason"] = reason

    # Skills and Education
    out["skills"] = extract_skills_heuristic(text)
    out["education"] = extract_education_heuristic(lines)

    if not out["summary"] and out["headline"]:
        skills_preview = ", ".join(out["skills"][:4]) if out["skills"] else "modern tech stacks"
        out["summary"] = f"{out['headline']} with ~{out['years_of_experience']} years of experience specializing in {skills_preview}."

    return out

