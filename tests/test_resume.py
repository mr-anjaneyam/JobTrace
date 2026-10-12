"""The profile panel must work with no model configured, and must not invent
fields it cannot find."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jobtrace.resume import parse_details

# Deliberately mangled the way pdf extraction mangles a real CV: spaces
# scattered through the header line, words run together in the summary.
RESUME = """ALE X R MORGAN
Springfield, Ohio, United States|+1 555 0100
alex@example.com|linkedin.com/in/alex-morgan|github.com/alexmorgan
SUMMARY
Full-stack developer who shipsAI products in production. Built things.
EDUCATION
B.Tech in Computer Science Engineering, State University 2022 - 2026
SKILLS
JavaScript, Python, React
EXPERIENCE
Full-Stack Developer Intern Jun 2025 - Aug 2025
Acme Systems
AI/ML Intern Jul 2024 - Aug 2024
Globex Labs
"""

d = parse_details(RESUME)
# the header line is mangled by PDF extraction; the profile URL is not
assert d["name"] == "Alex Morgan", d["name"]
assert d["location"] == "Springfield, Ohio, United States", d["location"]
# a real job title beats a PDF-mangled prose summary
assert d["headline"] == "Full-Stack Developer Intern", d["headline"]
# ...and education is never used as the headline
assert "B.Tech" not in d["headline"]
roles = {e["years"]: e for e in d["experience"]}
assert "Jun 2025 - Aug 2025" in roles and "Jul 2024 - Aug 2024" in roles, roles
assert roles["Jun 2025 - Aug 2025"]["org"] == "Acme Systems"
assert roles["Jun 2025 - Aug 2025"]["role"] == "Full-Stack Developer Intern"
# a section heading must never be captured as an employer
assert all(e["org"].upper() not in ("SKILLS", "EXPERIENCE", "EDUCATION", "SUMMARY")
           for e in d["experience"]), d["experience"]

blank = parse_details("")
assert blank["name"] == "" and blank["headline"] == "" and blank["location"] == "" and blank["experience"] == []
one = parse_details("Jane Roe\n")
assert one["name"] == "Jane Roe" and one["experience"] == [] and one["location"] == ""

# with no experience section, fall back to the summary line
only_summary = parse_details("Ann Lee\nSUMMARY\nSenior data engineer with ten years.\n")
assert only_summary["headline"].startswith("Senior data engineer"), only_summary["headline"]

# no profile URL -> fall back to the first line rather than failing
d2 = parse_details("JAMIE LEE\nAustin, Texas, United States\nEXPERIENCE\nEngineer 2020 - 2023\nInitech\n")
assert d2["name"] == "Jamie Lee", d2["name"]
assert d2["experience"][0]["org"] == "Initech"

# a phone number line must not be mistaken for a location
d3 = parse_details("Bob Ross\n+1 555 0199, 0200\nEXPERIENCE\n")
assert d3["location"] == "", d3["location"]
print("resume parsing tests PASS")
