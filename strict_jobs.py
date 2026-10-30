"""Strict latest-jobs verification; no third-party first-seen claims."""
from datetime import datetime,timedelta,timezone
from urllib.parse import urlparse
import requests

TRUSTED=frozenset(("greenhouse","ashby","smartrecruiters"))
MAX_AGE=timedelta(hours=48)
CLOSED=("this job is no longer available","this job is no longer accepting",
        "job posting is no longer available","position has been filled",
        "this position is no longer available","this role is no longer available",
        "this job has expired","the job you are looking for is no longer",
        "we are no longer accepting applications for this position")

def recent_employer_post(job, now, checkpoint=None, existing_published=None):
    if job.get("ats") not in TRUSTED:
        return False
    posted=job.get("published")
    if not isinstance(posted,datetime) or not posted.tzinfo:
        return False
    if posted>now or now-posted>MAX_AGE:
        return False
    # Rolling 48h dashboard: previously seen but still current jobs stay visible.
    return True

def verify_application(job,session=None,allow_aggregators=False):
    """Active public ATS presence plus reachable job-specific application page.

    Rejected when blocked or ambiguous: an HTTP 200 alone is insufficient if
    the destination is a generic company careers page or displays closed text.
    """
    if job.get("ats") not in TRUSTED and not allow_aggregators:
        return False,"not employer ATS"
    url=str(job.get("url") or "")
    parts=urlparse(url)
    if parts.scheme!="https" or not parts.hostname or parts.username or parts.password:
        return False,"invalid URL"
    try:
        client=session if session is not None else requests
        response=client.get(url,timeout=(6,12),allow_redirects=True)
        if response.status_code!=200:
            return False,"HTTP "+str(response.status_code)
        final=urlparse(str(response.url or ""))
        if final.scheme!="https" or not final.hostname:
            return False,"bad redirect"
        original_path=parts.path.rstrip("/").lower()
        new_path=final.path.rstrip("/").lower()
        if new_path in ("","/jobs","/careers","/join-us") and original_path not in ("","/jobs","/careers","/join-us"):
            return False,"redirected to generic careers page"
        content=str(response.text or "")[:300000].lower()
        if any(marker in content for marker in CLOSED):
            return False,"posting closed message"
        return True,"Current employer ATS and reachable application page"
    except (requests.RequestException,TypeError,ValueError) as exc:
        return False,type(exc).__name__
