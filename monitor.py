import os, re, json, html, sqlite3, smtplib, hashlib, logging
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from urllib.parse import urlparse
import requests, yaml
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
NOW = datetime.now(timezone.utc)
DB = os.getenv('DB_PATH', 'jobs.sqlite3')
UA = {'User-Agent': 'PersonalJobMonitor/1.0 (low-frequency public ATS feed reader)', 'Accept': 'application/json'}
ROLE = re.compile(r'\b(?:data engineer|machine learning engineer|ml engineer|ai[ /-]?ml engineer|applied ai engineer|llm engineer|generative ai engineer|genai engineer)\b', re.I)
EXPERIENCE = re.compile(r'(?<!\d)(\d{1,2})\s*(?:\+|(?:-|–|to)\s*\d{1,2})?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:relevant\s+|professional\s+|industry\s+)?experience', re.I)
EXPERIENCE_BEFORE = re.compile(r'(?<!\d)(\d{1,2})\s*(?:\+|(?:-|–|to)\s*\d{1,2})?\s*(?:years?|yrs?)\b', re.I)
STATES = re.compile(r'\b(?:USA|U\.S\.|United States|US Remote|Remote - US|Remote, US|Remote \(US\)|Remote \(USA\)|Remote \(United States\)|Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|District of Columbia|Albuquerque|Atlanta|Austin|Baltimore|Boston|Charlotte|Chicago|Cincinnati|Cleveland|Columbus|Dallas|Denver|Detroit|Houston|Indianapolis|Jacksonville|Kansas City|Las Vegas|Los Angeles|Miami|Minneapolis|Nashville|New Orleans|New York City|Orlando|Philadelphia|Phoenix|Pittsburgh|Portland|Raleigh|Sacramento|Salt Lake City|San Antonio|San Diego|San Francisco|San Jose|Seattle|St\. Louis|Tampa|Washington DC)\b', re.I)
STATE_CODES = re.compile(r',\s*(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MS|MN|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b')
EXCLUDE = re.compile(r'\b(?:intern|internship|staff|principal|director|vp|head of|architect|manager)\b', re.I)

def plain(s):
    return BeautifulSoup(html.unescape(s or ''), 'html.parser').get_text(' ', strip=True)

def dateparse(value):
    if not value: return None
    try:
        if isinstance(value, (float, int)):
            return datetime.fromtimestamp(value / 1000 if value > 1e11 else value, timezone.utc)
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError): return None

def get(url):
    r = requests.get(url, headers=UA, timeout=25)
    r.raise_for_status()
    return r.json()

def fetch(board):
    ats, slug, company = board['ats'], board['slug'], board['company']
    if ats == 'greenhouse':
        data = get(f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true')
        for j in data['jobs']:
            yield dict(company=company, ats=ats, id=str(j['id']), title=j['title'], location=(j.get('location') or {}).get('name',''), description=plain(j.get('content')), url=j.get('absolute_url',''), published=dateparse(j.get('first_published')), updated=dateparse(j.get('updated_at')), country=None)
    elif ats == 'lever':
        data = get(f'https://api.lever.co/v0/postings/{slug}?mode=json')
        for j in data:
            cat = j.get('categories') or {}
            yield dict(company=company, ats=ats, id=str(j['id']), title=j['text'], location=', '.join([str(x) for x in (cat.get('allLocations') or [cat.get('location','')]) if x]), description=plain(j.get('descriptionPlain') or j.get('description')), url=j.get('applyUrl') or j.get('hostedUrl',''), published=dateparse(j.get('createdAt')), updated=None, country=j.get('country'))
    elif ats == 'ashby':
        data = get(f'https://api.ashbyhq.com/posting-api/job-board/{slug}')
        for j in data['jobs']:
            if j.get('isListed') is False: continue
            locs = [j.get('location','')] + [x.get('location','') for x in j.get('secondaryLocations',[]) or []]
            country = (j.get('address') or {}).get('postalAddress',{}).get('addressCountry')
            yield dict(company=company, ats=ats, id=str(j.get('id') or j.get('jobUrl') or j['title']), title=j['title'], location=', '.join(filter(None,locs)), description=plain(j.get('descriptionPlain') or j.get('descriptionHtml')), url=j.get('applyUrl') or j.get('jobUrl',''), published=dateparse(j.get('publishedAt')), updated=None, country=country)
    else: raise ValueError(f'Unsupported ATS: {ats}')

def eligible(j):
    if not ROLE.search(j['title']) or EXCLUDE.search(j['title']): return False
    loc = j['location']
    country = str(j.get('country') or '').upper()
    if country and country not in ('US','USA','UNITED STATES'): return False
    if not (country in ('US','USA','UNITED STATES') or STATES.search(loc) or STATE_CODES.search(loc)): return False
    if re.search(r'\b(?:Canada|India|UK|United Kingdom|Europe|Germany|France|Australia)\b',loc,re.I) and not re.search(r'\b(?:US|USA|United States)\b',loc,re.I): return False
    # Strict: no experience evidence => no alert. Review ambiguous cases manually.
    desc = j['description']
    lines = re.split(r'[\n\r•]|(?<=[.!?])\s+', desc)
    mins = []
    for line in lines:
        if re.search(r'\b(?:require|qualification|experience|minimum|must have|you have|background)\b',line,re.I):
            mins += [int(x) for x in EXPERIENCE.findall(line)]
            if not mins and 'experience' in line.lower(): mins += [int(x) for x in EXPERIENCE_BEFORE.findall(line)]
    if not mins: return False
    # Any explicit requirement above five years excludes; conservatively prefer lower bounds.
    return min(mins) <= 5 and max(mins) <= 5 and any(2 <= x <= 5 for x in mins)

def connect():
    db = sqlite3.connect(DB)
    db.execute('CREATE TABLE IF NOT EXISTS jobs (key TEXT PRIMARY KEY, company TEXT, title TEXT, location TEXT, url TEXT, published TEXT, first_seen TEXT, last_seen TEXT, alerted INTEGER DEFAULT 0)')
    db.commit()
    return db

def iso(dt): return dt.isoformat(timespec='seconds') if dt else None

def send_email(jobs):
    host, user, password, recipient = [os.getenv(x) for x in ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD','ALERT_TO')]
    if not all((host,user,password,recipient)):
        logging.warning('Email secrets not configured; matches retained for later notification')
        return False
    msg = EmailMessage()
    msg['From'], msg['To'] = user, recipient
    msg['Subject'] = f'{len(jobs)} new direct-ATS AI/Data engineering matches'
    body = ['Newly discovered jobs from public employer ATS feeds.', 'Early listing = not verified absent from LinkedIn or Jobright.', '']
    for j in jobs:
        body += [f"{j['title']} — {j['company']}",f"Location: {j['location']}",f"First seen (UTC): {j['first_seen']}",f"Employer published (UTC): {j['published'] or 'Unavailable'}",f"Freshness: {j['freshness']}",f"Apply: {j['url']}",'']
    msg.set_content('\n'.join(body))
    with smtplib.SMTP(host, int(os.getenv('SMTP_PORT','587')), timeout=30) as smtp:
        smtp.starttls()
        smtp.login(user,password)
        smtp.send_message(msg)
    return True

def main():
    with open('boards.yml', encoding='utf-8') as f: boards=yaml.safe_load(f)['boards']
    db = connect()
    initial = db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0] == 0
    pending = []
    successes = 0
    for board in boards:
        try:
            found = list(fetch(board)); successes += 1
            logging.info('%s/%s: %d jobs', board['ats'],board['slug'],len(found))
        except (requests.RequestException, KeyError, ValueError, TypeError) as e:
            logging.error('Board failed %s/%s: %s',board['ats'],board['slug'],e)
            continue
        for j in found:
            if not eligible(j) or not j['url'].startswith('https://'): continue
            key = hashlib.sha256(f"{j['ats']}:{board['slug']}:{j['id']}".encode()).hexdigest()
            published = j['published']
            fresh = published is not None and timedelta(0) <= NOW-published <= timedelta(minutes=60)
            freshness = 'Published within 60 minutes' if fresh else ('Newly discovered; publication time unavailable' if published is None else 'Older posting')
            existing = db.execute('SELECT alerted FROM jobs WHERE key=?',(key,)).fetchone()
            if existing:
                db.execute('UPDATE jobs SET last_seen=? WHERE key=?',(iso(NOW),key))
                if existing[0] == 0 and (fresh or published is None):
                    pending.append(dict(key=key,**j,first_seen=iso(NOW),freshness=freshness))
            else:
                db.execute('INSERT INTO jobs(key,company,title,location,url,published,first_seen,last_seen,alerted) VALUES(?,?,?,?,?,?,?,?,?)', (key,j['company'],j['title'],j['location'],j['url'],iso(published),iso(NOW),iso(NOW), 1 if initial or (published and not fresh) else 0))
                if not initial and (fresh or published is None): pending.append(dict(key=key,**j,first_seen=iso(NOW),freshness=freshness))
    db.commit()
    if successes == 0: raise RuntimeError('All ATS boards failed')
    # Deduplicate within digest on normalized company/title/location.
    unique = {}
    for j in pending:
        identity = (re.sub(r'\W+','',j['company'].lower()),re.sub(r'\W+','',j['title'].lower()),re.sub(r'\W+','',j['location'].lower()))
        unique.setdefault(identity,j)
    alerts = list(unique.values())
    logging.info('New email candidates: %d; baseline: %s',len(alerts),initial)
    if alerts and send_email(alerts):
        db.executemany('UPDATE jobs SET alerted=1 WHERE key=?',[(j['key'],) for j in pending])
        db.commit()
    db.close()

if __name__ == '__main__': main()
