import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobtrace.sources import _job_id, normalize_url


def test_url_normalization():
    # Strips tracking params
    raw1 = "https://boards.greenhouse.io/stripe/jobs/12345?gh_jid=12345&utm_source=linkedin&utm_medium=job_post"
    clean1 = normalize_url(raw1)
    assert clean1 == "https://boards.greenhouse.io/stripe/jobs/12345"

    raw2 = "https://jobs.lever.co/spotify/abc-def?lever-source=glassdoor"
    clean2 = normalize_url(raw2)
    assert clean2 == "https://jobs.lever.co/spotify/abc-def"

    # Preserves clean query parameters that are not tracking params
    raw3 = "https://example.com/careers?dept=engineering&city=sf"
    clean3 = normalize_url(raw3)
    assert "dept=engineering" in clean3 and "city=sf" in clean3

    print("✓ URL normalization passes")


def test_job_id_stability():
    # URLs with different tracking params must yield the EXACT same job ID!
    u1 = "https://jobs.ashbyhq.com/notion/abc?utm_source=twitter"
    u2 = "https://jobs.ashbyhq.com/notion/abc?utm_source=email&utm_campaign=oct"

    id1 = _job_id("Notion", "Software Engineer", normalize_url(u1))
    id2 = _job_id("Notion", "Software Engineer", normalize_url(u2))
    assert id1 == id2, f"Job IDs must match despite different UTM parameters: {id1} != {id2}"

    print("✓ job ID stability passes")


if __name__ == "__main__":
    test_url_normalization()
    test_job_id_stability()
    print("All sources tests PASSED!")
