import json, time
from datetime import datetime, timedelta, timezone as dt_timezone
import requests
from django.core.cache import cache

class CeipalError(RuntimeError): pass

def _rows(data):
    if isinstance(data,list): return data
    if isinstance(data,dict):
        for key in ('results','data','records','items'):
            if isinstance(data.get(key),list): return data[key]
        # some CEIPAL list endpoints can return a single object when one match exists
        if data.get('id'): return [data]
    return []

class CeipalClient:
    def __init__(self,org):
        self.org=org; self.base=org.base_url.rstrip('/'); self.s=requests.Session(); self.timeout=30
    def _url(self,path): return f"{self.base}/{path.lstrip('/')}"
    def authenticate(self,force=False):
        key=f'ceipal-token-{self.org.pk}'
        token=None if force else cache.get(key)
        if token: return token
        payload={'email':self.org.api_email,'password':self.org.get_password()}
        if 'v2' in self.org.auth_path: payload['apiKey']=self.org.get_api_key()
        else: payload['api_key']=self.org.get_api_key()
        r=self.s.post(self._url(self.org.auth_path),json=payload,timeout=self.timeout)
        if r.status_code>=400: raise CeipalError(f'Authentication failed ({r.status_code}): {r.text[:300]}')
        data=r.json(); token=data.get('access_token')
        if not token: raise CeipalError('CEIPAL did not return access_token.')
        cache.set(key,token,50*60)
        return token
    def request(self,method,path,params=None,json_body=None,data=None,files=None,retry=True):
        token=self.authenticate(); headers={'Authorization':f'Bearer {token}'}
        if json_body is not None: headers['Content-Type']='application/json'
        r=self.s.request(method,self._url(path),headers=headers,params=params,json=json_body,data=data,files=files,timeout=self.timeout)
        if r.status_code in (401,403) and retry:
            cache.delete(f'ceipal-token-{self.org.pk}'); self.authenticate(force=True)
            return self.request(method,path,params,json_body,data,files,retry=False)
        if r.status_code==429: raise CeipalError('CEIPAL rate limit reached. Retry later.')
        if r.status_code>=400: raise CeipalError(f'CEIPAL {method} {path} failed ({r.status_code}): {r.text[:500]}')
        if not r.content: return {}
        try: return r.json()
        except Exception: return {'text':r.text}
    def find_job(self,req_id):
        data=self.request('GET',self.org.jobs_path,params={'searchkey':req_id})
        rows=_rows(data)
        if not rows: raise CeipalError(f'No CEIPAL job found for {req_id}.')
        q=str(req_id).strip().lower()
        def score(x):
            vals=[x.get('job_code'),x.get('client_job_id'),x.get('id')]
            if any(str(v or '').strip().lower()==q for v in vals): return 100
            if any(q in str(v or '').lower() for v in vals): return 80
            return 10
        job=sorted(rows,key=score,reverse=True)[0]
        job_id=job.get('id') or job.get('jobId')
        if not job_id: raise CeipalError('Job response did not include an encrypted job ID.')
        client=job.get('client_name') or job.get('client') or job.get('company_name') or job.get('company') or ''
        location=', '.join([str(x) for x in [job.get('primary_city') or job.get('city'), job.get('primary_state') or job.get('state')] if x])
        return {
            'job_id':str(job_id),'req_id':str(job.get('job_code') or job.get('client_job_id') or req_id),
            'title':str(job.get('position_title') or job.get('public_job_title') or job.get('jobTitle') or ''),
            'client':str(client or ''),'location':location,'description':str(job.get('requisition_description') or job.get('public_job_desc') or job.get('jobDescription') or ''),
            'skills':str(job.get('skills') or job.get('primarySkills') or ''),'raw':job,
        }
    def applicants_modified_since(self,modified_after):
        params={'modifiedAfter':modified_after.strftime('%Y-%m-%d %H:%M:%S')}
        return _rows(self.request('GET',self.org.applicants_path,params=params))
    def exact_applicant_search(self,email='',phone=''):
        if not self.org.applicant_exact_search_path: return []
        params={}
        if email: params['email']=email
        if phone: params['mobileNumber']=phone
        return _rows(self.request('GET',self.org.applicant_exact_search_path,params=params))
    def submissions(self,job_id,job_seeker_id=''):
        params={'job_id':job_id,'isPipeline':1}
        if job_seeker_id: params['job_seeker_id']=job_seeker_id
        return _rows(self.request('GET',self.org.submissions_path,params=params))
    def already_tagged(self,job_id,job_seeker_id): return bool(self.submissions(job_id,job_seeker_id))
    def apply_without_registration(self,job_id,person,pdf_bytes=None,pdf_name=None):
        data={'job_id':job_id,'standard_fields.email':person.get('email',''),'standard_fields.firstname':person.get('first_name',''),'standard_fields.lastname':person.get('last_name',''),'standard_fields.mobile_number':person.get('phone','')}
        if person.get('city'): data['standard_fields.city']=person['city']
        if self.org.country_default: data['standard_fields.country']=self.org.country_default
        if self.org.state_default: data['standard_fields.state']=self.org.state_default
        files=None
        if pdf_bytes and pdf_name: files={self.org.document_field_name:(pdf_name,pdf_bytes,'application/pdf')}
        result=self.request('POST',self.org.apply_without_registration_path,data=data,files=files)
        return result
    def tag_existing(self,job_id,applicant,person,pdf_bytes=None,pdf_name=None):
        if self.already_tagged(job_id,applicant.ceipal_applicant_id): return {'already_tagged':True}
        if self.org.existing_tag_path:
            return self.request('POST',self.org.existing_tag_path,json_body={'job_id':job_id,'job_seeker_id':applicant.ceipal_applicant_id})
        if self.org.use_apply_for_existing_tagging:
            return self.apply_without_registration(job_id,person,pdf_bytes,pdf_name)
        raise CeipalError('Existing Applicant tagging is not configured. Set existing_tag_path or enable sandbox-tested Apply Without Registration tagging in CEIPAL Organization admin.')
    def update_existing_applicant(self,applicant,person):
        if not self.org.update_applicant_path: return {'skipped':True,'reason':'update_applicant_path not configured'}
        payload={'jobSeekerId':applicant.ceipal_applicant_id}
        if person.get('linkedin_url'): payload[self.org.linkedin_field_name]=person['linkedin_url']
        if person.get('phone') and not applicant.phone: payload['mobileNumber']=person['phone']
        if person.get('email') and not applicant.email: payload['email']=person['email']
        if person.get('skills'): payload['skills']=person['skills']
        if person.get('current_company'): payload['currentCompany']=person['current_company']
        if person.get('job_title'): payload['jobTitle']=person['job_title']
        return self.request('PATCH',self.org.update_applicant_path,json_body=payload)
    def add_secondary_document(self,applicant,pdf_bytes,pdf_name):
        if not self.org.secondary_document_path: return {'skipped':True,'reason':'secondary_document_path not configured'}
        data={'job_seeker_id':applicant.ceipal_applicant_id,'applicantId':applicant.ceipal_applicant_id}
        files={self.org.document_field_name:(pdf_name,pdf_bytes,'application/pdf')}
        return self.request('POST',self.org.secondary_document_path,data=data,files=files)
