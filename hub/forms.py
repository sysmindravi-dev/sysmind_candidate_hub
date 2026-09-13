from django import forms
from .models import CeipalOrganization

class RequirementForm(forms.Form):
    ceipal_org=forms.ModelChoiceField(queryset=CeipalOrganization.objects.none(),label='CEIPAL Environment')
    requirement_id=forms.CharField(max_length=120,label='CEIPAL Requirement ID')
    def __init__(self,*args,user=None,**kwargs):
        super().__init__(*args,**kwargs)
        if user and user.is_superuser: qs=CeipalOrganization.objects.filter(active=True)
        elif user: qs=user.profile.ceipal_orgs.filter(active=True)
        else: qs=CeipalOrganization.objects.none()
        self.fields['ceipal_org'].queryset=qs

class CSVUploadForm(forms.Form):
    csv_file=forms.FileField(label='Candidate CSV',help_text='Required: Name. Recommended: LinkedIn URL, Current Location, Skills.')
    def clean_csv_file(self):
        f=self.cleaned_data['csv_file']
        if not f.name.lower().endswith('.csv'): raise forms.ValidationError('Please upload a .csv file.')
        if f.size>10*1024*1024: raise forms.ValidationError('CSV must be 10 MB or smaller.')
        return f
