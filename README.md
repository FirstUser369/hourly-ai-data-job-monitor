# On-demand US AI / ML / Data job finder

**No automatic hourly runs. No job-alert emails.** Click **Run workflow** whenever you want to see jobs added since your previous run.

## How to run it

1. Go to **Actions → Find AI/Data jobs since my last run** in this repository.
2. Click **Run workflow**, select `main`, and optionally check **Update public employer career feeds before searching**.
3. Open the completed run and view the **job table in the Summary** (up to 180 rows).
4. Under **Artifacts**, download `jobs-since-last-run-<run ID>`. It contains:
   - `job_results/jobs_since_last_run.csv` — complete Excel-ready list, sortable and filterable
   - `job_results/jobs_since_last_run.json` — full structured results
   - `job_results/results_summary.md` — the table as Markdown
   - `job_results/feed_health.json` — failures and source counts

The scan still includes **Greenhouse, Lever, Ashby, SmartRecruiters, Remote OK, Himalayas, Arbeitnow, and two GitHub job trackers**, plus any employer boards discovered from `career_pages.yml`.

## What "since the last run" actually means

The monitor saves a last-successful-manual-run timestamp in the existing private `jobs.sqlite3` file. On the first run after upgrading, it uses the latest timestamp from the older job-monitor database. On each subsequent successful run, the checkpoint advances.

Results have **honest recency labels**:
- **Published since last run (employer timestamp)**: a trusted employer feed explicitly reports a publication time later than the previous checkpoint; when reposted, this may reflect a subsequent release.
- **GitHub tracker reports posted since last run (unverified)**: the GitHub source reports an age of minutes, hours, days, or weeks, indicating an approximate posting time within the selected interval. This is not independently verified.
- **Newly discovered since last run (publication time unknown)**: absent from the saved job history, with no reliable original posting timestamp. These roles may actually have existed earlier.

A previously seen job is normally suppressed; unique identities are tracked in SQLite and duplicate company/role/location combinations are removed within each report. The full list is stored in CSV/JSON; the GitHub run Summary shows the first 180.

**First-time setup:** If no earlier history exists, the initial run displays a baseline of current matching listings and labels the date limitation rather than calling them newly posted. The first run after this upgrade can include all jobs in newly added GitHub feeds. If a feed fails, the scan reports the failure and does not move the global checkpoint, so a later run can recover skipped publications.

## Matching preferences

Target US and US-eligible remote roles in AI, ML, applied AI, LLMs, data science, data engineering, analytics, BI, MLOps, and adjacent software/platform work. Preference is ~2–5 years, with missing years allowed; internship, staff, principal and director roles are excluded. The relevance matcher uses title + description where available and scores the best matches first.

GitHub sources:
- [zapplyjobs/New-Grad-Jobs-2027](https://github.com/zapplyjobs/New-Grad-Jobs-2027): reads the README's six-column job tables, including posting-age labels and Apply links (may redirect through Zapply).
- [Tar-ive/ML_Newgrad_2027](https://github.com/Tar-ive/ML_Newgrad_2027): reads structured job records; only jobs with supported verification evidence qualify for a published time. This tracker may become unavailable or change format.

## Maintenance and limits

The scanner uses public feeds and configured employer career pages. It is not a comprehensive index of every US employer. Github-age labels can be stale; direct ATS publication timestamps are not always exposed. New jobs posted and removed between two manual scans may never be observed. Careers discovered on JavaScript-only or nonpublic pages require additional supported adapters.

**Keep the GitHub repository private**, because its job history is committed to source control. Allow **Read and write permissions** under Settings → Actions → General. The pre-existing SMTP secrets are no longer used by the main job finder; the standalone `Send test email` workflow remains separate.

Run the unit tests locally with `python -m unittest discover -s tests -v` after installing `requirements.txt`.
