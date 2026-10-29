"""Broad relevance scoring for AI, ML, data, analytics and adjacent engineering work."""
import re

GROUPS = {
    "machine learning": (r'\bmachine learning\b|\bdeep learning\b|\bml engineer\b|\bmlops\b|\bmodel serving\b|\bmodel training\b', 5),
    "generative AI": (r'\b(?:generative ai|genai|llms?|large language models?|rag|retrieval augmented generation|agents?|prompt engineer(?:ing)?)\b', 5),
    "data engineering": (r'\b(?:data engineer(?:ing)?|data platform|etl|elt|data pipelines?|dbt|spark|databricks|airflow|streaming data|data infrastructure)\b', 5),
    "AI engineering": (r'\b(?:artificial intelligence|applied ai|ai engineer(?:ing)?|intelligent systems|nlp|natural language processing|computer vision|speech recognition|inference engineer(?:ing)?)\b', 5),
    "analytics": (r'\b(?:analytics engineer(?:ing)?|data analy(?:st|tics)|product analytics|business intelligence|bi engineer(?:ing)?|decision scientist|experimentation|causal inference)\b', 4),
    "data science": (r'\b(?:data scien(?:ce|tist)|statistical model(?:ing|ling)|predictive model(?:ing|ling)|forecasting|recommendation systems?)\b', 5),
}
TITLE_HINT = re.compile(r'\b(?:engineer|developer|scientist|analyst|researcher|specialist|architect|technologist|programmer|consultant)\b', re.I)
TECH = re.compile(r'\b(?:python|pytorch|tensorflow|sql|spark|kafka|snowflake|aws|azure|gcp|vector database|llm|mlops|machine learning|etl|dbt|databricks)\b',re.I)
SENIOR_EXCLUDE = re.compile(r'\b(?:intern(?:ship)?|co.op|staff|principal|director|vice president|vp|head of|chief|distinguished|fellow)\b',re.I)
YEARS = re.compile(r'(?<!\d)(\d{1,2})(?:\s*(?:[-–—]|to)\s*(\d{1,2}))?\s*\+?\s*(?:years?|yrs?)\b', re.I)

def assess(title, description='', min_score=5):
    """Return (accepted, score, reasons); title carries strongest weight.
    Missing years are accepted and labeled; requirements above five years are rejected.
    """
    title=title or ''
    description=description or ''
    if SENIOR_EXCLUDE.search(title): return False,0,['excluded seniority/intern']
    if re.search(r'\b(?:sales representative|account executive|talent acquisition|recruiter|registered nurse|warehouse associate)\b',title,re.I):
        return False,0,['outside technical target']
    reasons=[]
    score=0
    for group,(pat,points) in GROUPS.items():
        title_hit=bool(re.search(pat,title,re.I))
        body_hit=bool(re.search(pat,description[:8000],re.I))
        if title_hit:
            score+=points+3; reasons.append(group+' in title')
        elif body_hit:
            score+=min(2,points);reasons.append(group+' in description')
    if not reasons: return False,0,['no relevant AI/data signals']
    # Avoid emailing every generic software engineering opening with ML in boilerplate.
    strong_title=any('in title' in reason for reason in reasons)
    if not strong_title and not (TITLE_HINT.search(title) and len(reasons)>=2 and TECH.search(description)):
        return False,score,['technical relevance too weak']
    if TITLE_HINT.search(title): score+=1
    # Inspect all explicit year requirements, not only the first mention.
    mentions=list(YEARS.finditer(description[:12000]))
    if mentions:
        required=max(int(match.group(2) or match.group(1)) for match in mentions)
        if required>=6:
            return False,0,['requires more than 5 years']
        if required in (3,4):
            score+=7
            reasons.append('experience: 3–4 years (highest priority)')
        elif required<=2:
            score+=4
            reasons.append('experience: 0–2 years (included)')
        else:
            score+=1
            reasons.append('experience: 5 years (lower priority)')
    else:
        reasons.append('experience not specified')
    return score>=min_score,score,reasons

def us_eligible(location='',country=None):
    location=(location or '').strip()
    country=str(country or '').strip().upper()
    if country in ('US','USA','UNITED STATES','UNITED STATES OF AMERICA'): return True
    if country and country not in ('US','USA','UNITED STATES','UNITED STATES OF AMERICA','WORLDWIDE','GLOBAL'): return False
    if re.search(r'\b(?:united states|u[.]?s[.]?a[.]?|us remote|remote us|north america|worldwide|global|anywhere)\b',location,re.I): return True
    if re.search(r'\b(?:canada|united kingdom|europe|india|germany|france|australia)\b',location,re.I):return False
    if re.search(r'\b(?:remote|united states)\b',location,re.I):return True
    if re.search(r',\s*(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MS|MN|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b',location): return True
    if re.search(r'\b(?:California|Texas|Florida|New York|Massachusetts|Washington|Georgia|Colorado|Illinois|Virginia|Maryland|Pennsylvania|North Carolina|New Jersey|Oregon|Ohio|Arizona|Michigan|Minnesota|Tennessee|Utah|Wisconsin|Connecticut|Missouri|Indiana|Nevada|NYC|New York City|SF|Bay Area|Silicon Valley|Atlanta|Boston|Chicago|Seattle|San Francisco|Austin|Dallas|Houston|Denver|Los Angeles|San Diego|Miami|Philadelphia|Phoenix|Raleigh|Portland|Nashville)\b',location,re.I):return True
    return False
