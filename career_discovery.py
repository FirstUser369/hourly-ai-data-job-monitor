"""Discover public employer ATS board identifiers from configured careers pages.

This is a bounded and opt-in company registry, NOT an internet-wide crawler.
Does not bypass login, robots restrictions, or JS security controls.
"""
import json
import logging
import re
from pathlib import Path
from urllib.parse import urlparse
import ipaddress
import requests
import yaml
from bs4 import BeautifulSoup

ALLOWED = {
    "boards.greenhouse.io":"greenhouse",
    "job-boards.greenhouse.io":"greenhouse",
    "jobs.lever.co":"lever",
    "jobs.ashbyhq.com":"ashby",
    "jobs.smartrecruiters.com":"smartrecruiters",
}
SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,90}$")
USER_AGENT = "PersonalJobMonitor/1.0 public employer careers discovery"

def safe_url(url):
    parts=urlparse(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        return False
    host=parts.hostname.lower()
    if host in ("localhost",) or host.endswith((".localhost",".local",".internal")):
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        return True

def board_from_url(url, company):
    if not safe_url(url):
        return None
    parts=urlparse(url)
    ats=ALLOWED.get(parts.hostname.lower())
    segments=[segment for segment in parts.path.split("/") if segment]
    if ats and segments and SLUG.fullmatch(segments[0]):
        return {"ats":ats,"slug":segments[0],"company":company}
    return None

def parse_careers_html(html, final_url, company):
    candidates=[final_url]
    doc=BeautifulSoup(html,"html.parser")
    for tag in doc.find_all(["a","iframe","script","link"]):
        for attribute in ("href","src"):
            uri=tag.get(attribute)
            if uri:
                from urllib.parse import urljoin
                candidates.append(urljoin(final_url,uri))
    # Public embeds may store the ATS URL as a plain text string.
    candidates.extend(re.findall(r"https://(?:job-boards[.]greenhouse[.]io|boards[.]greenhouse[.]io|jobs[.]lever[.]co|jobs[.]ashbyhq[.]com|jobs[.]smartrecruiters[.]com)/[A-Za-z0-9_-]+",html,re.I))
    found={}
    for candidate in candidates:
        board=board_from_url(candidate,company)
        if board:
            found[(board["ats"],board["slug"])]=board
    return list(found.values())

def validate_public_feed(session,board):
    ats,slug=board["ats"],board["slug"]
    if ats=="greenhouse":
        url=f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    elif ats=="lever":
        url=f"https://api.lever.co/v0/postings/{slug}?mode=json"
    elif ats=="ashby":
        url=f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    elif ats=="smartrecruiters":
        url=f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=1"
    else:
        return False
    try:
        r=session.get(url,timeout=(6,15))
        r.raise_for_status()
        data=r.json()
        return isinstance(data,(dict,list))
    except (requests.RequestException,ValueError):
        return False

def main():
    registry=Path("career_pages.yml")
    if not registry.exists():
        raise SystemExit("Add employer careers pages in career_pages.yml")
    companies=(yaml.safe_load(registry.read_text(encoding="utf-8")) or {}).get("companies",[])
    session=requests.Session()
    session.headers["User-Agent"]=USER_AGENT
    confirmed={}
    report=[]
    for record in companies[:100]:
        company=str(record.get("company") or "").strip()
        url=str(record.get("url") or "").strip()
        if not company or not safe_url(url):
            report.append({"company":company,"status":"invalid input"})
            continue
        try:
            response=session.get(url,timeout=(8,20),allow_redirects=True)
            response.raise_for_status()
            if not safe_url(response.url):
                raise ValueError("unsafe redirect target")
            if len(response.content)>2_000_000:
                raise ValueError("career landing page too large")
            matches=parse_careers_html(response.text,response.url,company)
            for board in matches:
                if validate_public_feed(session,board):
                    confirmed[(board["ats"],board["slug"])]=board
            report.append({"company":company,"status":"checked","candidates":len(matches)})
        except (requests.RequestException,ValueError) as exc:
            logging.warning("Career page failed %s: %s",company,type(exc).__name__)
            report.append({"company":company,"status":"failed","error":type(exc).__name__})
    # No failed discovery should wipe previously validated entries.
    output=Path("discovered_boards.yml")
    old=(yaml.safe_load(output.read_text(encoding="utf-8")) or {}).get("boards",[]) if output.exists() else []
    for board in old:
        if board.get("ats") in ALLOWED.values() and SLUG.fullmatch(str(board.get("slug") or "")):
            confirmed.setdefault((board["ats"],board["slug"]),board)
    output.write_text(yaml.safe_dump({"boards":list(confirmed.values())},sort_keys=False),encoding="utf-8")
    Path("career_discovery_report.json").write_text(json.dumps({"configured_pages":len(companies),"validated_boards":len(confirmed),"pages":report},indent=2),encoding="utf-8")
    print(f"Checked {len(companies)} configured career pages; {len(confirmed)} validated discovered boards.")
if __name__=="__main__":
    main()
