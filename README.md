# US AI / ML / Data Job Monitor — strict last-hour alerts

## Most important rule

**The hourly email contains only matching jobs with an employer-reported publication or release timestamp in the 60 minutes preceding that scan.** The monitor never treats `first_seen`, an update timestamp, a job-board crawl time, or "newly discovered" as evidence that a listing was published in the last hour.

Supported employer publication signals:
- **Greenhouse:** `first_published`, when exposed by the public response.
- **Ashby:** `publishedAt`, the *last* published event (can include a republished older role).
- **SmartRecruiters:** `releasedDate`, when exposed in public job details.

Sources without reliable employer publication timestamps (including Lever, Remote OK, Himalayas, and Arbeitnow) are **not eligible for strict last-hour email alerts**. They remain available for feed discovery and validation, but an API's success does not imply that its jobs can pass the strict timestamp rule. Missing, future, and older timestamps are excluded. This deliberate accuracy-first choice means **some genuine newly posted jobs will be missed**, particularly if the source doesn't disclose publication time or GitHub delays a run.

## Relevant roles

Scoring matches across ML engineering, generative AI, LLMs, MLOps, AI platform, NLP, computer vision, data science, data engineering, analytics, BI and adjacent engineering work. There is no strict requirement that job titles match an exact phrase. The preference is roughly 2–5 years; missing years is allowed. Roles are US or potentially US-eligible remote, per conservative location heuristics.

The system deduplicates jobs in the private SQLite history database and sends **at most 40** high-ranked, newly eligible published-within-last-hour postings per digest. Items with no reliable publication timestamp are NEVER emailed in this mode. SMTP must be configured in repository secrets; previous Gmail test has verified delivery.

## Employer careers expansion (bounded and safe)

No reliable service can read **every company's career website in the United States every hour**, and most career systems do not expose verified original posting times. Rather than claiming that, this repository includes a **weekly, opt-in company career-page discovery workflow**:

1. Add official employer careers URLs to `career_pages.yml` (15 initial examples; URLs can change).
2. Run Actions → **Hourly AI/Data job monitor + career discovery** → **Run workflow**, and check the `discover_career_pages` option when you want to include career-page discovery. A weekly scheduled check also runs Sunday 07:41 UTC.
3. The career-page discovery step in the unified workflow scans only these configured public landing pages for linked Greenhouse, Lever, Ashby, and SmartRecruiters company ATS boards. It validates API responses and commits `discovered_boards.yml`. It retains previously discovered feeds if a page temporarily fails.
4. The hourly scanner automatically reads both `boards.yml` and `discovered_boards.yml` and deduplicates board identifiers.
5. Review the `career-discovery-report-...` artifact to learn which company career pages were processed.

Discovery is limited to public links and scripts visible in the HTML. JavaScript-only career pages, Workday tenants, and sites without public ATS feeds need custom, permitted integrations. **Finding a feed is not the same as verifying an hourly publication timestamp**. Lever career feeds can be discovered but are excluded from strict-hour alerts unless a reliable publication signal becomes available.

To add more US companies, extend `career_pages.yml` with their official careers landing URLs. The job monitor does not autonomously enumerate all US employers.

## Run and verify

- Actions → **Hourly AI/Data job monitor + career discovery** → Run workflow on `main`. For a manual run choose whether to also discover career pages; otherwise it just scans jobs. Cron scans twice hourly at minutes 13 and 43 UTC, with discovery plus scan every Sunday at 07:41 UTC; GitHub may delay scheduled runs. The default branch is monitored.
- The existing **Send test email** workflow remains separate so SMTP can be tested without changing job history.
- Download the hourly **scan-report** artifact and inspect `last_run.json`, especially `verified_timestamp_jobs`, `posted_last_60_minutes`, `eligible_seen`, `new_matches`, and `boards_failed`.
- First successful run after this change reuses the existing saved baseline; no reset.
- GitHub repository should remain **private** because `jobs.sqlite3` is stored in version control.
- Repository Settings → Actions → General: **Read and write permissions**.
- Actions secrets: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_TO`. Gmail: `smtp.gmail.com`, SSL port `465`, Google App Password.

Local testing:
```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python monitor.py --dry-run
python career_discovery.py
```

## Technical boundaries

ATS boards can change without notice. Failed feeds are logged, and successful feeds continue. Discovery honors public surfaces without bypassing authentication. Employer publication timestamps can reflect first publication or republishing depending on ATS. Strict filtering is a **rolling 60-minute window**, not proof of first appearance online or absence from LinkedIn/Jobright. Scheduled GitHub Actions jobs are best effort and can miss windows if severely delayed.
