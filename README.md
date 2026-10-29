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

The scan includes **Greenhouse, Lever, Ashby, SmartRecruiters, Remote OK, Himalayas, Arbeitnow, Jobicy, Working Nomads, SimplifyJobs/New-Grad-Positions, and two GitHub job trackers**, plus any employer boards discovered from `career_pages.yml`.

## What "since the last run" actually means

The monitor saves a last-successful-manual-run timestamp in the existing private `jobs.sqlite3` file. On the first run after upgrading, it uses the latest timestamp from the older job-monitor database. On each subsequent successful run, the checkpoint advances.

Results have **honest recency labels**:
- **Published since last run (employer timestamp)**: a trusted employer feed explicitly reports a publication time later than the previous checkpoint; when reposted, this may reflect a subsequent release.
- **GitHub tracker reports posted since last run (unverified)**: the GitHub source reports an age of minutes, hours, days, or weeks, indicating an approximate posting time within the selected interval. This is not independently verified.
- **Newly discovered since last run (publication time unknown)**: absent from the saved job history, with no reliable original posting timestamp. These roles may actually have existed earlier.

A previously seen job is normally suppressed; unique identities are tracked in SQLite and duplicate company/role/location combinations are removed within each report. The full list is stored in CSV/JSON; the GitHub run Summary shows the first 180. Expanding sources can cause a one-time batch of previously unseen but older jobs, which are labeled **newly discovered (publication time unknown)** rather than published since the previous run.

**First-time setup:** If no earlier history exists, the initial run displays a baseline of current matching listings and labels the date limitation rather than calling them newly posted. The first run after this upgrade can include all jobs in newly added GitHub feeds. If a feed fails, the scan reports the failure and does not move the global checkpoint, so a later run can recover skipped publications.

## Matching preferences

Target US and US-eligible remote roles in AI, ML, applied AI, LLMs, data science, data engineering, analytics, BI, MLOps, and adjacent software/platform work. Experience priority: **3–4 years first**, **0–2 years included**, **5 years included at lower priority**, and **6+ years excluded whenever explicitly stated**. Jobs without a stated requirement remain eligible but are labeled **experience not specified**. Ranges are evaluated using their upper bound (e.g., 3–6 is excluded). Internship, staff, principal and director roles remain excluded. The relevance matcher uses title + description where available, prioritizes the target experience band, and scores the best matches first. The results table and downloaded CSV include an experience classification.

GitHub sources:
- [SimplifyJobs/New-Grad-Positions](https://github.com/SimplifyJobs/New-Grad-Positions): reads open five-column HTML job tables and prefers direct application URLs; the source targets new graduates, and older/internship roles are still filtered by our relevance model.
- [zapplyjobs/New-Grad-Jobs-2027](https://github.com/zapplyjobs/New-Grad-Jobs-2027): reads the README's six-column job tables, including posting-age labels and Apply links (may redirect through Zapply).
- [Tar-ive/ML_Newgrad_2027](https://github.com/Tar-ive/ML_Newgrad_2027): reads structured job records; only jobs with supported verification evidence qualify for a published time. This tracker may become unavailable or change format.

## Maintenance and limits

The scanner uses public feeds and configured employer career pages. Jobicy's public API provides USA-eligible remote listings with pagination and source attribution. The API is cached for at least 60 minutes between manual runs, and the cache is saved in the private GitHub repository. Working Nomads supplies additional remote postings and credits its own listings. SimplifyJobs' public repository provides early-career listings and links directly to external employer posting URLs where available. Its relative age labels are source-reported rather than employer verified. Himalayas is now searched across seven AI/data keyword families and up to six pages each. These sources are not the equivalent of indexing every US employer. It is not a comprehensive index of every US employer. Github-age labels can be stale; direct ATS publication timestamps are not always exposed. New jobs posted and removed between two manual scans may never be observed. Careers discovered on JavaScript-only or nonpublic pages require additional supported adapters.

**Keep the GitHub repository private**, because its job history is committed to source control. Allow **Read and write permissions** under Settings → Actions → General. The pre-existing SMTP secrets are no longer used by the main job finder; the standalone `Send test email` workflow remains separate.

Run the unit tests locally with `python -m unittest discover -s tests -v` after installing `requirements.txt`.

## 139 AI-focused employer career pages (opt-in discovery)

The file [career_pages.yml](career_pages.yml) now contains **139 candidate company career URLs**, grouped by frontier AI/model platforms, cloud/data infrastructure, consumer/fintech marketplaces, and autonomy/robotics/security/enterprise AI. These are candidate links, **not 139 verified active ATS feeds**. Career page URLs can move or be inaccessible; JS-only pages and Workday tenants are not automatically scraped.

To check them, click **Actions → Find AI/Data jobs since my last run → Run workflow** and enable **Update public employer career feeds before searching**. This scans up to 200 configured public pages using up to 10 workers, validates supported linked Greenhouse, Ashby, Lever, and SmartRecruiters feeds, and adds usable feeds to the same job search. The Actions **Summary** reports pages checked, public ATS feeds validated, and failed/no-ATS counts. Download **career_discovery_report.json** for a per-company breakdown. Existing verified feeds are retained when pages fail temporarily.

**Important:** Career discovery is optional and does not query all 139 company job catalogs directly. Workday and proprietary career sites require provider-specific integrations. The new registry is intended to expand coverage incrementally as verifiable feeds are discovered, without inventing coverage.

## Additional employer-direct GitHub discovery

The manual finder also reads [ApplyGuy/2027-New-Grad-Jobs](https://github.com/ApplyGuy/2027-New-Grad-Jobs) via its public structured JSON listing, preferring `listingUrl` (employer application) over the aggregator's intermediary link. The tracker-reported posting date is kept separate and is **not** treated as employer-verified publication time. This expands coverage to Workday and other employer systems without scraping gated pages. The run Summary includes a per-source result count to reveal when any single provider (such as Himalayas) dominates the results.
