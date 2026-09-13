import requests
from django.conf import settings
from hub.models import AppSettings

class SignalHireError(RuntimeError): pass
class SignalHireClient:
    URL='https://www.signalhire.com/api/v1/candidate/search'
    def __init__(self):
        self.cfg=AppSettings.get_solo(); self.api_key=self.cfg.get_signalhire_api_key(); self.timeout=35
        if not self.api_key: raise SignalHireError('SignalHire API key is not configured.')
    def credits(self):
        r=requests.get('https://www.signalhire.com/api/v1/credits',headers={'apikey':self.api_key},timeout=20)
        if r.status_code>=400: raise SignalHireError(f'Credit check failed ({r.status_code}).')
        return int(r.headers.get('X-Credits-Left','-1'))
    def lookup_sync(self,identifier):
        payload={'items':[identifier],'withoutWaterfall':True}
        r=requests.post(self.URL,headers={'apikey':self.api_key,'Content-Type':'application/json'},json=payload,timeout=self.timeout)
        if r.status_code==402: raise SignalHireError('SignalHire credits are exhausted.')
        if r.status_code==429: raise SignalHireError('SignalHire rate limit reached.')
        if r.status_code>=400: raise SignalHireError(f'SignalHire failed ({r.status_code}): {r.text[:300]}')
        rows=r.json() if isinstance(r.json(),list) else []
        return (rows[0] if rows else {'item':identifier,'status':'failed'}), int(r.headers.get('X-Credits-Left','-1'))
    def lookup_async(self,identifier,candidate_id,secret):
        base=settings.SIGNALHIRE_CALLBACK_BASE_URL.rstrip('/')
        if not base: raise SignalHireError('SIGNALHIRE_CALLBACK_BASE_URL is required for async mode.')
        callback=f'{base}/signalhire/callback/{secret}/{candidate_id}/'
        payload={'items':[identifier],'callbackUrl':callback}
        r=requests.post(self.URL,headers={'apikey':self.api_key,'Content-Type':'application/json'},json=payload,timeout=20)
        if r.status_code==402: raise SignalHireError('SignalHire credits are exhausted.')
        if r.status_code==429: raise SignalHireError('SignalHire rate limit reached.')
        if r.status_code>=400: raise SignalHireError(f'SignalHire failed ({r.status_code}): {r.text[:300]}')
        data=r.json(); return str(data.get('requestId','')), int(r.headers.get('X-Credits-Left','-1'))

def parse_candidate(obj, fallback_name='', fallback_linkedin='', fallback_location=''):
    c=obj or {}; contacts=c.get('contacts') or []
    emails=[]; phones=[]
    for item in contacts:
        val=str(item.get('value') or item.get('contact') or '')
        typ=str(item.get('type') or '').lower()
        if '@' in val or 'email' in typ: emails.append(val)
        elif val: phones.append(val)
    socials=c.get('social') or []
    linkedin=fallback_linkedin
    for s in socials:
        url=str(s.get('url') or s.get('link') or '')
        if 'linkedin.com' in url.lower(): linkedin=url; break
    exp=c.get('experience') or []
    current=exp[0] if exp else {}
    full=str(c.get('fullName') or c.get('full_name') or fallback_name).strip()
    parts=full.split(); first=parts[0] if parts else ''; last=' '.join(parts[1:]) if len(parts)>1 else ''
    loc=c.get('location') or fallback_location
    if isinstance(loc,dict): loc=', '.join(str(loc.get(k) or '') for k in ('city','state','country') if loc.get(k))
    skills=c.get('skills') or []
    if isinstance(skills,list): skills=', '.join(str(x.get('name') if isinstance(x,dict) else x) for x in skills)
    return {'first_name':first,'last_name':last,'full_name':full,'email':emails[0] if emails else '', 'phone':phones[0] if phones else '', 'linkedin_url':linkedin,'location':str(loc or ''),'skills':str(skills or ''),'job_title':str(current.get('position') or current.get('title') or c.get('jobTitle') or ''),'current_company':str(current.get('company') or current.get('companyName') or ''),'raw':c}
