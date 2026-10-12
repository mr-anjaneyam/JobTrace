import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobtrace.seniority import apply_cap, is_junior_title, is_senior_title


def test_seniority_title_detection():
    assert is_senior_title("Senior Software Engineer")
    assert is_senior_title("Staff Engineer")
    assert is_senior_title("Principal Architect")
    assert is_senior_title("Software Engineer III")
    assert is_senior_title("Director of Engineering")

    assert is_junior_title("Software Engineer Intern")
    assert is_junior_title("Junior Full-Stack Developer")
    assert is_junior_title("New Grad Software Engineer")

    # Junior marker wins
    assert not is_senior_title("Senior Engineering Intern")
    assert is_junior_title("Senior Engineering Intern")
    print("✓ seniority title detection passes")


def test_configurable_seniority_caps():
    # 1. Target = Junior / Intern: senior roles capped at 3
    s, r = apply_cap(9, "Senior Backend Engineer", "strong fit", target_seniority="junior")
    assert s == 3
    assert "senior role for junior target" in r

    # Junior role for junior target is UNTOUCHED
    s, r = apply_cap(9, "Software Engineer Intern", "strong fit", target_seniority="junior")
    assert s == 9

    # 2. Target = Senior: Senior roles are UNTOUCHED!
    s, r = apply_cap(9, "Senior Backend Engineer", "strong fit", target_seniority="senior")
    assert s == 9, f"Senior role must NOT be capped for senior candidate! Got: {s}"

    # But low-level intern roles for senior candidate are capped
    s, r = apply_cap(9, "Software Engineer Intern", "strong fit", target_seniority="senior")
    assert s == 3
    assert "intern/entry role for senior target" in r

    # 3. Target = Any: No roles are capped
    s, _ = apply_cap(9, "Senior Director of Sales", "test", target_seniority="any")
    assert s == 9
    s, _ = apply_cap(9, "Software Engineer Intern", "test", target_seniority="any")
    assert s == 9

    print("✓ configurable seniority caps pass")


if __name__ == "__main__":
    test_seniority_title_detection()
    test_configurable_seniority_caps()
    print("All seniority tests PASSED!")
