# Hourly AI / ML / Data Opportunity Monitor

Automated hourly discovery from **35 previously live-validated employer ATS feeds**, plus three supplementary public job boards: **Remote OK**, **Himalayas**, and **Arbeitnow** (46 configured feeds in total including eight new SmartRecruiters employer candidates). An employer ATS is the best source for early direct-apply links; secondary boards expand company coverage but are not necessarily early.

## Broader relevance matching

This version matches **fields and skills**, not exact job titles: machine learning, generative AI, NLP, computer vision, data platforms, ETL, analytics engineering, data science, experimentation, business intelligence, research engineering, platform engineering with AI/data technologies, MLOps, etc. It scores a job using the title and description. **2–5 years is preferred**, not a hard requirement, and missing experience numbers no longer reject a job. Internships and explicitly senior management/staff/principal roles are still excluded. US and worldwide-remote options can qualify.

Up to **40 distinct highest-scored matches** are emailed per successful scan; unsent new matches remain pending. Each email includes its relevance rationale, first-seen timestamp, publication-time classification, provider/source name, and link. Employer ATS feeds link directly to employers; Remote OK and Himalayas links follow their respective feed terms. This system does **not** prove a listing is absent from LinkedIn/Jobright, and secondary feeds can have publication/cache delays.

## Safety and transition

The old SQLite job history remains unchanged. On the first scan after deploying broader matching, the monitor **baselines the newly expanded job pool without emailing older results**. Subsequent scans alert on first-seen new matches, even if the provider supplies no trustworthy publish timestamp. The `first_seen` timestamp indicates **discovery by this monitor**, not guaranteed publication time. This initial rescan may take longer than earlier runs.

The provider-specific APIs can return errors or change without notice. Each scan writes `validation_report.json` and `last_run.json`, uploaded as a GitHub Actions artifact. Failed feeds do not stop other working sources. The three new supplementary feeds have **not yet been live-validated in this repository** and their health needs to be checked after merge.

## Email setup

Repository Settings → Secrets and variables → Actions:
`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_TO`.

For Gmail, use `smtp.gmail.com`, port `465`, and a Google App Password. Preserve Actions → General → **Read and write permissions**, because the history database is committed to the private repository.

## Run

Actions → Hourly direct ATS job monitor → Run workflow on `main`. Hourly schedule is at minute 17 UTC, but GitHub scheduling is best effort. The standalone **Send test email** workflow verifies SMTP separately. Tests run before every production scan.

Local:
```shell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python monitor.py --validate-only
python monitor.py --dry-run
```

## Source policy

- Employer ATS feeds: Greenhouse, Lever, Ashby; SmartRecruiters now has eight candidate employer IDs from observed employer posting URLs; these must pass live API checks before claiming active feeds. The adapter fetches descriptions through the documented public detail API and keeps employer posting/apply links.
- Remote OK: public JSON API `https://remoteok.com/api`, source attributed.
- Himalayas: `https://himalayas.app/jobs/api/search`, uses unchanged `applicationLink` and source attribution. Public API cache is refreshed on a daily cadence and can lag new employer postings.
- Remotive was **not** added to hourly checks: its public API is delayed 24 hours and advises at most four checks a day.
- Arbeitnow: public board at `https://www.arbeitnow.com/api/job-board-api`, largely European/remote; only US-eligible listings are considered and source attribution is preserved.
- Workday is not included without a supported per-tenant integration; no bypass of access controls or protected scraping.

If this broad monitor is too noisy, adjust the `min_score` default in `matching.py`; raise it to be more selective, or lower it to increase recall. None of the new providers guarantees US availability without checking the original posting.
