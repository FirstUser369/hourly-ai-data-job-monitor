"""Additional public remote job feeds; aggregator links retain attribution.
These are supplementary discovery sources, not employer-direct ATS feeds.
"""
import re
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from datetime import datetime,timezone

def textify(s):
    return BeautifulSoup(s or '', 'html.parser').get_text(' ',strip=True)

def get(session,url,params=None):
    r=session.get(url,params=params,timeout=(8,25))
    r.raise_for_status()
    return r.json()

def remoteok(session):
    data=get(session,'https://remoteok.com/api')
    if not isinstance(data,list):raise ValueError('RemoteOK response not a list')
    for j in data:
        if not isinstance(j,dict) or not j.get('id') or not j.get('position'):continue
        url=j.get('url') or ''
        if not str(url).startswith('https://'):continue
        location=j.get('location') or 'Remote worldwide'
        yield dict(company=j.get('company','Unknown'),ats='remoteok',id=str(j['id']),title=j['position'],
            location=location,description=textify(j.get('description')),url=url,
            published=None,updated=None,country=None,source='Remote OK',employer_direct=False)

def himalayas(session):
    # Broader search across the technical landscape instead of exact job titles.
    seen=set()
    for query in ('data','machine learning','AI','analytics','platform engineer'):
      for page in range(1,4):
        data=get(session,'https://himalayas.app/jobs/api/search',
            {'q':query,'country':'US','sort':'recent','page':page})
        jobs=data.get('jobs') or []
        if not isinstance(jobs,list):raise ValueError('Himalayas malformed jobs response')
        if not jobs:break
          for j in jobs:
              if not isinstance(j,dict):continue
              uid=str(j.get('guid') or j.get('applicationLink') or '')
              if not uid or uid in seen:continue
              seen.add(uid)
              url=j.get('applicationLink') or uid
              if not str(url).startswith('https://'):continue
              restrictions=j.get('locationRestrictions') or []
              loc='Remote, United States' if not restrictions else 'Remote, '+ ', '.join(str(z) for z in restrictions[:5])
              yield dict(company=j.get('companyName','Unknown'),ats='himalayas',id=uid,title=j.get('title',''),
                location=loc,description=textify(j.get('description')),url=url,
                published=None,updated=None,country='US',source='Himalayas',employer_direct=False)

def arbeitnow(session):
    """Public board with mainly European jobs; US/wider remote filtering happens downstream."""
    seen=set()
    for page in range(1,4):
        data=get(session,'https://www.arbeitnow.com/api/job-board-api',{'page':page})
        items=data.get('data') or []
        if not isinstance(items,list):raise ValueError('Arbeitnow malformed jobs feed')
        for j in items:
            uid=str(j.get('slug') or j.get('url') or '')
            if not uid or uid in seen:continue
            seen.add(uid)
            url=j.get('url') or ''
            if not str(url).startswith('https://'):continue
            yield dict(company=j.get('company_name','Unknown'),ats='arbeitnow',id=uid,title=j.get('title',''),
              location=j.get('location') or ('Remote worldwide' if j.get('remote') else ''),
              description=textify(j.get('description')),url=url,published=None,updated=None,country=None,
              source='Arbeitnow',employer_direct=False)
        if not items:break
