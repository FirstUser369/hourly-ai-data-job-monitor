"""Fortune 500 (2026) discovery seed list.

Data credited to Installmap (September 2026, CC BY 4.0). This is a
candidate employer-homepage list, not confirmed careers/job board feeds.
Never infer a careers URL by blindly appending /careers.
"""
import csv
import io
from urllib.parse import urlparse
import requests

SOURCE="https://installmap.com/static/data/fortune-100-ai-homepage/fortune500.csv"
CREDIT="Installmap, Fortune 500 2026 domain dataset (2026-09-04), CC BY 4.0"
def load_fortune500(session=None):
    session=session or requests
    response=session.get(SOURCE,timeout=(10,35))
    response.raise_for_status()
    text=response.content.decode("utf-8-sig")
    reader=csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("Fortune dataset missing headers")
    headers={name.lower().strip().replace(" ","_"):name for name in reader.fieldnames}
    def get(row,*names):
        for name in names:
            key=headers.get(name)
            if key and row.get(key):
                return str(row[key]).strip()
        return ""
    items={}
    for row in reader:
        rank=get(row,"rank","fortune_rank","fortune_500_rank")
        company=get(row,"company","name","company_name")
        domain=get(row,"domain","website","url","final_url")
        if not rank.isdecimal() or not (1<=int(rank)<=500):
            continue
        rank=int(rank)
        # Preserve the company's roster entry even when the source has no
        # company domain. Missing domains must not hide the other 498.
        homepage=""
        if domain:
            domain=domain.strip()
            if "://" not in domain:
                domain="https://"+domain
            parsed=urlparse(domain)
            if parsed.scheme=="https" and parsed.hostname and not parsed.username and not parsed.password:
                homepage="https://"+parsed.hostname.lower().strip(".")+"/"
        entry={"company":company or "Fortune rank "+str(rank),
               "url":homepage,"fortune_rank":rank,
               "registry":"fortune500_2026",
               "domain_status":"available" if homepage else "missing_or_invalid"}
        # Upstream can repeat ranks. Keep the first complete row, but prefer
        # a later row when it supplies the missing corporate homepage.
        previous=items.get(rank)
        if previous is None or (not previous["url"] and homepage):
            items[rank]=entry
    # A source with missing/duplicate ranks must still yield usable companies.
    # Missing ranks are recorded by discovery rather than inventing names.
    if not items:
        raise ValueError("Fortune source contained no valid ranked companies")
    return [items[i] for i in sorted(items)]
