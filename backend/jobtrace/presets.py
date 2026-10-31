"""Ready-made company lists per country.

Every entry was checked against the live career API and has open roles located in that country.
Boards come and go, so a company that starts failing only shows up as a warning in the scan log.
"""
from __future__ import annotations

from . import geo


def _c(name: str, board: str, slug: str, domain: str) -> dict:
    return {"name": name, "board": board, "slug": slug, "domain": domain}


INDIA = [
    # Indian companies and scale-ups
    _c("Paytm", "lever", "paytm", "paytm.com"),
    _c("Meesho", "lever", "meesho", "meesho.com"),
    _c("CRED", "lever", "cred", "cred.club"),
    _c("Zeta", "lever", "zeta", "zeta.tech"),
    _c("Mindtickle", "lever", "mindtickle", "mindtickle.com"),
    _c("Hevo Data", "lever", "hevodata", "hevodata.com"),
    _c("InMobi", "greenhouse", "inmobi", "inmobi.com"),
    _c("HighRadius", "greenhouse", "highradius", "highradius.com"),
    _c("Groww", "greenhouse", "groww", "groww.in"),
    _c("Zenoti", "greenhouse", "zenoti", "zenoti.com"),
    _c("Sigmoid", "greenhouse", "sigmoid", "sigmoid.com"),
    _c("Druva", "greenhouse", "druva", "druva.com"),
    _c("Observe.AI", "greenhouse", "observeai", "observe.ai"),
    _c("Tekion", "ashby", "tekion", "tekion.com"),
    _c("Sarvam AI", "ashby", "sarvam", "sarvam.ai"),
    _c("Atlan", "ashby", "atlan", "atlan.com"),
    # Global companies with large engineering teams in India
    _c("Okta", "greenhouse", "okta", "okta.com"),
    _c("MongoDB", "greenhouse", "mongodb", "mongodb.com"),
    _c("Zscaler", "greenhouse", "zscaler", "zscaler.com"),
    _c("Pure Storage", "greenhouse", "purestorage", "purestorage.com"),
    _c("Rubrik", "greenhouse", "rubrik", "rubrik.com"),
    _c("Netskope", "greenhouse", "netskope", "netskope.com"),
    _c("GitLab", "greenhouse", "gitlab", "gitlab.com"),
    _c("Toast", "greenhouse", "toast", "toasttab.com"),
    _c("Elastic", "greenhouse", "elastic", "elastic.co"),
    _c("Agoda", "greenhouse", "agoda", "agoda.com"),
    _c("Commvault", "greenhouse", "commvault", "commvault.com"),
    _c("Datadog", "greenhouse", "datadog", "datadoghq.com"),
    _c("Twilio", "greenhouse", "twilio", "twilio.com"),
    _c("Airbnb", "greenhouse", "airbnb", "airbnb.com"),
    _c("Coinbase", "greenhouse", "coinbase", "coinbase.com"),
    _c("OpenAI", "ashby", "openai", "openai.com"),
    _c("Snowflake", "ashby", "snowflake", "snowflake.com"),
    _c("Mastercard", "workday", "mastercard/wd1/CorporateCareers", "mastercard.com"),
    _c("Intel", "workday", "intel/wd1/External", "intel.com"),
    _c("Micron", "workday", "micron/wd1/External", "micron.com"),
    _c("Cadence", "workday", "cadence/wd1/External_Careers", "cadence.com"),
    _c("Cisco", "workday", "cisco/wd5/Cisco_Careers", "cisco.com"),
    _c("NXP", "workday", "nxp/wd3/careers", "nxp.com"),
    _c("Analog Devices", "workday", "analogdevices/wd1/External", "analog.com"),
    _c("Wells Fargo", "workday", "wf/wd1/WellsFargoJobs", "wellsfargo.com"),
    _c("Citi", "workday", "citi/wd5/2", "citi.com"),
    _c("State Street", "workday", "statestreet/wd1/Global", "statestreet.com"),
    _c("HPE", "workday", "hpe/wd5/Jobsathpe", "hpe.com"),
    _c("HP", "workday", "hp/wd5/ExternalCareerSite", "hp.com"),
    _c("Autodesk", "workday", "autodesk/wd1/Ext", "autodesk.com"),
    _c("BlackRock", "workday", "blackrock/wd1/BlackRock_Professional", "blackrock.com"),
    _c("Workday", "workday", "workday/wd5/Workday", "workday.com"),
    _c("JPMorgan Chase", "oracle", "jpmc.fa.oraclecloud.com/CX_1001", "jpmorganchase.com"),
]

COMPANIES: dict[str, list[dict]] = {"india": INDIA}


def companies_for(country: str | None) -> list[dict]:
    return [dict(c) for c in COMPANIES.get(geo.normalize_country(country), [])]


def add_missing(cfg: dict, country: str | None) -> list[str]:
    """Append the country's preset companies that are not in the config yet; returns the names added."""
    have = {str(c.get("name", "")).strip().lower() for c in cfg.get("companies") or []}
    added: list[str] = []
    for entry in companies_for(country):
        if entry["name"].lower() not in have:
            cfg.setdefault("companies", []).append(entry)
            added.append(entry["name"])
    return added
