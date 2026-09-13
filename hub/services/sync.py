from datetime import timedelta
from django.utils import timezone
from hub.models import ApplicantIndex, AppSettings
from .ceipal import CeipalClient
from .matching import normalize_linkedin, normalize_phone

def sync_org(org, modified_after=None):
    cfg=AppSettings.get_solo()
    modified_after=modified_after or (timezone.now()-timedelta(days=cfg.applicant_sync_lookback_days))
    rows=CeipalClient(org).applicants_modified_since(modified_after)
    count=0
    for r in rows:
        aid=r.get('id') or r.get('jobSeekerId') or r.get('applicantId')
        if not aid: continue
        defaults={
            'applicant_number':str(r.get('applicant_id') or r.get('applicantId') or ''),'first_name':str(r.get('firstname') or r.get('firstName') or ''),'last_name':str(r.get('lastname') or r.get('lastName') or ''),
            'full_name':str(r.get('consultant_name') or r.get('fullName') or f"{r.get('firstname','')} {r.get('lastname','')}").strip(),'email':str(r.get('email') or ''),'alt_email':str(r.get('email_address_1') or ''),'phone':str(r.get('mobile_number') or r.get('mobileNumber') or r.get('other_phone') or ''),
            'city':str(r.get('city') or ''),'state':str(r.get('state') or ''),'country':str(r.get('country') or ''),'job_title':str(r.get('job_title') or r.get('jobTitle') or ''),'skills':str(r.get('skills') or ''),'linkedin_url':str(r.get('linkedInProfileUrl') or r.get('linkedin_url') or ''),'linkedin_normalized':normalize_linkedin(str(r.get('linkedInProfileUrl') or r.get('linkedin_url') or '')),'phone_normalized':normalize_phone(str(r.get('mobile_number') or r.get('mobileNumber') or r.get('other_phone') or '')),'resume_path':str(r.get('resume_path') or ''),'raw_data':r,
        }
        ApplicantIndex.objects.update_or_create(org=org,ceipal_applicant_id=str(aid),defaults=defaults); count+=1
    return count
