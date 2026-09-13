from io import BytesIO
from reportlab.lib.pagesizes import LETTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors
from reportlab.lib.units import inch

def _text(v):
    if isinstance(v,list): return ', '.join(str(x.get('name') if isinstance(x,dict) else x) for x in v)
    return str(v or '')

def generate_profile_pdf(person):
    buf=BytesIO(); styles=getSampleStyleSheet()
    title=ParagraphStyle('Title2',parent=styles['Title'],fontSize=18,leading=22,spaceAfter=8)
    h=ParagraphStyle('H',parent=styles['Heading2'],fontSize=11,leading=14,spaceBefore=10,spaceAfter=4)
    body=ParagraphStyle('B',parent=styles['BodyText'],fontSize=9,leading=12)
    doc=SimpleDocTemplate(buf,pagesize=LETTER,rightMargin=.55*inch,leftMargin=.55*inch,topMargin=.55*inch,bottomMargin=.55*inch)
    story=[Paragraph(_text(person.get('full_name')) or 'Candidate Profile',title)]
    contact=[]
    for label,key in [('Location','location'),('Email','email'),('Phone','phone'),('LinkedIn','linkedin_url')]:
        if person.get(key): contact.append([label,Paragraph(_text(person[key]),body)])
    if contact:
        t=Table(contact,colWidths=[.8*inch,6.4*inch]); t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('BOTTOMPADDING',(0,0),(-1,-1),4)])); story += [t,Spacer(1,8)]
    raw=person.get('raw') or {}
    if person.get('job_title') or person.get('current_company'):
        story += [Paragraph('Current Position',h),Paragraph(f"{_text(person.get('job_title'))}{' — ' if person.get('job_title') and person.get('current_company') else ''}{_text(person.get('current_company'))}",body)]
    if person.get('skills'):
        story += [Paragraph('Skills',h),Paragraph(_text(person.get('skills')),body)]
    exp=raw.get('experience') or []
    if exp:
        story.append(Paragraph('Experience',h))
        for e in exp[:20]:
            if not isinstance(e,dict): continue
            line=' — '.join(x for x in [_text(e.get('position') or e.get('title')),_text(e.get('company') or e.get('companyName'))] if x)
            dates=' to '.join(x for x in [_text(e.get('startDate') or e.get('from')),_text(e.get('endDate') or e.get('to') or 'Present')] if x)
            story.append(Paragraph(f'<b>{line}</b>',body));
            if dates: story.append(Paragraph(dates,body))
            if e.get('description'): story.append(Paragraph(_text(e['description']),body))
            story.append(Spacer(1,5))
    edu=raw.get('education') or []
    if edu:
        story.append(Paragraph('Education',h))
        for e in edu[:10]:
            if isinstance(e,dict): story.append(Paragraph(' — '.join(x for x in [_text(e.get('degree')),_text(e.get('faculty') or e.get('fieldOfStudy')),_text(e.get('university') or e.get('school'))] if x),body))
    story += [Spacer(1,12),Paragraph('Generated for internal recruiting use from professional profile information returned by the configured enrichment provider.',ParagraphStyle('foot',parent=body,fontSize=7,textColor=colors.grey))]
    doc.build(story); return buf.getvalue()
