import pytest

from jobtrace import geo, pipeline, presets, sources
from jobtrace.relevance import apply_location_cap


@pytest.mark.parametrize("location", [
    "Bengaluru, Karnataka, India", "Pune", "Hyderabad, Telangana", "IND Bangalore", "Remote - India",
    "San Francisco; Bengaluru", "Delhi NCR", "Gurgaon, Haryana", "India",
])
def test_india_locations_match(location):
    assert geo.location_in_country(location, "india")


@pytest.mark.parametrize("location", [
    "Indianapolis, IN", "Indiana, USA", "Remote - US", "London, UK", "Berlin", "New York, NY",
    "Singapore", "Remote, Canada", "Austin, TX, United States", "Remote",
])
def test_other_locations_do_not_match(location):
    assert not geo.location_in_country(location, "india")


@pytest.mark.parametrize("location", ["", "   ", "2 Locations", "Multiple Locations"])
def test_unknown_locations_are_kept(location):
    assert geo.location_in_country(location, "india")


def test_global_remote_needs_opt_in():
    for loc in ("Remote", "Anywhere", "Worldwide", "Remote - APAC"):
        assert not geo.location_in_country(loc, "india")
        assert geo.location_in_country(loc, "india", include_remote=True)
    # a remote role tied to another country stays out either way
    assert not geo.location_in_country("Remote - US", "india", include_remote=True)
    assert not geo.location_in_country("Hybrid - New York", "india", include_remote=True)


def test_country_aliases_and_blank():
    assert geo.normalize_country("India") == "india"
    assert geo.normalize_country("IND") == "india"
    assert geo.location_in_country("Paris", "")  # no country means anywhere


def test_country_target_covers_every_city():
    assert geo.matches_target("India", "Pune")
    assert geo.matches_target("Bengaluru", "Bengaluru, India")
    assert not geo.matches_target("India", "Berlin")


def test_target_locations_adds_filter_country():
    cfg = {"candidate": {"locations": ["Remote"]}, "filters": {"country": "india"}}
    assert geo.target_locations(cfg) == ["Remote", "India"]
    assert geo.target_locations({"filters": {"country": "india"}}) == ["India"]
    assert geo.target_locations({"candidate": {"locations": ["Pune", "india"]}, "filters": {"country": "India"}}) == ["Pune", "india"]


def test_location_cap_respects_country_and_unknown():
    kept, _ = apply_location_cap(9, "Mysuru", ["India"], breakdown={})
    assert kept == 9
    kept, _ = apply_location_cap(9, "2 Locations", ["India"], breakdown={})
    assert kept == 9
    capped, reason = apply_location_cap(9, "Berlin", ["India"], breakdown={})
    assert capped < 9 and "location mismatch" in reason


def test_passes_filters_with_country():
    job = {"title": "Backend Engineer", "location": "Pune, India"}
    filters = {"title_include": ["engineer"], "country": "india"}
    assert pipeline.passes_filters(job, filters)
    assert not pipeline.passes_filters({**job, "location": "Austin, TX"}, filters)
    assert pipeline.passes_filters({**job, "location": "Remote"}, {**filters, "include_remote": True})
    assert not pipeline.passes_filters({**job, "location": "Remote"}, filters)
    # without a country nothing changes
    assert pipeline.passes_filters({**job, "location": "Austin, TX"}, {"title_include": ["engineer"]})


def test_pipeline_searches_by_country(tmp_path, monkeypatch):
    from jobtrace.store import Store

    seen = []

    def fake_fetch(entry, keyword=""):
        seen.append(keyword)
        jobs = [
            {"id": "a", "company": "Acme", "title": "Engineer", "url": "https://a/1", "location": "Pune, India",
             "posted_at": None, "description": "python", "source": "workday", "domain": "", "matches_filter": True},
            {"id": "b", "company": "Acme", "title": "Engineer", "url": "https://a/2", "location": "Austin, TX",
             "posted_at": None, "description": "python", "source": "workday", "domain": "", "matches_filter": True},
        ]
        return jobs, None

    monkeypatch.setattr(sources, "fetch_company", fake_fetch)
    store = Store(tmp_path / "t.db")
    cfg = {
        "companies": [{"name": "Acme", "board": "workday", "slug": "acme/wd1/x"}],
        "discovery": {"enabled": False},
        "filters": {"title_include": ["engineer"], "country": "india"},
        "llm": {"provider": "none"},
    }
    pipeline.run_pipeline(cfg=cfg, store=store, root_dir=tmp_path, quiet=True)
    assert seen == ["India"]
    rows = {r["id"]: r["matches_filter"] for r in store.db.execute("SELECT id, matches_filter FROM jobs")}
    assert rows == {"a": 1, "b": 0}

    seen.clear()
    cfg["filters"]["include_remote"] = True
    pipeline.run_pipeline(cfg=cfg, store=store, root_dir=tmp_path, quiet=True)
    assert seen == [""]  # global remote roles need the unfiltered listing


def test_presets_are_well_formed():
    entries = presets.companies_for("India")
    assert len(entries) > 30
    names = [e["name"].lower() for e in entries]
    assert len(names) == len(set(names))
    for e in entries:
        assert e["board"] in sources.BOARDS
        assert e["slug"] and e["domain"]


def test_add_missing_keeps_existing_companies():
    cfg = {"companies": [{"name": "okta", "board": "greenhouse", "slug": "okta"}]}
    added = presets.add_missing(cfg, "india")
    assert "Okta" not in added and "Paytm" in added
    assert sum(1 for c in cfg["companies"] if c["name"].lower() == "okta") == 1
    assert presets.add_missing(cfg, "india") == []
    assert presets.add_missing(cfg, "atlantis") == []
