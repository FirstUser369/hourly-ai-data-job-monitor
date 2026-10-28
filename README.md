# Hourly US AI/Data Engineering Job Monitor

1. Create a **private** GitHub repository and upload these files, preserving `.github/workflows/hourly.yml`.
2. Edit `boards.yml` with real company ATS board slugs (examples are not guaranteed live).
3. Set GitHub Settings > Secrets and variables > Actions > New repository secret:
   - `SMTP_HOST` e.g. `smtp.gmail.com`
   - `SMTP_PORT` e.g. `587`
   - `SMTP_USER` sender email
   - `SMTP_PASSWORD` SMTP app password (not your regular account password)
   - `ALERT_TO` recipient email
4. In Settings > Actions > General set Workflow permissions to **Read and write permissions**.
5. Run Actions > Hourly ATS job monitor > Run workflow to establish baseline.
6. Subsequent scheduled runs at minute 17 UTC will email new matches. GitHub may delay scheduled workflows.

## Caveats
- Greenhouse `first_published` and Lever `createdAt` are used when supplied. Ashby public feeds may not provide a reliable publication timestamp; such matches are labeled newly discovered, not verified published in the last hour.
- Strict experience matching may miss roles without explicit 2–5 year statements. Requirements with multiple numbers may be conservatively excluded.
- Location heuristic excludes ambiguous remote-anywhere jobs and may miss US cities not listed. Review and extend the location rules.
- The early-listing flag is **not** a verified LinkedIn/Jobright absence check. No board-index comparison is performed.
- SQLite is committed to a private repo for persistence; this is a simple MVP, not an enterprise database. Keep the repo private.
- First run baselines matching jobs without emailing. Avoid deleting the SQLite file or it will baseline again.
- `first_seen` on retry candidates is the retry timestamp in the email, not the original DB first-seen time; inspect SQLite for the original value.
- Employer board API availability, field names and terms may change. Check workflow logs for failed boards.
