"""Only alert when source supplies a trustworthy public publication/release time."""
from datetime import datetime, timezone, timedelta

PUBLISH_TIME_ATS = frozenset(("greenhouse", "ashby", "smartrecruiters"))

def published_last_hour(job, now=None):
    now = now or datetime.now(timezone.utc)
    timestamp = job.get("published")
    source = job.get("ats")
    if source not in PUBLISH_TIME_ATS or not isinstance(timestamp, datetime):
        return False
    if timestamp.tzinfo is None:
        return False
    age = now.astimezone(timezone.utc) - timestamp.astimezone(timezone.utc)
    return timedelta(0) <= age <= timedelta(minutes=60)

def timestamp_class(job):
    if job.get("ats") == "ashby":
        return "Last published by employer (may include republication)"
    if job.get("ats") == "greenhouse":
        return "Employer first-published timestamp"
    if job.get("ats") == "smartrecruiters":
        return "Employer release timestamp"
    return "No verified employer publication timestamp"
