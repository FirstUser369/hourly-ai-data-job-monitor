# On-demand US AI / ML / Data job finder

**No automatic hourly runs. No job-alert emails.** Click **Run workflow** whenever you want to see jobs added since your previous run.

## Current behavior: balanced sources, STRICT since-last-run interval

Each manual run compares source time evidence against the timestamp saved by the **previous completed manual search**. Only source times strictly after that checkpoint and no later than this scan can qualify. Previously seen 1–2-day-old jobs are **not repeated** merely because they remain online. Discovering an old listing for the first time is not evidence that it was newly posted.

All supported sources are queried: public Greenhouse, Lever, Ashby and SmartRecruiters employer APIs, remote boards (including Himalayas, Remote OK, Jobicy, Arbeitnow and Working Nomads), and public GitHub job trackers (Zapply, ML Newgrad, Simplify and ApplyGuy). A source needs a usable timestamp or sufficiently precise approximate-age label to qualify. Undated jobs are excluded rather than misrepresented as new.

The workflow Summary separates **employer-timestamped**, **third-party-reported** and **Himalayas recently updated** listings. The last category is **NOT confirmation that the job was originally posted since the previous scan**: Himalayas `pubDate` reports last update. GitHub minute/hour labels and other third-party date claims are not independently verified. Each entry includes an application URL that must pass a public link check, or for Himalayas, the provider's official live-job API check. Blocked or uncertain links fail closed. Availability can change after the scan.

The Summary round-robins sources so one job board doesn't dominate the first page; the CSV/JSON contain **every qualifying nonduplicate result** without arbitrary per-provider quotas. Your preferred experience priority remains 3–4 years first, then 0–2, then 5; explicit 6+ year requirements excluded. If a job doesn't state a requirement, its experience is marked unspecified.

## How to run it

1. Go to **Actions → Find AI/Data jobs since my last run** in this repository.
2. Click **Run workflow**, select `main`, and optionally check **Update public employer career feeds before searching**.
3. Open the completed run and view the **job table in the Summary** (up to 180 rows).
4. Under **Artifacts**, download `jobs-since-last-run-<run ID>`. It contains:
   - `job_results/jobs_since_last_run.csv` — complete Excel-ready list, sortable and filterable
   - `job_results/jobs_since_last_run.json` — full structured results
   - `job_results/results_summary.md` — the table as Markdown
   - `job_results/feed_health.json` — failures and source counts

The scan includes the direct employer boards and supplementary remote/GitHub feeds listed above; the optional discovery step adds validated company ATS boards.

## What counts as new

The run uses the previous completed scan timestamp, not a rolling 48-hour window. Freshness source labels and application status checks are reported separately. **No previous checkpoint** means no posting can be labeled as posted *since* a previous run; run once to establish the baseline. Failed feeds are reported, but a completed search advances the checkpoint so jobs from healthy feeds are not repeated in later runs. If a provider fails, its jobs may be missed until their timestamps fall inside a subsequent requested interval; the workflow does not invent time evidence.

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

## Fortune 500 (2026) company career discovery

In addition to the 139 AI-focused candidate career pages, the optional discovery step now loads **all 500 companies** from a published 2026 Fortune 500 company/domain dataset (Installmap, September 2026, CC BY 4.0), deduplicates homepage domains, and attempts to follow **real careers links** exposed on those company homepages. The dataset citation and import errors are recorded in `career_discovery_report.json`. Data source: https://installmap.com/static/data/fortune-100-ai-homepage/fortune500.csv ; original ranking: https://fortune.com/ranking/fortune500/.

The manual workflow's checkbox **Discover AI companies + Fortune 500 (2026) public career feeds before searching** defaults to enabled. It checks up to 800 combined pages with 16 parallel workers. This does *not* mean that 500 independent jobs feeds have been verified: individual sites may use Workday, custom JavaScript career portals or an application-wall; only publicly linked and validated Greenhouse, Lever, Ashby and SmartRecruiters boards are added to `discovered_boards.yml`. Company discovery validates public ATS feeds. Fortune 500 Workday and custom portals may still need additional adapters; a discovered company is not automatically a live, searchable job feed.

If the Fortune dataset is inaccessible or malformed, discovery shows an import failure rather than silently treating fewer companies as 500. The public source list is loaded during the run, not copied or fabricated as career URLs.

### Fortune roster resilience

The published 2026 Fortune 500 dataset can contain all 500 ranked companies but fewer than 500 usable corporate domains. Discovery **preserves all 500 roster entries** and scans every usable homepage instead of discarding the entire list. Missing/invalid domains are explicitly reported in `career_discovery_report.json` under `fortune500_missing_companies`, with each company and rank. If the source itself is unavailable or lacks 500 ranked records, the workflow reports a discovery error rather than silently showing 0/500 as successful. Adding a company to the registry does not prove its jobs are integrated with the strict latest-only job report.

### Last-run filtering and Fortune data irregularities

The finder now compares each source's timestamp evidence with the previous completed manual scan. It does not replay a rolling 48-hour list. The Fortune registry loader tolerates duplicated source ranks and reports missing ranks without inventing companies. Employer links are checked before reporting.

