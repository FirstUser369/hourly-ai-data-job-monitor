"""Optional public, attributed USA job sources."""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup

CACHE=Path("provider_cache/jobicy.json")
def plain(x):return BeautifulSoup(str(x or ""),"html.parser").get_text(" ",strip=True)
def parse_jobicy(data):
    if not isinstance(data,dict) or not isinstance(data.get("jobs"),list):raise ValueError("Jobicy response malformed")
    out=[]
    for j in data["jobs"]:
        u=j.get("url") or ""
        if not str(u).startswith("https://") or not j.get("jobTitle"):continue
        out.append(dict(ats="jobicy",id=str(j.get("id") or u),company=j.get("companyName") or "Unknown",
            title=j["jobTitle"],location=j.get("jobGeo") or "Remote",description=plain(j.get("jobDescription") or j.get("jobExcerpt")),
            url=u,published=None,country=None,source="Jobicy",employer_direct=False))
    return out
def jobicy(session,now=None):
    now=now or datetime.now(timezone.utc)
    if CACHE.exists():
        try:
            c=json.loads(CACHE.read_text(encoding="utf-8"))
            previous=datetime.fromisoformat(c["fetched"])
            if timedelta(0)<=now-previous<timedelta(hours=1):
                return parse_jobicy({"jobs":c["jobs"]})
        except (ValueError,KeyError,TypeError):pass
    items=[];cursor=None
    for _ in range(7):
        args={"count":200,"geo":"usa"}
        if cursor:args["cursor"]=cursor
        r=session.get("https://jobicy.com/api/jobs",params=args,timeout=(8,30));r.raise_for_status()
        data=r.json()
        if not isinstance(data,dict) or data.get("success") is False or not isinstance(data.get("jobs"),list):
            raise ValueError("Jobicy response malformed")
        items.extend(data["jobs"])
        cursor=data.get("nextCursor")
        if not cursor:break
    CACHE.parent.mkdir(parents=True,exist_ok=True)
    CACHE.write_text(json.dumps({"fetched":now.isoformat(),"jobs":items}),encoding="utf-8")
    return parse_jobicy({"jobs":items})
def parse_nomads(data):
    if not isinstance(data,list):raise ValueError("Working Nomads response malformed")
    out=[]
    for j in data:
        u=j.get("url") or ""
        if not str(u).startswith("https://") or not j.get("title"):continue
        out.append(dict(ats="workingnomads",id=u,company=j.get("company_name") or "Unknown",
          title=j["title"],location=j.get("location") or "Remote",description=plain(j.get("description")),
          url=u,published=None,country=None,source="Working Nomads",employer_direct=False))
    return out
def nomads(session):
    r=session.get("https://www.workingnomads.com/api/exposed_jobs/",timeout=(8,30));r.raise_for_status()
    return parse_nomads(r.json())
def parse_simplify(raw):
    doc=BeautifulSoup(raw,"html.parser");results=[];company=""
    for tr in doc.find_all("tr"):
        cells=tr.find_all("td",recursive=False)
        if len(cells)!=5:continue
        name=cells[0].get_text(" ",strip=True)
        if name and name not in ("↳","↪"):company=name.replace("🔥","").strip()
        title=cells[1].get_text(" ",strip=True);location=cells[2].get_text(" ",strip=True)
        application=cells[3]
        if "🔒" in application.get_text(" ",strip=True):continue
        links=[a.get("href") for a in application.find_all("a",href=True)]
        links=[u for u in links if u.startswith("https://") and not (urlparse(u).hostname or "").endswith("simplify.jobs")]
        if not links or not title or not company:continue
        u=links[0]
        results.append(dict(ats="github_simplify",id=u,company=company,title=title,
           location=location,description="",url=u,published=None,country=None,
           source="SimplifyJobs/New-Grad-Positions",employer_direct=True,
           reported_age=cells[4].get_text(" ",strip=True)))
    return results
def simplify(session):
    r=session.get("https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md",timeout=(10,35))
    r.raise_for_status()
    return parse_simplify(r.text)
