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
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import yaml
import monitor
from github_watch import fetch_watchlist
from wide_sources import jobicy, nomads, simplify

NOW = datetime.now(timezone.utc)
OUTPUT = Path("job_results")
OUTPUT.mkdir(exist_ok=True)
MAX_SUMMARY_ROWS = 180


def parse_iso(value):
    return monitor.dateparse(value)


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


def assess_new(job, checkpoint, existing):
    """Return status only if this is new relative to prior run."""
    posted = job.get("published")
    # Employer source-reported publication time, not tracker-created timestamp.
    if job.get("ats") in ("greenhouse", "ashby", "smartrecruiters"):
        if posted and posted.tzinfo and checkpoint:
            # Employer-supplied posting time overrides vague discovery status.
            # Do not call an older publication "new" merely because the
            # monitor has never seen that company/job ID before.
            if posted > NOW or posted <= checkpoint:
                return None
            previous_published = parse_iso(existing[1]) if existing else None
            if not previous_published or previous_published < posted:
                return "Published since last run (employer timestamp)"
            return None
    if job.get("ats") == "github_tracker":
        if existing:
            return None
        minutes = job.get("github_reported_age_minutes")
        if isinstance(minutes, int):
            if checkpoint and (NOW - checkpoint).total_seconds() < minutes * 60:
                return None
            if checkpoint:
                return "GitHub tracker reports posted since last run (unverified)"
            return "Current GitHub tracker listing (first run; age source-reported)"
        if not checkpoint:
            return "Current GitHub tracker listing (initial run; date unknown)"
        return "Newly discovered on tracker (posting date unverified)"
    # Newly discovered jobs (not necessarily posted since previous run).
    if existing:
        return None
    if not checkpoint:
        return "Current listing (initial baseline, publication time unknown)"
    return "Newly discovered since last run (publication time unknown)"


def safe_link(value):
    value = str(value or "")
    if re.match(r"^https://[^\s<>]+$", value):
        return value.replace("|", "%7C").replace(")", "%29")
    return ""


def safe_cell(value):
    return html.escape(str(value or "").replace("|", " ").replace("\n", " ").replace("\r", " "))


def write_results(rows, checkpoint, source_label, report, failed):
    rows.sort(key=lambda j: (j["status"].startswith("Published"), j["score"]), reverse=True)
    fields = ["company", "title", "location", "source", "published_utc", "first_seen_utc",
              "score", "relevance", "status", "apply_url"]
    with (OUTPUT / "jobs_since_last_run.csv").open("w", newline="", encoding="utf-8-sig") as out:
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        for item in rows:
            writer.writerow({field: item.get(field, "") for field in fields})
    (OUTPUT / "jobs_since_last_run.json").write_text(
        json.dumps({"scan_utc":monitor.iso(NOW), "previous_scan_utc":monitor.iso(checkpoint),
                    "checkpoint_basis":source_label, "results":rows, "feed_health":report},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    published=sum(x["status"].startswith("Published") for x in rows)
    discovered=len(rows)-published
    lines = [
        "# Jobs found since your last run",
        "",
        f"**Scan:** {monitor.iso(NOW)} UTC",
        f"**Previous checkpoint:** {monitor.iso(checkpoint) or 'None'} ({source_label})",
        f"**Results:** {len(rows)} unique matching roles · {published} employer-timestamped publications · {discovered} newly discovered or baseline listings",
        f"**Feeds:** {len(report)-len(failed)}/{len(report)} succeeded",
        "",
        "Jobs with employer publication timestamps are marked separately from listings **first discovered** by this monitor. "
        "A GitHub job list's posting age is not independent proof of an employer's original posting time. "
        "The full list, including application URLs, is in the CSV and JSON artifacts below this workflow run.",
        "",
        f"### Results (first {min(len(rows),MAX_SUMMARY_ROWS)} of {len(rows)})",
        "",
        "| Company | Role | Location | Recency | Source | Apply |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows[:MAX_SUMMARY_ROWS]:
        url=safe_link(row["apply_url"])
        link=f"[Open]({url})" if url else "Unavailable"
        lines.append("| " + " | ".join([
            safe_cell(row["company"]),safe_cell(row["title"]),safe_cell(row["location"]),
            safe_cell(row["status"]),safe_cell(row["source"]),link
        ]) + " |")
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
                found=jobicy(monitor.SESSION)
            elif board["ats"]=="workingnomads":
                found=nomads(monitor.SESSION)
            elif board["ats"]=="github_simplify":
                found=simplify(monitor.SESSION)
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
                first_seen=current[0] if current else monitor.iso(NOW)
                published=monitor.iso(job.get("published"))
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
                result.append({"company":job["company"],"title":job["title"],
                               "location":job.get("location",""),"source":job.get("source") or board["ats"],
                               "published_utc":published or "",
                               "first_seen_utc":first_seen,"score":job.get("score",0),
                               "relevance":job.get("relevance",""),"status":status,"apply_url":url})
        total,published,discovered=write_results(result,checkpoint,checkpoint_basis,health,failed)
        # If ANY feed fails, do not advance the global checkpoint: the next manual
        # run can recover the missed published-time interval for that feed.
        # Individual jobs are still persisted, and deduplication prevents repeats.
        if not failed:
            db.execute("INSERT INTO metadata(key,value) VALUES('manual_last_success',?) "
                       "ON CONFLICT(key) DO UPDATE SET value=excluded.value",(monitor.iso(NOW),))
        db.commit()
    finally:
        db.close()
    logging.info("Sources %s/%s OK; eligible=%s; results=%s; published=%s; discovered=%s",
                 len(health)-len(failed),len(health),eligible_count,total,published,discovered)
    if failed:
        logging.warning("Some sources failed; checkpoint not advanced. Inspect feed_health.json.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
