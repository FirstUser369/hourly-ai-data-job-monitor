"""Manual job discovery since the last successful manual scan.

Reports exact employer-publication dates separately from newly discovered postings.
Writes GitHub Actions run summary + CSV/JSON results. Does not send email.
"""
import csv
import hashlib
import html
import json
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from email.utils import parsedate_to_datetime

import yaml
import monitor
from github_watch import fetch_watchlist
from wide_sources import jobicy, nomads, simplify, applyguy
from strict_jobs import TRUSTED, recent_employer_post, verify_application

NOW = datetime.now(timezone.utc)
OUTPUT = Path("job_results")
OUTPUT.mkdir(exist_ok=True)
MAX_SUMMARY_ROWS = 180


def parse_iso(value):
    if isinstance(value,datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else None
    dt=monitor.dateparse(value)
    if dt: return dt
    if isinstance(value,str):
        try: return parsedate_to_datetime(value).astimezone(timezone.utc)
        except (ValueError,TypeError,IndexError): return None
    return None


def previous_checkpoint(db):
    row = db.execute("SELECT value FROM metadata WHERE key='manual_last_success'").fetchone()
    if row:
        return parse_iso(row[0]), "previous successful manual job search"
    # Seamless migration from the old scanner's existing job state.
    row = db.execute("SELECT MAX(last_seen) FROM jobs").fetchone()
    if row and row[0]:
        return parse_iso(row[0]), "most recent scan recorded by old monitor"
    return None, "no previous scan (first run)"


def identity(job, board):
    return hashlib.sha256(
        f"{job['ats']}:{board['slug']}:{job['id']}".encode("utf-8")
    ).hexdigest()


def source_time(job, checkpoint):
    """Source proof must be STRICTLY between the previous and current runs."""
    if checkpoint is None or checkpoint>=NOW: return None
    ats=job.get("ats")
    if ats in ("greenhouse","ashby","smartrecruiters"):
        dt=parse_iso(job.get("published")); basis="Employer publication/release"
    elif ats=="lever":
        dt=parse_iso(job.get("published")); basis="Lever posting created time (not necessarily public release)"
    elif ats=="github_ml_tracker":
        dt=parse_iso(job.get("published")); basis="GitHub tracker timestamp (unverified)"
    elif ats=="himalayas":
        dt=parse_iso(job.get("published")); basis="Himalayas updated time (NOT necessarily new)"
    elif ats in ("jobicy","workingnomads","arbeitnow","remoteok"):
        dt=parse_iso(job.get("published")); basis="Third-party posting time (unverified)"
    elif ats=="github_applyguy":
        try:
            day=datetime.strptime(str(job.get("tracker_reported_posted")),"%Y-%m-%d").replace(tzinfo=timezone.utc)
            dt=day if checkpoint<day and day+timedelta(days=1)<=NOW else None
        except ValueError: dt=None
        basis="GitHub date only (unverified)"
    elif ats in ("github_zapply","github_simplify"):
        age=job.get("github_reported_age_minutes")
        if not isinstance(age,int) or age<0: return None
        raw=str(job.get('reported_age') or '').lower()
        margin=1440 if raw.endswith(('d','day','days')) else (10080 if raw.endswith(('w','wk','week','weeks')) else (60 if raw.endswith(('h','hr','hours')) else 1))
        if timedelta(minutes=age+margin)>NOW-checkpoint: return None
        dt=NOW-timedelta(minutes=age); basis="GitHub approximate age (unverified)"
    else: return None
    if ats=="himalayas":
        expires=parse_iso(job.get("expiry"))
        if expires and expires<=NOW: return None
    return (dt,basis) if dt and checkpoint<dt<=NOW else None

def assess_new(job,checkpoint,existing):
    info=source_time(job,checkpoint)
    return info[1] if info else None

def safe_link(value):
    value = str(value or "")
    if re.match(r"^https://[^\s<>]+$", value):
        return value.replace("|", "%7C").replace(")", "%29")
    return ""


def safe_cell(value):
    return html.escape(str(value or "").replace("|", " ").replace("\n", " ").replace("\r", " "))


def write_results(rows, checkpoint, source_label, report, failed):
    # Experience preference takes precedence over recency and relevance score.
    tiers={"experience: 3–4 years (highest priority)":4,
           "experience: 0–2 years (included)":3,
           "experience: 5 years (lower priority)":2,
           "experience not specified":1}
    rows.sort(key=lambda j: (tiers.get(j.get("experience"),0),
                             j["published_utc"], j["score"]), reverse=True)
    # Round-robin the Summary across providers within each experience tier.
    # The CSV/JSON retain ALL qualifying results; do not artificially cap a feed.
    display_rows=[]
    remaining=list(rows)
    while remaining:
        used_sources=set()
        rest=[]
        for item in remaining:
            source=item["source"]
            if source not in used_sources:
                display_rows.append(item)
                used_sources.add(source)
            else:
                rest.append(item)
        remaining=rest
    fields = ["company", "title", "location", "source", "published_utc", "first_seen_utc",
              "score", "experience", "relevance", "status", "freshness_class", "verification", "apply_url"]
    with (OUTPUT / "jobs_since_last_run.csv").open("w", newline="", encoding="utf-8-sig") as out:
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        for item in rows:
            writer.writerow({field: item.get(field, "") for field in fields})
    (OUTPUT / "jobs_since_last_run.json").write_text(
        json.dumps({"scan_utc":monitor.iso(NOW), "previous_scan_utc":monitor.iso(checkpoint),
                    "checkpoint_basis":source_label, "results":rows, "feed_health":report},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    published=sum(x["freshness_class"]=="Employer timestamp" for x in rows)
    discovered=len(rows)-published
    lines=[
        "# Jobs found since your last run", "",
        f"**Scan:** {monitor.iso(NOW)} UTC",
        f"**Previous checkpoint:** {monitor.iso(checkpoint) or 'None'} ({source_label})",
        f"**Results:** {len(rows)} source-timed results ({published} direct employer timestamps; {discovered} other time signals)",
        f"**Feeds:** {len(report)-len(failed)}/{len(report)} succeeded",
        "**Strict interval:** A source timestamp or conservatively estimated tracker age must fall after the previous manual scan. New discovery by itself never qualifies.",
        "Himalayas UPDATE timestamps are not evidence of a newly published job. Approximate GitHub and third-party times are labeled as unverified.",
        "Application links or official source-status endpoints are checked where possible; blocked/uncertain links are omitted.",
        "",
    ]
    groups=[
        ("Employer timestamp","Employer ATS timestamps (highest confidence)"),
        ("Third-party reported","Tracker/aggregator-reported recent postings (unverified)"),
        ("Updated only","Himalayas recently updated listings (not confirmed newly posted)"),
    ]
    shown=0
    for category,heading in groups:
        group=[x for x in display_rows if x.get("freshness_class")==category]
        if not group: continue
        lines.extend([f"### {heading}: {len(group)}", "",
                      "| Company | Role | Location | Experience | Source | Source time (UTC) | Evidence | Apply |",
                      "|---|---|---|---|---|---|---|---|"])
        for row in group[:max(0,MAX_SUMMARY_ROWS-shown)]:
            link=safe_link(row["apply_url"])
            lines.append("| "+" | ".join([
                safe_cell(row["company"]),safe_cell(row["title"]),safe_cell(row["location"]),
                safe_cell(row["experience"]),safe_cell(row["source"]),safe_cell(row["published_utc"]),
                safe_cell(row["status"]),f"[Open]({link})" if link else "Unavailable"])+" |")
            shown+=1
        lines.append("")
    counts=Counter(row["source"] for row in rows)
    if counts:
        lines.extend(["", "### Where these results came from", "",
                      "| Source | Jobs in report |",
                      "|---|---:|"])
        for source,count in counts.most_common():
            lines.append(f"| {safe_cell(source)} | {count} |")
        lines.append("")
        lines.append("These counts describe the current report, not the total jobs available on each site.")
    if not rows:
        lines.extend(["", "**No matching new openings found in the checked feeds.** "
                           "Check the feed-health section below; a successful scan does not guarantee exhaustive US coverage."])
    if failed:
        lines.extend(["", "### Feed failures", "",
                      "The failed sources were not evaluated completely. Results may be incomplete.",
                      ""])
        for entry in failed[:30]:
            lines.append(f"- {safe_cell(entry['company'])}: {safe_cell(entry['error'])}")
    summary="\n".join(lines)+"\n"
    (OUTPUT / "results_summary.md").write_text(summary, encoding="utf-8")
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
            out.write(summary)
    return len(rows),published,discovered


def main():
    with open("boards.yml", encoding="utf-8") as handle:
        boards=yaml.safe_load(handle).get("boards", [])
    extra=Path("discovered_boards.yml")
    if extra.exists():
        boards += (yaml.safe_load(extra.read_text(encoding="utf-8")) or {}).get("boards", [])
    boards += [
        {"ats":"github_tracker","slug":"zapply","company":"Zapply GitHub tracker"},
        {"ats":"github_tracker","slug":"ml_tracker","company":"ML Newgrad GitHub tracker"},
        {"ats":"jobicy","slug":"usa","company":"Jobicy US remote"},
        {"ats":"workingnomads","slug":"all","company":"Working Nomads"},
        {"ats":"github_simplify","slug":"newgrad","company":"SimplifyJobs New Grad Positions"},
        {"ats":"github_applyguy","slug":"newgrad2027","company":"ApplyGuy GitHub direct employer listings"},
    ]
    dedup={(b["ats"],b["slug"]):b for b in boards}
    boards=list(dedup.values())
    if not boards:
        raise RuntimeError("No job sources configured")

    db=monitor.connect()
    checkpoint,checkpoint_basis=previous_checkpoint(db)
    db.close()
    if checkpoint and checkpoint > NOW:
        raise RuntimeError("Previous scan checkpoint is in the future")

    def read_board(board):
        try:
            if board["ats"]=="github_tracker":
                found=fetch_watchlist(board["slug"],monitor.SESSION)
            elif board["ats"]=="jobicy":
                found=jobicy(monitor.SESSION,force_refresh=True)
            elif board["ats"]=="workingnomads":
                found=nomads(monitor.SESSION)
            elif board["ats"]=="github_simplify":
                found=simplify(monitor.SESSION)
            elif board["ats"]=="github_applyguy":
                found=applyguy(monitor.SESSION)
            else:
                found=list(monitor.fetch(board))
            return board,found,None
        except Exception as exc:
            logging.exception("Failed to read %s/%s",board["ats"],board["slug"])
            return board,[],f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=8) as pool:
        fetched=list(pool.map(read_board,boards))
    health=[{"company":board["company"],"ats":board["ats"],"slug":board["slug"],
             "ok":error is None,"jobs":len(jobs),"error":error}
            for board,jobs,error in fetched]
    failed=[x for x in health if not x["ok"]]
    (OUTPUT / "feed_health.json").write_text(json.dumps(health,indent=2),encoding="utf-8")

    db=monitor.connect()
    seen=set()
    result=[]
    eligible_count=0
    closed_or_unverified=0
    try:
        for board,jobs,error in fetched:
            if error:
                continue
            for job in jobs:
                if not isinstance(job,dict):
                    continue
                if not monitor.eligible(job):
                    continue
                url=safe_link(job.get("url"))
                if not url:
                    continue
                eligible_count+=1
                key=identity(job,board)
                current=db.execute("SELECT first_seen,published FROM jobs WHERE key=?",(key,)).fetchone()
                status=assess_new(job,checkpoint,current)
                time_info=source_time(job,checkpoint)
                verification=""
                if status:
                    valid,verification=verify_application(job,allow_aggregators=True)
                    if not valid:
                        closed_or_unverified+=1
                        # Retry unverifiable applications next run; do not mark as seen.
                        continue
                first_seen=current[0] if current else monitor.iso(NOW)
                published=monitor.iso(parse_iso(job.get("published")))
                db.execute("""INSERT INTO jobs(key,company,title,location,url,published,first_seen,last_seen,alerted)
                    VALUES(?,?,?,?,?,?,?,?,0)
                    ON CONFLICT(key) DO UPDATE SET
                    company=excluded.company,title=excluded.title,location=excluded.location,
                    url=excluded.url,published=COALESCE(excluded.published,jobs.published),
                    last_seen=excluded.last_seen""",
                    (key,job["company"],job["title"],job.get("location",""),
                     url,published,first_seen,monitor.iso(NOW)))
                if not status:
                    continue
                # Within one run, suppress repeats of the same role across multiple providers.
                signature=(re.sub(r"\W+","",str(job["company"]).lower()),
                           re.sub(r"\W+","",str(job["title"]).lower()),
                           re.sub(r"\W+","",str(job.get("location","")).lower()))
                if signature in seen:
                    continue
                seen.add(signature)
                experience=next((label for label in str(job.get("relevance","")).split(", ") if label.startswith("experience")), "experience not specified")
                freshness_class=("Employer timestamp" if job["ats"] in ("greenhouse","ashby","smartrecruiters")
                                 else ("Updated only" if job["ats"]=="himalayas" else "Third-party reported"))
                result.append({"company":job["company"],"title":job["title"],
                               "location":job.get("location",""),"source":job.get("source") or board["ats"],
                               "published_utc":monitor.iso(time_info[0]) if time_info else "",
                               "first_seen_utc":first_seen,"score":job.get("score",0),
                               "experience":experience,"relevance":job.get("relevance",""),"status":status,
                               "freshness_class":freshness_class,
                               "verification":verification,"apply_url":url})
        total,published,discovered=write_results(result,checkpoint,checkpoint_basis,health,failed)
        logging.info("Expired, blocked or unverified applications excluded: %s", closed_or_unverified)
        # Every completed job search is a new checkpoint, including partial scans.
        # Failed source counts remain in feed_health.json and Summary.
        db.execute("INSERT INTO metadata(key,value) VALUES('manual_last_success',?) "
                   "ON CONFLICT(key) DO UPDATE SET value=excluded.value",(monitor.iso(NOW),))
        db.commit()
    finally:
        db.close()
    logging.info("Sources %s/%s OK; eligible=%s; results=%s; published=%s; discovered=%s",
                 len(health)-len(failed),len(health),eligible_count,total,published,discovered)
    if failed:
        logging.warning("Some sources failed; checkpoint advanced for the completed scan. Inspect feed_health.json.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
