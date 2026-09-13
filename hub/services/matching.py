import re
from rapidfuzz.fuzz import ratio, token_set_ratio
from hub.models import ApplicantIndex, AppSettings

def normalize_linkedin(url):
    s=(url or '').strip().lower().split('?')[0].rstrip('/')
    s=re.sub(r'^https?://(www\.)?','',s)
    return s

def normalize_phone(p): return re.sub(r'\D','',p or '')[-10:]
def normalize_email(e): return (e or '').strip().lower()
def split_location(s): return [x.strip().lower() for x in re.split(r'[,|/]',s or '') if x.strip()]

def score_candidate(name,location,skills,linkedin,app):
    if linkedin and app.linkedin_url and normalize_linkedin(linkedin)==normalize_linkedin(app.linkedin_url): return 100
    score=0
    # Fuzzy identity guess requested by SysMind: name + location + skills can independently contribute.
    score += int(45 * ratio((name or '').lower(),(app.full_name or '').lower())/100)
    loc_a=' '.join(split_location(location)); loc_b=' '.join(split_location(','.join([app.city,app.state,app.country])))
    if loc_a and loc_b: score += int(25 * token_set_ratio(loc_a,loc_b)/100)
    if skills and app.skills: score += int(30 * token_set_ratio(skills.lower(),app.skills.lower())/100)
    return min(score,99)

def find_best_match(org,name,location='',skills='',linkedin=''):
    qs=ApplicantIndex.objects.filter(org=org)
    if linkedin:
        target=normalize_linkedin(linkedin)
        app=qs.filter(linkedin_normalized=target).first()
        if app: return app,100
    # Narrow by first/last token where possible, then fuzzy-score a capped candidate set.
    tokens=[t for t in re.findall(r'[a-zA-Z]+',name or '') if len(t)>1]
    narrowed=qs
    if tokens:
        from django.db.models import Q
        q=Q()
        for t in tokens[:2]: q |= Q(full_name__icontains=t)
        narrowed=qs.filter(q)
    best=None; best_score=0
    for app in narrowed[:250]:
        s=score_candidate(name,location,skills,linkedin,app)
        if s>best_score: best,best_score=app,s
    return best,best_score

def exact_local_match(org,email='',phone='',linkedin=''):
    if linkedin:
        target=normalize_linkedin(linkedin)
        a=ApplicantIndex.objects.filter(org=org,linkedin_normalized=target).first()
        if a: return a
    if email:
        a=ApplicantIndex.objects.filter(org=org,email__iexact=normalize_email(email)).first()
        if a: return a
    np=normalize_phone(phone)
    if np:
        a=ApplicantIndex.objects.filter(org=org,phone_normalized=np).first()
        if a: return a
    return None
