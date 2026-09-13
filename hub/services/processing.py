import csv, io, re
from django.core.files.base import ContentFile
from django.db import transaction
from hub.models import AppSettings, ApplicantIndex, AuditLog, ImportCandidate, BackgroundTask
from .matching import find_best_match, exact_local_match, normalize_linkedin, normalize_phone
from rapidfuzz.fuzz import token_set_ratio
from .signalhire import SignalHireClient, SignalHireError, parse_candidate
from .ceipal import CeipalClient, CeipalError
from .profile_pdf import generate_profile_pdf
from .quota import reserve, consume, release, QuotaError

HEADER_ALIASES={
 'name':['name','candidate name','full name','candidate'],
 'linkedin':['linkedin','linkedin url','linkedin profile','linkedin profile url','linkedinurl'],
 'location':['location','current location','candidate location','city/state','current city'],
 'skills':['skills','skill','primary skills','key skills'],
}
def _key(s): return re.sub(r'[^a-z0-9]+',' ',(s or '').lower()).strip()
def parse_csv(upload):
    raw=upload.read()
    for enc in ('utf-8-sig','utf-8','latin-1'):
        try: text=raw.decode(enc); break
        except UnicodeDecodeError: continue
    reader=csv.DictReader(io.StringIO(text)); headers={_key(h):h for h in (reader.fieldnames or [])}
    mapping={}
    for target,aliases in HEADER_ALIASES.items():
        for a in aliases:
            if _key(a) in headers: mapping[target]=headers[_key(a)]; break
    if 'name' not in mapping: raise ValueError('CSV must contain a Name/Candidate Name/Full Name column.')
    rows=[]
    for n,row in enumerate(reader,start=2):
        name=(row.get(mapping['name']) or '').strip()
        if not name: continue
        rows.append({'row_number':n,'name':name,'linkedin_url':(row.get(mapping.get('linkedin','')) or '').strip(),'location':(row.get(mapping.get('location','')) or '').strip(),'skills':(row.get(mapping.get('skills','')) or '').strip()})
    return rows

def classify_candidate(candidate):
    cfg=AppSettings.get_solo(); req=candidate.batch.requirement
    app,score=find_best_match(req.org,candidate.name,candidate.location,candidate.skills,candidate.linkedin_url)
    candidate.matched_applicant=app; candidate.match_score=score
    target=(req.skills or req.job_description or req.job_title or '')
    candidate.job_fit_score=int(token_set_ratio(candidate.skills.lower(), target.lower())) if target and candidate.skills else 0
    if app and score>=cfg.auto_match_threshold:
        candidate.status='EXISTING'; candidate.ceipal_applicant_id=app.ceipal_applicant_id
    elif app and score>=cfg.possible_match_threshold:
        candidate.status='POSSIBLE'
    else: candidate.status='READY'
    candidate.save(update_fields=['matched_applicant','match_score','job_fit_score','status','ceipal_applicant_id','updated_at'])
    return candidate

def _person_from_existing(candidate):
    a=candidate.matched_applicant
    parts=(candidate.name or (a.full_name if a else '')).split(); first=parts[0] if parts else ''; last=' '.join(parts[1:]) if len(parts)>1 else ''
    return {'first_name':first,'last_name':last,'full_name':candidate.name,'email':(a.email if a else ''),'phone':(a.phone if a else ''),'linkedin_url':candidate.linkedin_url or (a.linkedin_url if a else ''),'location':candidate.location,'skills':candidate.skills or (a.skills if a else ''),'job_title':a.job_title if a else '','current_company':'','raw':{}}

def _upsert_index(org,applicant_id,person,raw=None):
    obj,_=ApplicantIndex.objects.update_or_create(org=org,ceipal_applicant_id=str(applicant_id),defaults={
        'full_name':person.get('full_name',''),'first_name':person.get('first_name',''),'last_name':person.get('last_name',''),'email':person.get('email',''),'phone':person.get('phone',''),'city':person.get('location','')[:200],'skills':person.get('skills',''),'job_title':person.get('job_title',''),'linkedin_url':person.get('linkedin_url',''),'linkedin_normalized':normalize_linkedin(person.get('linkedin_url','')),'phone_normalized':normalize_phone(person.get('phone','')),'raw_data':raw or {}})
    return obj

def process_existing(candidate,user):
    req=candidate.batch.requirement; app=candidate.matched_applicant
    if not app: raise RuntimeError('No existing Applicant is attached to this candidate.')
    client=CeipalClient(req.org); person=_person_from_existing(candidate)
    client.update_existing_applicant(app,person)
    result=client.tag_existing(req.ceipal_job_id,app,person)
    candidate.ceipal_submission_id=str(result.get('submissionId') or result.get('submission_id') or '')
    candidate.processing_state='COMPLETE'; candidate.status='COMPLETE'; candidate.save(update_fields=['ceipal_submission_id','processing_state','status','updated_at'])
    AuditLog.objects.create(user=user,action='EXISTING_APPLICANT_TAGGED',requirement=req,candidate=candidate,details={'applicant_id':app.ceipal_applicant_id,'result':result})
    return candidate

def process_with_signalhire(candidate,user,signalhire_result=None,remaining=None):
    req=candidate.batch.requirement; event=None
    try:
        if signalhire_result is None:
            if not candidate.linkedin_url and not (candidate.signalhire_status=='success' and candidate.signalhire_payload):
                candidate.status='FAILED'; candidate.processing_state='NO_IDENTIFIER'; candidate.error_message='No LinkedIn URL is available for SignalHire lookup.'; candidate.save()
                return candidate
            # If a previous paid lookup succeeded but CEIPAL later failed, reuse the stored payload.
            # This prevents a Retry from consuming another SignalHire credit.
            if candidate.signalhire_status=='success' and candidate.signalhire_payload:
                result={'status':'success','candidate':candidate.signalhire_payload}
            else:
                event=reserve(user,req,candidate)
                cfg=AppSettings.get_solo(); sh=SignalHireClient()
                if cfg.signalhire_mode=='async':
                    rid,remaining=sh.lookup_async(candidate.linkedin_url,candidate.pk,cfg.signalhire_callback_secret)
                    candidate.signalhire_request_id=rid; candidate.signalhire_status='pending'; candidate.status='PENDING'; candidate.processing_state='SIGNALHIRE_PENDING'; candidate.save()
                    return candidate
                result,remaining=sh.lookup_sync(candidate.linkedin_url)
        else:
            result=signalhire_result
            event=candidate.credit_events.filter(status='RESERVED').order_by('-created_at').first()
        candidate.signalhire_status=result.get('status','')
        if result.get('status')!='success':
            if event: release(event,remaining)
            candidate.status='FAILED'; candidate.processing_state='SIGNALHIRE_NO_MATCH'; candidate.error_message=f"SignalHire status: {result.get('status','failed')}"; candidate.save()
            return candidate
        if event: consume(event,remaining)
        person=parse_candidate(result.get('candidate') or {},candidate.name,candidate.linkedin_url,candidate.location)
        candidate.email=person['email']; candidate.phone=person['phone']; candidate.signalhire_payload=result.get('candidate') or {}; candidate.processing_state='SIGNALHIRE_COMPLETE'; candidate.save()
        # Exact second check locally, then optional CEIPAL exact endpoint.
        existing=exact_local_match(req.org,person['email'],person['phone'],person['linkedin_url'])
        cc=CeipalClient(req.org)
        if not existing and req.org.applicant_exact_search_path:
            rows=cc.exact_applicant_search(person['email'],person['phone'])
            if rows:
                r=rows[0]; aid=r.get('id') or r.get('jobSeekerId') or r.get('applicantId')
                if aid: existing=_upsert_index(req.org,aid,person,r)
        pdf=generate_profile_pdf(person); fname=f"{re.sub(r'[^A-Za-z0-9_-]+','_',person['full_name'] or candidate.name)}_LinkedIn_Profile.pdf"
        candidate.profile_pdf.save(fname,ContentFile(pdf),save=False)
        if existing:
            candidate.matched_applicant=existing; candidate.ceipal_applicant_id=existing.ceipal_applicant_id; candidate.created_new_applicant=False
            cc.update_existing_applicant(existing,person); cc.add_secondary_document(existing,pdf,fname)
            tag=cc.tag_existing(req.ceipal_job_id,existing,person)
            candidate.ceipal_submission_id=str(tag.get('submissionId') or tag.get('submission_id') or '')
            action='ENRICHED_EXISTING_APPLICANT'
        else:
            result_apply=cc.apply_without_registration(req.ceipal_job_id,person,pdf,fname)
            aid=result_apply.get('applicantId') or result_apply.get('applicant_id')
            if not aid: raise CeipalError(f'Apply Without Registration did not return applicantId: {result_apply}')
            newidx=_upsert_index(req.org,aid,person,result_apply); candidate.matched_applicant=newidx; candidate.ceipal_applicant_id=str(aid); candidate.created_new_applicant=True
            candidate.ceipal_submission_id=str(result_apply.get('submissionId') or result_apply.get('submission_id') or '')
            action='CREATED_AND_TAGGED_APPLICANT'
        candidate.status='COMPLETE'; candidate.processing_state='COMPLETE'; candidate.error_message=''; candidate.save()
        AuditLog.objects.create(user=user,action=action,requirement=req,candidate=candidate,details={'applicant_id':candidate.ceipal_applicant_id,'submission_id':candidate.ceipal_submission_id,'signalhire_remaining':remaining})
        return candidate
    except Exception as e:
        if event and event.status=='RESERVED': release(event,remaining,failed=True)
        candidate.status='FAILED'; candidate.error_message=str(e); candidate.processing_state='FAILED'; candidate.save(update_fields=['status','error_message','processing_state','updated_at'])
        AuditLog.objects.create(user=user,action='PROCESSING_FAILED',requirement=req,candidate=candidate,details={'error':str(e)})
        return candidate

def process_selected(batch,user):
    for c in batch.candidates.filter(selected=True).order_by('row_number'):
        if c.status=='COMPLETE': continue
        if c.status=='EXISTING': process_existing(c,user)
        elif c.status in ('READY','POSSIBLE','FAILED'): process_with_signalhire(c,user)
