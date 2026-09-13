import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Sum, Q
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from .forms import RequirementForm, CSVUploadForm
from .models import *
from .services.ceipal import CeipalClient, CeipalError
from .services.processing import parse_csv, classify_candidate, process_selected, process_with_signalhire
from .services.quota import usage_snapshot
from .services.sync import sync_org


def _can_org(user,org): return user.is_superuser or user.profile.ceipal_orgs.filter(pk=org.pk).exists()
def _can_req(user,req): return _can_org(user,req.org)

@login_required
def dashboard(request):
    reqs=Requirement.objects.filter(created_by=request.user).order_by('-created_at')[:20] if not request.user.is_superuser else Requirement.objects.all().order_by('-created_at')[:20]
    cfg=AppSettings.get_solo();
    company_used=SignalHireUsage.objects.filter(month__year=timezone.now().year,month__month=timezone.now().month,status='CONSUMED').aggregate(v=Sum('credits'))['v'] or 0
    orgs=CeipalOrganization.objects.filter(active=True) if request.user.is_superuser else request.user.profile.ceipal_orgs.filter(active=True)
    return render(request,'hub/dashboard.html',{'requirements':reqs,'cfg':cfg,'company_used':company_used,'orgs':orgs})

@login_required
def new_requirement(request):
    form=RequirementForm(request.POST or None,user=request.user)
    if request.method=='POST' and form.is_valid():
        org=form.cleaned_data['ceipal_org']; rid=form.cleaned_data['requirement_id'].strip()
        try:
            data=CeipalClient(org).find_job(rid)
            req,created=Requirement.objects.get_or_create(org=org,ceipal_job_id=data['job_id'],defaults={'created_by':request.user,'entered_req_id':data['req_id'],'job_title':data['title'],'client_name':data['client'],'location':data['location'],'job_description':data['description'],'skills':data['skills'],'raw_data':data['raw']})
            if not created:
                req.entered_req_id=data['req_id']; req.job_title=data['title']; req.client_name=data['client']; req.location=data['location']; req.job_description=data['description']; req.skills=data['skills']; req.raw_data=data['raw']; req.save()
            AuditLog.objects.create(user=request.user,action='REQUIREMENT_LOADED',requirement=req,details={'input':rid})
            return redirect('requirement_detail',pk=req.pk)
        except Exception as e: messages.error(request,str(e))
    return render(request,'hub/new_requirement.html',{'form':form})

@login_required
def requirement_detail(request,pk):
    req=get_object_or_404(Requirement,pk=pk)
    if not _can_req(request.user,req): return HttpResponseForbidden()
    q=usage_snapshot(request.user,req); batches=req.batches.order_by('-created_at')[:10]
    return render(request,'hub/requirement_detail.html',{'req':req,'quota':q,'batches':batches,'upload_form':CSVUploadForm()})

@login_required
def upload_csv(request,pk):
    req=get_object_or_404(Requirement,pk=pk)
    if not _can_req(request.user,req): return HttpResponseForbidden()
    if request.method!='POST': return redirect('requirement_detail',pk=pk)
    form=CSVUploadForm(request.POST,request.FILES)
    if not form.is_valid(): messages.error(request,str(form.errors)); return redirect('requirement_detail',pk=pk)
    f=form.cleaned_data['csv_file']
    try: rows=parse_csv(f)
    except Exception as e: messages.error(request,str(e)); return redirect('requirement_detail',pk=pk)
    batch=ImportBatch.objects.create(requirement=req,uploaded_by=request.user,filename=f.name,row_count=len(rows))
    for row in rows:
        c=ImportCandidate.objects.create(batch=batch,**row); classify_candidate(c)
        if c.status=='EXISTING': c.selected=True; c.save(update_fields=['selected'])
    # Default-select the best-fit unmatched candidates only up to the currently available SignalHire quota.
    avail=usage_snapshot(request.user,req)['available']
    for c in batch.candidates.filter(status='READY').order_by('-job_fit_score','row_number')[:avail]:
        c.selected=True; c.save(update_fields=['selected'])
    AuditLog.objects.create(user=request.user,action='CSV_UPLOADED',requirement=req,details={'batch_id':batch.pk,'filename':f.name,'rows':len(rows)})
    return redirect('batch_detail',pk=batch.pk)

@login_required
def batch_detail(request,pk):
    batch=get_object_or_404(ImportBatch,pk=pk); req=batch.requirement
    if not _can_req(request.user,req): return HttpResponseForbidden()
    candidates=batch.candidates.select_related('matched_applicant').order_by('row_number')
    quota=usage_snapshot(request.user,req)
    stats={k:candidates.filter(status=k).count() for k in ['EXISTING','POSSIBLE','READY','PENDING','COMPLETE','FAILED']}
    return render(request,'hub/batch_detail.html',{'batch':batch,'req':req,'candidates':candidates,'quota':quota,'stats':stats})

@login_required
def update_selection(request,pk):
    batch=get_object_or_404(ImportBatch,pk=pk)
    if not _can_req(request.user,batch.requirement): return HttpResponseForbidden()
    if request.method=='POST':
        chosen=set(request.POST.getlist('candidate'))
        for c in batch.candidates.all():
            c.selected=str(c.pk) in chosen; c.save(update_fields=['selected'])
        messages.success(request,'Selection updated.')
    return redirect('batch_detail',pk=pk)

@login_required
def process_batch(request,pk):
    batch=get_object_or_404(ImportBatch,pk=pk)
    if not _can_req(request.user,batch.requirement): return HttpResponseForbidden()
    if request.method!='POST': return redirect('batch_detail',pk=pk)
    process_selected(batch,request.user)
    messages.success(request,'Processing completed for all candidates that could be completed. Review any failed rows for configuration/API messages.')
    return redirect('batch_detail',pk=pk)

@login_required
def retry_candidate(request,pk):
    c=get_object_or_404(ImportCandidate,pk=pk)
    if not _can_req(request.user,c.batch.requirement): return HttpResponseForbidden()
    c.selected=True; c.save(update_fields=['selected'])
    if c.status=='EXISTING':
        from .services.processing import process_existing; process_existing(c,request.user)
    else: process_with_signalhire(c,request.user)
    return redirect('batch_detail',pk=c.batch_id)

@login_required
def activity(request):
    logs=AuditLog.objects.filter(user=request.user).select_related('requirement','candidate')[:200]
    return render(request,'hub/activity.html',{'logs':logs})

@login_required
def report(request):
    if not (request.user.is_superuser or request.user.profile.is_manager): return HttpResponseForbidden()
    rows=[]
    for u in User.objects.filter(is_active=True).order_by('username'):
        req_count=AuditLog.objects.filter(user=u,requirement__isnull=False).values('requirement_id').distinct().count()
        credits=SignalHireUsage.objects.filter(user=u,status='CONSUMED').aggregate(v=Sum('credits'))['v'] or 0
        rows.append({'user':u,'requirements_count':req_count,'credits_used':credits})
    recent=Requirement.objects.select_related('created_by','org').prefetch_related('batches__candidates').order_by('-created_at')[:200]
    return render(request,'hub/report.html',{'rows':rows,'recent':recent})

@login_required
def sync_ceipal_now(request,org_id):
    org=get_object_or_404(CeipalOrganization,pk=org_id)
    if not (request.user.is_superuser or request.user.profile.is_manager): return HttpResponseForbidden()
    try: n=sync_org(org); messages.success(request,f'Synced {n} CEIPAL Applicants into the local matching index.')
    except Exception as e: messages.error(request,str(e))
    return redirect('dashboard')

@csrf_exempt
def signalhire_callback(request,secret,candidate_id):
    cfg=AppSettings.get_solo()
    if not cfg.signalhire_callback_secret or secret!=cfg.signalhire_callback_secret: return HttpResponseForbidden()
    if request.method!='POST': return HttpResponse(status=405)
    c=get_object_or_404(ImportCandidate,pk=candidate_id)
    try: payload=json.loads(request.body.decode('utf-8'))
    except Exception: return HttpResponse(status=400)
    row=payload[0] if isinstance(payload,list) and payload else {'status':'failed'}
    c.signalhire_payload=row.get('candidate') or {}; c.signalhire_status=row.get('status',''); c.save(update_fields=['signalhire_payload','signalhire_status','updated_at'])
    BackgroundTask.objects.create(task_type='FINALIZE_SIGNALHIRE',payload={'candidate_id':c.pk,'row':row})
    return HttpResponse('OK')
