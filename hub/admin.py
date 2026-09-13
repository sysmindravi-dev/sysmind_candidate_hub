from django.contrib import admin, messages
from django import forms
from .models import *
from .services.ceipal import CeipalClient, CeipalError
from .services.signalhire import SignalHireClient

class CeipalOrgForm(forms.ModelForm):
    api_password=forms.CharField(widget=forms.PasswordInput(render_value=False),required=False,help_text='Leave blank to keep current password.')
    api_key=forms.CharField(widget=forms.PasswordInput(render_value=False),required=False,help_text='Leave blank to keep current API key.')
    class Meta: model=CeipalOrganization; fields='__all__'
    def save(self,commit=True):
        obj=super().save(commit=False)
        if self.cleaned_data.get('api_password'): obj.set_password(self.cleaned_data['api_password'])
        if self.cleaned_data.get('api_key'): obj.set_api_key(self.cleaned_data['api_key'])
        if commit: obj.save(); self.save_m2m()
        return obj

@admin.register(CeipalOrganization)
class CeipalOrganizationAdmin(admin.ModelAdmin):
    form=CeipalOrgForm; list_display=('name','code','base_url','active','updated_at'); actions=['test_connection']
    exclude=('api_password_cipher','api_key_cipher')
    @admin.action(description='Test selected CEIPAL connection(s)')
    def test_connection(self,request,queryset):
        for obj in queryset:
            try:
                CeipalClient(obj).authenticate(force=True); self.message_user(request,f'{obj.name}: connection successful.',messages.SUCCESS)
            except Exception as e: self.message_user(request,f'{obj.name}: {e}',messages.ERROR)

class AppSettingsForm(forms.ModelForm):
    signalhire_api_key=forms.CharField(widget=forms.PasswordInput(render_value=False),required=False,help_text='Leave blank to keep current key.')
    class Meta: model=AppSettings; fields='__all__'
    def save(self,commit=True):
        obj=super().save(commit=False)
        if self.cleaned_data.get('signalhire_api_key'): obj.set_signalhire_api_key(self.cleaned_data['signalhire_api_key'])
        if commit: obj.save()
        return obj

@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    form=AppSettingsForm; exclude=('signalhire_api_key_cipher',); actions=['test_signalhire']
    @admin.action(description='Test SignalHire key / show remaining credits')
    def test_signalhire(self,request,queryset):
        try: self.message_user(request,f'SignalHire connection successful. Remaining standard credits: {SignalHireClient().credits()}',messages.SUCCESS)
        except Exception as e: self.message_user(request,f'SignalHire: {e}',messages.ERROR)
    def has_add_permission(self,request): return not AppSettings.objects.exists()
    def has_delete_permission(self,request,obj=None): return False

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display=('user','monthly_signalhire_limit','is_manager'); filter_horizontal=('ceipal_orgs',); search_fields=('user__username','user__email','user__first_name','user__last_name')

@admin.register(Requirement)
class RequirementAdmin(admin.ModelAdmin):
    list_display=('entered_req_id','job_title','client_name','org','created_by','fetched_at'); search_fields=('entered_req_id','job_title','client_name'); list_filter=('org',)

@admin.register(ApplicantIndex)
class ApplicantIndexAdmin(admin.ModelAdmin):
    list_display=('full_name','email','phone','org','applicant_number','synced_at'); search_fields=('full_name','email','phone','linkedin_url','applicant_number'); list_filter=('org',)

@admin.register(SignalHireUsage)
class SignalHireUsageAdmin(admin.ModelAdmin):
    list_display=('user','requirement','candidate','status','credits','month','created_at'); list_filter=('status','month','requirement__org')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display=('created_at','user','action','requirement','candidate'); search_fields=('action','candidate__name','requirement__entered_req_id'); readonly_fields=('created_at',)

admin.site.register(ImportBatch)
admin.site.register(ImportCandidate)
admin.site.register(BackgroundTask)
