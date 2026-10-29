"""Discover public employer ATS board identifiers from configured careers pages.

This is a bounded and opt-in company registry, NOT an internet-wide crawler.
Does not bypass login, robots restrictions, or JS security controls.
"""
import json
import os
import logging
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
import ipaddress
import requests
import yaml
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from fortune500_registry import load_fortune500, SOURCE as FORTUNE_SOURCE, CREDIT as FORTUNE_CREDIT

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

def career_links(html, origin):
    """Follow actual public career links, never guessed paths."""
    host=urlparse(origin).hostname or ""
    links=[]
    for tag in BeautifulSoup(html,"html.parser").select("a[href]"):
        target=urljoin(origin,tag.get("href") or "")
        if not safe_url(target):
            continue
        target_host=urlparse(target).hostname or ""
        label=tag.get_text(" ",strip=True).lower()
        path=urlparse(target).path.lower()
        same_domain=(target_host==host or target_host.endswith("."+host))
        related=bool(re.search(r"\b(careers?|jobs?|join us|join our team|work with us|open positions|opportunities)\b",label) or re.search(r"/(careers?|jobs?|join-us|opportunities)(?:/|$)",path))
        if same_domain and related and target not in links and target!=origin:
            links.append(target)
    return links[:2]

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
        targets=career_links(resp.text,resp.url) if record.get("registry")=="fortune500_2026" else []
        for target in targets:
            try:
                another=session.get(target,timeout=(5,12),allow_redirects=True)
                another.raise_for_status()
                if safe_url(another.url) and len(another.content)<=2_000_000:
                    potential.extend(parse_careers_html(another.text,another.url,company))
            except (requests.RequestException,ValueError):
                pass
        potential=list({(b["ats"],b["slug"]):b for b in potential}.values())
        verified=[board for board in potential if validate_public_feed(session,board)]
        return verified,{"company":company,"url":url,"status":"verified_feed" if verified else "no_public_ats_found",
                         "potential_feeds":len(potential),"career_links_checked":len(targets),"verified_feed_count":len(verified)}
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
    try:
        fortune=load_fortune500()
        fortune_error=None
    except (requests.RequestException,ValueError,UnicodeError) as exc:
        fortune=[]
        fortune_error=type(exc).__name__+": "+str(exc)
        logging.error("Fortune 500 import unavailable: %s",fortune_error)
    registered={urlparse(str(item.get("url") or "")).hostname for item in companies}
    # Preserve missing-domain Fortune records as explicit unresolved entries.
    additional=[item for item in fortune if not item.get("url") or urlparse(item["url"]).hostname not in registered]
    missing_domains=[item for item in fortune if not item.get("url")]
    all_companies=companies+additional
    with ThreadPoolExecutor(max_workers=16) as pool:
        results=list(pool.map(inspect_page,all_companies[:800]))
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
    summary={"configured_pages":len(companies),"fortune500_year":2026,"fortune500_source":FORTUNE_SOURCE,
             "fortune500_credit":FORTUNE_CREDIT,"fortune500_loaded":len(fortune),
             "fortune500_error":fortune_error,"fortune500_added":len(additional),
             "fortune500_domain_unresolved":len(missing_domains),
             "fortune500_missing_companies":[{"rank":item["fortune_rank"],"company":item["company"]} for item in missing_domains],
             "total_candidates":len(all_companies),"checked_pages":len(report),"verified_this_run":newly_verified,
             "validated_boards_total":len(confirmed),
             "no_public_ats_found":sum(x["status"]=="no_public_ats_found" for x in report),
             "failed_pages":sum(x["status"]=="failed" for x in report),"pages":report}
    Path("career_discovery_report.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print("Fortune roster: %s/500 entries; %s missing/invalid domains" % (len(fortune),len(missing_domains)))
    print("Career discovery: %s pages checked; %s verified ATS feeds found; %s total known; %s failed" %
          (len(report),newly_verified,len(confirmed),summary["failed_pages"]))
    summary_file=os.getenv("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file,"a",encoding="utf-8") as handle:
            handle.write("\n### Employer career-page discovery\n\n")
            handle.write(f"- Candidate employer pages checked: **{len(report)}**\n")
            handle.write(f"- Fortune 500 roster entries loaded: **{len(fortune)}/500**\n")
            handle.write(f"- Fortune 500 entries with no usable official homepage: **{len(missing_domains)}**\n")
            handle.write(f"- Public ATS feeds validated this run: **{newly_verified}**\n")
            handle.write(f"- Validated feeds retained in registry: **{len(confirmed)}**\n")
            handle.write(f"- Pages without visible public ATS: **{summary['no_public_ats_found']}**\n")
            handle.write(f"- Failed career pages: **{summary['failed_pages']}**\n\n")
            handle.write("For per-company statuses, download career_discovery_report.json in this run's artifact.\n")
if __name__=="__main__":
    main()
