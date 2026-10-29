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
        if not rank.isdecimal() or not (1<=int(rank)<=500) or not company:
            continue
        domain=domain.strip()
        if not domain:
            continue
        if "://" not in domain:
            domain="https://"+domain
        parsed=urlparse(domain)
        if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password:
            continue
        # Visit just the official root, not a stale recorded final-url path.
        homepage="https://"+parsed.hostname.lower().strip(".")+"/"
        items[int(rank)]={"company":company,"url":homepage,"fortune_rank":int(rank),
                          "registry":"fortune500_2026"}
    if len(items)!=500:
        raise ValueError("Expected exactly 500 ranks with company+domain; got %d. Check upstream CSV columns."%len(items))
    return [items[i] for i in range(1,501)]
