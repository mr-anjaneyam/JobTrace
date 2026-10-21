import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobtrace.seniority import (
    apply_cap,
    extract_required_years,
    is_junior_title,
    is_mid_title,
    is_senior_title,
)


def test_seniority_title_detection():
    assert is_senior_title("Senior Software Engineer")
    assert is_senior_title("Staff Engineer")
    assert is_senior_title("Principal Architect")
    assert is_senior_title("Software Engineer III")
    assert is_senior_title("Director of Engineering")

    assert is_mid_title("Fullstack Software Engineer, II")
    assert is_mid_title("Software Engineer II")
    assert is_mid_title("SDE 2")
    assert not is_mid_title("Senior Software Engineer II")  # Senior wins
    assert is_senior_title("Software Engineering SMTS")
    assert is_senior_title("Software Engineering PMTS")
    assert is_senior_title("Software Development Engineer 4")

    assert is_junior_title("Software Engineer Intern")
    assert is_junior_title("Junior Full-Stack Developer")
    assert is_junior_title("New Grad Software Engineer")
    assert is_junior_title("Software Development Engineer 1")
    assert is_junior_title("SDE 1")

    # Junior marker wins
    assert not is_senior_title("Senior Engineering Intern")
    assert is_junior_title("Senior Engineering Intern")
    print("[OK] seniority title detection passes")


def test_extract_required_years():
    assert extract_required_years("4+ years experience with JavaScript/TypeScript") == 4.0
    assert extract_required_years("Requires minimum 3 years of software experience") == 3.0
    assert extract_required_years("5-7 years of professional development experience") == 5.0
    assert extract_required_years("At least 2 years in Python and AWS") == 2.0
    assert extract_required_years("Company with 10 years of history in finance. Requires 1 year of experience in Python.") == 1.0
    assert extract_required_years("No specific requirements mentioned") is None
    print("[OK] extract_required_years passes")


def test_configurable_seniority_caps():
    # 1. Target = Junior / Intern: senior roles capped at 3
    s, r = apply_cap(9, "Senior Backend Engineer", "strong fit", target_seniority="junior")
    assert s == 3
    assert "senior role for junior target" in r

    # Junior role for junior target is UNTOUCHED
    s, r = apply_cap(9, "Software Engineer Intern", "strong fit", target_seniority="junior")
    assert s == 9

    # 2. Hard experience requirement gating from description:
    # 4+ years requires cap at 2 for junior candidate
    bd = {"skills": 100, "seniority": 90}
    s, r = apply_cap(
        10,
        "Fullstack Software Engineer, II",
        "Perfect fit",
        target_seniority="junior",
        description="4+ years experience with JavaScript/TypeScript and supporting libraries",
        candidate_years=1.2,
        breakdown=bd,
    )
    assert s == 2, f"Expected 2 for 4+ yrs requirement on junior candidate, got {s}"
    assert "requires 4+ yrs experience" in r
    assert bd["seniority"] <= 20

    # 3+ years requires cap at 3 for junior candidate
    s, r = apply_cap(
        9,
        "Software Engineer",
        "Good fit",
        target_seniority="junior",
        description="Minimum 3 years of industry experience required",
        candidate_years=1.0,
    )
    assert s == 3
    assert "requires 3+ yrs experience" in r

    # Mid-level II role with no years stated capped at 5
    s, r = apply_cap(
        9,
        "Software Engineer, II",
        "Good fit",
        target_seniority="junior",
    )
    assert s == 5
    assert "mid-level II role" in r

    # 3. Target = Senior: Senior roles are UNTOUCHED!
    s, r = apply_cap(9, "Senior Backend Engineer", "strong fit", target_seniority="senior")
    assert s == 9, f"Senior role must NOT be capped for senior candidate! Got: {s}"

    # But low-level intern roles for senior candidate are capped
    s, r = apply_cap(9, "Software Engineer Intern", "strong fit", target_seniority="senior")
    assert s == 3
    assert "intern/entry role for senior target" in r

    # 4. Target = Any: No roles are capped
    s, _ = apply_cap(9, "Senior Director of Sales", "test", target_seniority="any")
    assert s == 9
    s, _ = apply_cap(9, "Software Engineer Intern", "test", target_seniority="any")
    assert s == 9

    print("[OK] configurable seniority caps pass")


if __name__ == "__main__":
    test_seniority_title_detection()
    test_extract_required_years()
    test_configurable_seniority_caps()
    print("All seniority tests PASSED!")
