import os, re, json, html, sqlite3, smtplib, hashlib, logging, argparse, time
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from urllib.parse import urlparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
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
EXCLUDE = re.compile(r'\b(?:intern|internship|co-op|new grad|staff|principal|director|vp|head of|architect|manager|recruiter|solutions engineer)\b', re.I)

def plain(s):
    return BeautifulSoup(html.unescape(s or ''), 'html.parser').get_text(' ', strip=True)

def dateparse(value):
    if not value: return None
    try:
        if isinstance(value, (float, int)):
            return datetime.fromtimestamp(value / 1000 if value > 1e11 else value, timezone.utc)
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError): return None

SESSION = requests.Session()
SESSION.headers.update(UA)
SESSION.mount('https://', HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429,500,502,503,504], allowed_methods=['GET'])))

def get(url, params=None):
    r = SESSION.get(url, params=params, timeout=(8,25))
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
            yield dict(company=company, ats=ats, id=str(j['id']), title=j['text'], location=', '.join([str(x) for x in (cat.get('allLocations') or [cat.get('location','')]) if x]), description=plain(j.get('descriptionPlain') or j.get('description')), url=j.get('applyUrl') or j.get('hostedUrl',''), published=None, updated=None, country=j.get('country'))
    elif ats == 'ashby':
        data = get(f'https://api.ashbyhq.com/posting-api/job-board/{slug}')
        for j in data['jobs']:
            if j.get('isListed') is False: continue
            locs = [j.get('location','')] + [x.get('location','') for x in j.get('secondaryLocations',[]) or []]
            country = (j.get('address') or {}).get('postalAddress',{}).get('addressCountry')
            yield dict(company=company, ats=ats, id=str(j.get('id') or j.get('jobUrl') or j['title']), title=j['title'], location=', '.join(filter(None,locs)), description=plain(j.get('descriptionPlain') or j.get('descriptionHtml')), url=j.get('applyUrl') or j.get('jobUrl',''), published=dateparse(j.get('publishedAt')), updated=None, country=country)
    elif ats == 'smartrecruiters':
        offset = 0
        while offset < 3000:
            data = get(f'https://api.smartrecruiters.com/v1/companies/{slug}/postings', {'limit':100,'offset':offset})
            jobs = data.get('content')
            if not isinstance(jobs,list): raise ValueError('Malformed SmartRecruiters feed')
            for j in jobs:
                l = j.get('location') or {}
                location = ', '.join(str(l.get(k) or '') for k in ('city','region','country') if l.get(k))
                description = plain(j.get('jobAd') if isinstance(j.get('jobAd'),str) else j.get('description'))
                yield dict(company=company, ats=ats, id=str(j['id']),title=j.get('name') or j.get('title',''), location=location,description=description,url=j.get('jobAdUrl') or j.get('applyUrl') or j.get('ref',''),published=dateparse(j.get('releasedDate')),updated=None,country=l.get('country'))
            if len(jobs)<100: break
            offset+=100
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
    db.execute('PRAGMA journal_mode=DELETE')
    db.execute('CREATE TABLE IF NOT EXISTS jobs (key TEXT PRIMARY KEY, company TEXT, title TEXT, location TEXT, url TEXT, published TEXT, first_seen TEXT, last_seen TEXT, alerted INTEGER DEFAULT 0)')
    db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)')
    db.commit()
    return db

def iso(dt): return dt.isoformat(timespec='seconds') if dt else None

def send_email(jobs):
    host, user, password, recipient = [os.getenv(x) for x in ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD','ALERT_TO')]
    if not all((host,user,password,recipient)):
        raise RuntimeError('Missing SMTP_HOST, SMTP_USER, SMTP_PASSWORD or ALERT_TO; unsent matches retained')
    msg = EmailMessage()
    msg['From'], msg['To'] = user, recipient
    msg['Subject'] = f'{len(jobs)} new direct-ATS AI/Data engineering matches'
    body = ['Newly discovered jobs from public employer ATS feeds.', 'Early listing = not verified absent from LinkedIn or Jobright.', '']
    for j in jobs:
        body += [f"{j['title']} — {j['company']}",f"Location: {j['location']}",f"First seen (UTC): {j['first_seen']}",f"Employer published (UTC): {j['published'] or 'Unavailable'}",f"Freshness: {j['freshness']}",f"Apply: {j['url']}",'']
    msg.set_content('\n'.join(body))
    port=int(os.getenv('SMTP_PORT','587'))
    if port == 465:
        with smtplib.SMTP_SSL(host,port,timeout=30) as smtp:
            smtp.login(user,password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host,port,timeout=30) as smtp:
            smtp.starttls()
            smtp.login(user,password)
            smtp.send_message(msg)
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    boards=yaml.safe_load(Path('boards.yml').read_text(encoding='utf-8'))['boards']
    dedup={(b['ats'],b['slug']):b for b in boards if b.get('ats') in ('greenhouse','lever','ashby','smartrecruiters')}
    boards=list(dedup.values())
    if not boards: raise RuntimeError('No configured boards')
    def check(board):
        try:
            return (board,list(fetch(board)),None)
        except (requests.RequestException, KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            return (board,[],f'{type(exc).__name__}: {exc}')
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(check,boards))
    report={'scan_utc':iso(NOW),'boards':[{'company':b['company'],'ats':b['ats'],'slug':b['slug'],'ok':err is None,'jobs':len(jobs),'error':err} for b,jobs,err in results]}
    Path('validation_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    successes=sum(err is None for _,_,err in results)
    logging.info('Feed health: %s/%s OK',successes,len(results))
    if args.validate_only: return 0 if successes else 2
    if not successes: raise RuntimeError('All feeds failed. State was not changed.')
    db=connect()
    try:
        initialized=db.execute("SELECT value FROM metadata WHERE key='initialized'").fetchone() is not None
        pending=[]
        for board,found,error in results:
            if error:
                logging.error('Feed failed %s/%s: %s',board['ats'],board['slug'],error)
                continue
            for j in found:
                if not eligible(j) or not str(j['url']).startswith('https://'): continue
                key=hashlib.sha256(f"{j['ats']}:{board['slug']}:{j['id']}".encode()).hexdigest()
                published=j['published']
                fresh=published is not None and timedelta(minutes=-5)<=NOW-published<=timedelta(minutes=60)
                classification='published_within_60m' if fresh else ('first_discovered_time_unverified' if published is None else 'older_publication')
                existing=db.execute('SELECT first_seen,alerted FROM jobs WHERE key=?',(key,)).fetchone()
                first_seen=existing[0] if existing else iso(NOW)
                alerted=existing[1] if existing else 0
                db.execute("""INSERT INTO jobs(key,company,title,location,url,published,first_seen,last_seen,alerted)
                    VALUES(?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(key) DO UPDATE SET company=excluded.company,title=excluded.title,location=excluded.location,url=excluded.url,published=excluded.published,last_seen=excluded.last_seen""",
                    (key,j['company'],j['title'],j['location'],j['url'],iso(published),first_seen,iso(NOW),alerted))
                if initialized and not alerted and (fresh or published is None):
                    pending.append(dict(key=key,**j,first_seen=first_seen,freshness=classification))
        if not initialized:
            db.execute("INSERT INTO metadata(key,value) VALUES('initialized',?)",(iso(NOW),))
            # Baseline jobs must not be emailed subsequently.
            db.execute('UPDATE jobs SET alerted=1')
        db.commit()
        if not initialized:
            logging.info('Baseline established; subsequent runs notify on new jobs')
            return 0
        # Deduplicate digest, marking every source identity as alerted if delivery succeeds.
        unique={}
        for j in pending:
            signature=(re.sub(r'\W+','',j['company'].lower()),re.sub(r'\W+','',j['title'].lower()),re.sub(r'\W+','',j['location'].lower()))
            unique.setdefault(signature,j)
        alerts=list(unique.values())
        if alerts and not args.dry_run and send_email(alerts):
            db.executemany('UPDATE jobs SET alerted=1 WHERE key=?',[(j['key'],) for j in pending])
            db.commit()
        Path('last_run.json').write_text(json.dumps({'scan_utc':iso(NOW),'boards_ok':successes,'boards_failed':len(results)-successes,'new_matches':len(alerts),'baseline':not initialized},indent=2))
        logging.info('%s new matches',len(alerts))
    finally:
        db.close()
    return 0

if __name__=='__main__':
    raise SystemExit(main())
