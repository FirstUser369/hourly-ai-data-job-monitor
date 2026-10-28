# US AI / ML / Data Job Monitor — strict last-hour alerts

## Most important rule

**Employer ATS alerts require a publication or release timestamp in the preceding 60 minutes. GitHub watchlist alerts use separately labeled tracker-reported recency, not independent employer timestamps.** The monitor never treats `first_seen`, an update timestamp, a job-board crawl time, or "newly discovered" as evidence that a listing was published in the last hour.

Supported employer publication signals:
- **Greenhouse:** `first_published`, when exposed by the public response.
- **Ashby:** `publishedAt`, the *last* published event (can include a republished older role).
- **SmartRecruiters:** `releasedDate`, when exposed in public job details.

Other feeds without reliable employer publication timestamps (including Lever, Remote OK, Himalayas, and Arbeitnow) are **not eligible for employer-confirmed last-hour alerts**. They remain available for feed discovery and validation, but an API's success does not imply that its jobs can pass the strict timestamp rule. Missing, future, and older timestamps are excluded. This deliberate accuracy-first choice means **some genuine newly posted jobs will be missed**, particularly if the source doesn't disclose publication time or GitHub delays a run.

## Relevant roles

Scoring matches across ML engineering, generative AI, LLMs, MLOps, AI platform, NLP, computer vision, data science, data engineering, analytics, BI and adjacent engineering work. There is no strict requirement that job titles match an exact phrase. The preference is roughly 2–5 years; missing years is allowed. Roles are US or potentially US-eligible remote, per conservative location heuristics.

The system deduplicates jobs in the private SQLite history database and sends **at most 40** high-ranked, newly eligible published-within-last-hour postings per digest. Items with no reliable employer timestamp are not emailed from ATS feeds; tracker-reported GitHub recency is a separately labeled exception. SMTP must be configured in repository secrets; previous Gmail test has verified delivery.

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

## GitHub job-list watchlists (new)

Besides employer ATS feeds, the same hourly monitor now reads two public, frequently updated GitHub job repositories:

- [zapplyjobs/New-Grad-Jobs-2027](https://github.com/zapplyjobs/New-Grad-Jobs-2027): parses actual six-column markdown job rows with minute-level age labels (for example, \`22m\`, \`59m\`); only those below 60 minutes qualify. Values such as \`1h\`, \`today\`, unknown, or older do NOT qualify. Its apply links may be **Zapply redirects**, not employer-direct application URLs. Labels are **tracker-reported**, not employer verified.
- [Tar-ive/ML_Newgrad_2027](https://github.com/Tar-ive/ML_Newgrad_2027): reads structured \`data/listings.json\`, requires active US role with a "live" verification from Greenhouse, Ashby, or SmartRecruiters and an exact tracker-reported employer posting timestamp within 60 minutes. Direct application URL is preferred. This verifier is **third-party**, not an independent assertion by our monitor.

No additional GitHub credentials are required. Both feeds run as part of the existing hourly GitHub Actions workflow. They are **two extra sources** on top of the original 46, giving 48 configured feeds. Source failures are recorded individually; remaining sources continue.

**Two distinct freshness standards:** employer ATS alerts use the provider's actual timestamp; GitHub job tracker alerts use the source's reported time or reported employer verification. Every email labels the distinction, including the source and whether the link is an employer-direct URL. GitHub listings can be added late, backdated, or inaccurate. The tracker timestamp cannot prove that an opening first appeared on an employer's website within the last hour. If you want ONLY independently confirmed employer publications, remove the two \`github_tracker\` rows from \`boards.yml\`.

Job matching remains broad, but internships, principal/staff/director roles, and non-US listings are still screened out. Title-only GitHub entries without a full description are inherently less certain about the exact years required. The normal SQLite alert deduplication and Gmail settings are unchanged.

The GitHub Actions automatic schedule is **separate from data ingestion**. An integration that identifies more jobs cannot fix an absent \`schedule\` run. Verify the Actions run event is \`schedule\`, not \`workflow_dispatch\`; if GitHub still skips it, an approved external trigger may be necessary. GitHub's built-in cron scheduling is best effort.
