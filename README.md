# Hourly US AI / ML / Data Engineer Monitor

Scheduled GitHub Actions job checks public employer ATS APIs every hour and emails newly discovered matching postings.

**Roles:** AI/ML Engineer, ML Engineer, Applied AI Engineer, LLM Engineer, GenAI Engineer, Data Engineer.
**Experience:** 2–5 years when an explicit requirement is available.
**Location:** US-only, with conservative location matching.
**Feeds:** Greenhouse, Lever, Ashby, SmartRecruiters (company identifier required).
**Sources:** employer-direct application URLs; no aggregator scraping.

## Activate
1. Keep this GitHub repository **private**. GitHub Actions will commit `jobs.sqlite3` to preserve history.
2. In Settings → Secrets and variables → Actions add `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_TO`. Gmail normally uses `smtp.gmail.com`, port `465`, and an app password.
3. Settings → Actions → General: enable **Read and write permissions**.
4. Merge the implementation PR to `main`, then open Actions → Hourly direct ATS job monitor → Run workflow.
5. The initial scan builds a baseline without emailing old listings. Check the `scan-report` artifact for broken/inactive ATS board slugs.
6. Later successful scans send new matches. Failed feeds do not prevent other boards from being scanned.

## Notes on accuracy
- The **35 board slugs returned successful API responses** in the first live run (2026-10-28); 15 invalid candidates were removed after HTTP 404 errors. Live feed health is still rechecked hourly. The workflow creates a validation report on every scan; remove failed slugs after confirming actual employer ATS links.
- A newly found posting is **not necessarily published within 60 minutes**. Ashby may supply `publishedAt`; Lever `createdAt` is not publication proof. The email distinguishes `published_within_60m` from `first_discovered_time_unverified`.
- This monitor **does not check LinkedIn or Jobright** to prove that a job has not been indexed there.
- US matching and years-of-experience extraction are conservative and may omit good matches. Review description before applying.
- Workday's tenant-specific public pages are not implemented as a universal connector; avoid undocumented scraping bypasses.
- GitHub's hourly scheduler is best effort, not an exact-time SLA. SMTP and live ATS connectivity require real-workflow verification.
- State is stored in a committed SQLite file for a small private monitor, not a multi-user production database.
- If email delivery fails, unalerted matches are eligible for retry on the next successful scan.
- Secrets must never be committed.

## Development
```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python monitor.py --validate-only
python monitor.py --dry-run
```
