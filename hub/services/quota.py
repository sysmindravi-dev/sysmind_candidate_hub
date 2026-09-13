from datetime import date
from django.db import transaction
from django.db.models import Sum
from hub.models import AppSettings, UserProfile, SignalHireUsage

class QuotaError(RuntimeError): pass

def month_start():
    t=date.today(); return t.replace(day=1)

def _active(qs): return qs.filter(status__in=['RESERVED','CONSUMED'])
def usage_snapshot(user, requirement):
    m=month_start(); cfg=AppSettings.get_solo(); profile=UserProfile.objects.get(user=user)
    company=_active(SignalHireUsage.objects.filter(month=m)).aggregate(v=Sum('credits'))['v'] or 0
    user_used=_active(SignalHireUsage.objects.filter(month=m,user=user)).aggregate(v=Sum('credits'))['v'] or 0
    req_used=_active(SignalHireUsage.objects.filter(requirement=requirement)).aggregate(v=Sum('credits'))['v'] or 0
    return {
        'company_used':company,'company_limit':cfg.company_monthly_signalhire_limit,
        'user_used':user_used,'user_limit':profile.monthly_signalhire_limit,
        'requirement_used':req_used,'requirement_limit':requirement.signalhire_limit,
        'available':max(0,min(cfg.company_monthly_signalhire_limit-company, profile.monthly_signalhire_limit-user_used, requirement.signalhire_limit-req_used))
    }

@transaction.atomic
def reserve(user, requirement, candidate):
    cfg=AppSettings.objects.select_for_update().get(pk=AppSettings.get_solo().pk)
    profile=UserProfile.objects.select_for_update().get(user=user)
    req=type(requirement).objects.select_for_update().get(pk=requirement.pk)
    m=month_start()
    company=_active(SignalHireUsage.objects.filter(month=m)).aggregate(v=Sum('credits'))['v'] or 0
    user_used=_active(SignalHireUsage.objects.filter(month=m,user=user)).aggregate(v=Sum('credits'))['v'] or 0
    req_used=_active(SignalHireUsage.objects.filter(requirement=req)).aggregate(v=Sum('credits'))['v'] or 0
    if company >= cfg.company_monthly_signalhire_limit: raise QuotaError('Company monthly SignalHire limit has been reached.')
    if user_used >= profile.monthly_signalhire_limit: raise QuotaError('Your monthly SignalHire limit has been reached.')
    if req_used >= req.signalhire_limit: raise QuotaError('This requirement has reached its SignalHire limit.')
    existing=SignalHireUsage.objects.filter(candidate=candidate,status__in=['RESERVED','CONSUMED']).first()
    if existing: return existing
    return SignalHireUsage.objects.create(user=user,requirement=req,candidate=candidate,month=m,status='RESERVED',credits=1)

def consume(event, remaining=None):
    event.status='CONSUMED'; event.signalhire_remaining=remaining; event.save(update_fields=['status','signalhire_remaining','updated_at'])
def release(event, remaining=None, failed=False):
    event.status='FAILED' if failed else 'RELEASED'; event.signalhire_remaining=remaining; event.save(update_fields=['status','signalhire_remaining','updated_at'])
