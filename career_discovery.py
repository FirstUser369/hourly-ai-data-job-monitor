"""Discover public employer ATS board identifiers from configured careers pages.

This is a bounded and opt-in company registry, NOT an internet-wide crawler.
Does not bypass login, robots restrictions, or JS security controls.
"""
import json
import logging
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
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

def inspect_page(record):
    company=str(record.get("company") or "").strip()
    url=str(record.get("url") or "").strip()
    if not company or not safe_url(url):
        return [],{"company":company,"url":url,"status":"invalid_input","verified_feed_count":0}
    session=requests.Session()
    session.headers["User-Agent"]=USER_AGENT
    try:
        # Independent sessions per worker; bound redirects/response size and request time.
        resp=session.get(url,timeout=(6,16),allow_redirects=True)
        resp.raise_for_status()
        if not safe_url(resp.url):
            raise ValueError("unsafe redirect")
        if len(resp.content)>2_000_000:
            raise ValueError("HTML landing page too large")
        potential=parse_careers_html(resp.text,resp.url,company)
        verified=[board for board in potential if validate_public_feed(session,board)]
        return verified,{"company":company,"url":url,"status":"verified_feed" if verified else "no_public_ats_found",
                         "potential_feeds":len(potential),"verified_feed_count":len(verified)}
    except (requests.RequestException,ValueError,TypeError) as err:
        logging.warning("Career page %s: %s",company,type(err).__name__)
        return [],{"company":company,"url":url,"status":"failed","error":type(err).__name__,
                   "verified_feed_count":0}
    finally:
        session.close()

def main():
    registry=Path("career_pages.yml")
    if not registry.exists():
        raise SystemExit("Missing career_pages.yml")
    companies=(yaml.safe_load(registry.read_text(encoding="utf-8")) or {}).get("companies",[])
    if not isinstance(companies,list):
        raise ValueError("companies must be a list")
    # More than 100 companies can be checked on a manual run without serial waits.
    with ThreadPoolExecutor(max_workers=10) as pool:
        results=list(pool.map(inspect_page,companies[:200]))
    confirmed={}
    report=[]
    for boards,entry in results:
        report.append(entry)
        for board in boards:
            confirmed[(board["ats"],board["slug"])]=board
    newly_verified=len(confirmed)
    # A transient inaccessible careers site never erases a previously verified feed.
    output=Path("discovered_boards.yml")
    old=(yaml.safe_load(output.read_text(encoding="utf-8")) or {}).get("boards",[]) if output.exists() else []
    if not isinstance(old,list):
        old=[]
    for board in old:
        if board.get("ats") in ALLOWED.values() and SLUG.fullmatch(str(board.get("slug") or "")):
            confirmed.setdefault((board["ats"],board["slug"]),board)
    output.write_text(yaml.safe_dump({"boards":list(confirmed.values())},sort_keys=False),encoding="utf-8")
    summary={"configured_pages":len(companies),"checked_pages":len(report),"verified_this_run":newly_verified,
             "validated_boards_total":len(confirmed),
             "no_public_ats_found":sum(x["status"]=="no_public_ats_found" for x in report),
             "failed_pages":sum(x["status"]=="failed" for x in report),"pages":report}
    Path("career_discovery_report.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print("Career discovery: %s pages checked; %s verified ATS feeds found; %s total known; %s failed" %
          (len(report),newly_verified,len(confirmed),summary["failed_pages"]))
if __name__=="__main__":
    main()
