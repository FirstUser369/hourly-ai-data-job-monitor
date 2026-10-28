"""Public GitHub job lists. Report age comes from tracker, NOT employer publication."""
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import requests

ZAPPLY = "https://raw.githubusercontent.com/zapplyjobs/New-Grad-Jobs-2027/main/README.md"
ML_LIST = "https://raw.githubusercontent.com/Tar-ive/ML_Newgrad_2027/main/data/listings.json"

def reported_minutes(label):
    label=(label or "").strip().lower()
    # Reject dates, "today", hour-rounded listings and unknown ages to maintain <60 min precision.
    match=re.fullmatch(r"(\d+)\s*(?:m|min|mins|minutes?)",label)
    if match:
        n=int(match.group(1))
        return n if 0<=n<60 else None
    return None

def parse_zapply(markdown):
    """Read genuine six-column README rows. The source's Posted ages are approximations."""
    results=[]
    for line in markdown.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells=[c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells)!=6:
            continue
        company, title, location, age, visa, apply=cells
        minutes=reported_minutes(age)
        if minutes is None:
            continue
        urls=re.findall(r"\]\((https://[^)\s]+)\)",apply)
        if not urls:
            continue
        url=urls[-1]
        if not urlparse(url).hostname:
            continue
        company=BeautifulSoup(company.replace("**",""),"html.parser").get_text(" ",strip=True)
        title=BeautifulSoup(title.replace("**",""),"html.parser").get_text(" ",strip=True)
        if not title or not company:
            continue
        results.append(dict(
            ats="github_zapply", company=company, id=url, title=title,
            location=location, description="", url=url, published=None,
            source="zapplyjobs/New-Grad-Jobs-2027",
            github_reported_age_minutes=minutes, freshness_kind="github_reported_age",
            employer_direct=False, country=None))
    return results

def parse_ml_list(data):
    """Use a verifier's employer-posted timestamp only if the source marked it live.
    Its timestamp is still third-party reported; label it honestly.
    """
    if not isinstance(data,list):
        raise ValueError("Expected ML tracker list")
    results=[]
    for entry in data:
        if not isinstance(entry,dict) or not entry.get("active",False) or entry.get("is_usa") is not True:
            continue
        proof=entry.get("verification") or {}
        if proof.get("status")!="live" or proof.get("via") not in ("greenhouse","ashby","smartrecruiters"):
            continue
        posted=proof.get("posted")
        if not isinstance(posted,(int,float)) or posted<=0:
            continue
        url=entry.get("apply_url") or entry.get("url") or ""
        if not str(url).startswith("https://"):
            continue
        try:
            published=datetime.fromtimestamp(posted,tz=timezone.utc)
        except (ValueError,OverflowError,OSError):
            continue
        locations=entry.get("locations") or []
        description=str(proof.get("evidence") or "")
        results.append(dict(
            ats="github_ml_tracker", company=entry.get("company") or "Unknown",
            id=str(entry.get("id") or url),title=entry.get("title") or "",
            location=", ".join(locations), description=description, url=url,
            published=published, country="US",
            source="Tar-ive/ML_Newgrad_2027",
            freshness_kind="github_verifier_employer_time",
            employer_direct=True))
    return results

def fetch_watchlist(kind, session):
    if kind=="zapply":
        r=session.get(ZAPPLY,timeout=(10,35))
        r.raise_for_status()
        return parse_zapply(r.text)
    if kind=="ml_tracker":
        r=session.get(ML_LIST,timeout=(10,35))
        r.raise_for_status()
        return parse_ml_list(r.json())
    raise ValueError(f"Unsupported GitHub tracker: {kind}")

def recent_tracker_job(job, now):
    """Tracker age is from source's snapshot; do not treat as verified publication."""
    kind=job.get("freshness_kind")
    if kind=="github_reported_age":
        n=job.get("github_reported_age_minutes")
        return isinstance(n,int) and 0<=n<60
    if kind=="github_verifier_employer_time":
        posted=job.get("published")
        if not isinstance(posted,datetime) or posted.tzinfo is None:
            return False
        age=(now-posted).total_seconds()
        return 0<=age<=3600
    return False

def tracker_basis(job):
    if job.get("freshness_kind")=="github_reported_age":
        return "GitHub tracker says posted <60m; NOT independently employer-verified"
    if job.get("freshness_kind")=="github_verifier_employer_time":
        return "GitHub tracker reports verified employer posting time; independently unconfirmed"
    return "Unverified tracker time"
