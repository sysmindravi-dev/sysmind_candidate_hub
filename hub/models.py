from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from .crypto import encrypt, decrypt

class CeipalOrganization(models.Model):
    name=models.CharField(max_length=100)
    code=models.SlugField(max_length=30, unique=True, help_text='Example: us or india')
    base_url=models.URLField(default='https://api.ceipal.com')
    api_version=models.CharField(max_length=10, default='v1')
    api_email=models.EmailField()
    api_password_cipher=models.TextField(blank=True)
    api_key_cipher=models.TextField(blank=True)
    active=models.BooleanField(default=True)
    # CEIPAL documented defaults. Paths are configurable so account-specific/custom APIs can be changed without code.
    auth_path=models.CharField(max_length=200, default='/v1/createAuthtoken')
    jobs_path=models.CharField(max_length=200, default='/v1/getJobPostingsList')
    applicants_path=models.CharField(max_length=200, default='/v1/getApplicantsList')
    applicant_exact_search_path=models.CharField(max_length=200, blank=True, help_text='Optional CEIPAL V2/Custom endpoint that supports exact email/mobile filters. If blank, the local synchronized Applicant index is used.')
    submissions_path=models.CharField(max_length=200, default='/v1/getSubmissionsList')
    apply_without_registration_path=models.CharField(max_length=200, default='/v1/applyJobWithOutRegistration')
    create_applicant_path=models.CharField(max_length=200, default='/v1/createApplicant')
    update_applicant_path=models.CharField(max_length=200, blank=True, help_text='Your CEIPAL V2/Custom PATCH endpoint for an existing Applicant.')
    secondary_document_path=models.CharField(max_length=200, blank=True, help_text='Your CEIPAL endpoint for adding a secondary Applicant document without replacing the primary resume.')
    existing_tag_path=models.CharField(max_length=200, blank=True, help_text='Preferred endpoint to tag an existing Applicant to a job using job_id + job_seeker_id. Leave blank to use Apply Without Registration only if sandbox-tested.')
    use_apply_for_existing_tagging=models.BooleanField(default=False, help_text='Enable only after confirming CEIPAL reuses an existing Applicant instead of creating a duplicate.')
    linkedin_field_name=models.CharField(max_length=100, default='linkedInProfileUrl')
    document_field_name=models.CharField(max_length=100, default='document_fields.1')
    country_default=models.CharField(max_length=20, blank=True)
    state_default=models.CharField(max_length=20, blank=True)
    created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
    def __str__(self): return self.name
    def set_password(self,v): self.api_password_cipher=encrypt(v)
    def get_password(self): return decrypt(self.api_password_cipher)
    def set_api_key(self,v): self.api_key_cipher=encrypt(v)
    def get_api_key(self): return decrypt(self.api_key_cipher)

class UserProfile(models.Model):
    user=models.OneToOneField(User,on_delete=models.CASCADE,related_name='profile')
    ceipal_orgs=models.ManyToManyField(CeipalOrganization,blank=True,related_name='user_profiles')
    monthly_signalhire_limit=models.PositiveIntegerField(default=100)
    is_manager=models.BooleanField(default=False)
    def __str__(self): return self.user.get_full_name() or self.user.username

class AppSettings(models.Model):
    singleton=models.BooleanField(default=True,unique=True,editable=False)
    company_monthly_signalhire_limit=models.PositiveIntegerField(default=2000)
    default_requirement_signalhire_limit=models.PositiveIntegerField(default=10)
    auto_match_threshold=models.PositiveIntegerField(default=90)
    possible_match_threshold=models.PositiveIntegerField(default=70)
    signalhire_api_key_cipher=models.TextField(blank=True)
    signalhire_mode=models.CharField(max_length=10,choices=[('sync','Sync'),('async','Async')],default='sync')
    signalhire_callback_secret=models.CharField(max_length=120,blank=True)
    applicant_sync_lookback_days=models.PositiveIntegerField(default=365)
    def __str__(self): return 'Application Settings'
    def set_signalhire_api_key(self,v): self.signalhire_api_key_cipher=encrypt(v)
    def get_signalhire_api_key(self): return decrypt(self.signalhire_api_key_cipher)
    @classmethod
    def get_solo(cls):
        obj,_=cls.objects.get_or_create(singleton=True)
        return obj

class Requirement(models.Model):
    org=models.ForeignKey(CeipalOrganization,on_delete=models.PROTECT)
    created_by=models.ForeignKey(User,on_delete=models.PROTECT,related_name='requirements_worked')
    entered_req_id=models.CharField(max_length=120)
    ceipal_job_id=models.CharField(max_length=500)
    job_title=models.CharField(max_length=500,blank=True)
    client_name=models.CharField(max_length=500,blank=True)
    location=models.CharField(max_length=500,blank=True)
    job_description=models.TextField(blank=True)
    skills=models.TextField(blank=True)
    signalhire_limit_override=models.PositiveIntegerField(null=True,blank=True)
    raw_data=models.JSONField(default=dict,blank=True)
    fetched_at=models.DateTimeField(default=timezone.now)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['org','ceipal_job_id'],name='unique_requirement_per_org')]
    def __str__(self): return f'{self.entered_req_id} - {self.job_title}'
    @property
    def signalhire_limit(self):
        return self.signalhire_limit_override or AppSettings.get_solo().default_requirement_signalhire_limit

class ApplicantIndex(models.Model):
    org=models.ForeignKey(CeipalOrganization,on_delete=models.CASCADE,related_name='applicant_index')
    ceipal_applicant_id=models.CharField(max_length=500)
    applicant_number=models.CharField(max_length=100,blank=True)
    first_name=models.CharField(max_length=200,blank=True); last_name=models.CharField(max_length=200,blank=True)
    full_name=models.CharField(max_length=500,blank=True,db_index=True)
    email=models.EmailField(blank=True,db_index=True); alt_email=models.EmailField(blank=True)
    phone=models.CharField(max_length=100,blank=True,db_index=True)
    city=models.CharField(max_length=200,blank=True); state=models.CharField(max_length=200,blank=True); country=models.CharField(max_length=200,blank=True)
    job_title=models.CharField(max_length=500,blank=True); skills=models.TextField(blank=True)
    linkedin_url=models.URLField(max_length=1000,blank=True,db_index=True)
    linkedin_normalized=models.CharField(max_length=1000,blank=True,db_index=True)
    phone_normalized=models.CharField(max_length=32,blank=True,db_index=True)
    resume_path=models.TextField(blank=True)
    raw_data=models.JSONField(default=dict,blank=True)
    ceipal_modified=models.DateTimeField(null=True,blank=True); synced_at=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['org','ceipal_applicant_id'],name='unique_applicant_per_org')]
    def __str__(self): return self.full_name or self.applicant_number

class ImportBatch(models.Model):
    requirement=models.ForeignKey(Requirement,on_delete=models.CASCADE,related_name='batches')
    uploaded_by=models.ForeignKey(User,on_delete=models.PROTECT)
    filename=models.CharField(max_length=500)
    row_count=models.PositiveIntegerField(default=0)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self): return f'{self.filename} ({self.row_count})'

class ImportCandidate(models.Model):
    STATUS=[('NEW','New'),('EXISTING','Existing'),('POSSIBLE','Possible Match'),('READY','Ready for SignalHire'),('PENDING','SignalHire Pending'),('COMPLETE','Complete'),('FAILED','Failed'),('SKIPPED','Skipped')]
    batch=models.ForeignKey(ImportBatch,on_delete=models.CASCADE,related_name='candidates')
    row_number=models.PositiveIntegerField()
    name=models.CharField(max_length=500)
    linkedin_url=models.URLField(max_length=1000,blank=True)
    location=models.CharField(max_length=500,blank=True)
    skills=models.TextField(blank=True)
    status=models.CharField(max_length=20,choices=STATUS,default='NEW')
    match_score=models.PositiveIntegerField(default=0)
    job_fit_score=models.PositiveIntegerField(default=0)
    matched_applicant=models.ForeignKey(ApplicantIndex,null=True,blank=True,on_delete=models.SET_NULL)
    selected=models.BooleanField(default=False)
    email=models.EmailField(blank=True); phone=models.CharField(max_length=100,blank=True)
    signalhire_request_id=models.CharField(max_length=100,blank=True)
    signalhire_status=models.CharField(max_length=50,blank=True)
    signalhire_payload=models.JSONField(default=dict,blank=True)
    ceipal_applicant_id=models.CharField(max_length=500,blank=True)
    ceipal_submission_id=models.CharField(max_length=500,blank=True)
    created_new_applicant=models.BooleanField(default=False)
    profile_pdf=models.FileField(upload_to='candidate_profiles/%Y/%m/',blank=True)
    error_message=models.TextField(blank=True)
    processing_state=models.CharField(max_length=50,default='NEW')
    created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['batch','row_number'],name='unique_row_per_batch')]
    def __str__(self): return self.name

class SignalHireUsage(models.Model):
    STATUS=[('RESERVED','Reserved'),('CONSUMED','Consumed'),('RELEASED','Released'),('FAILED','Failed')]
    user=models.ForeignKey(User,on_delete=models.PROTECT)
    requirement=models.ForeignKey(Requirement,on_delete=models.CASCADE,related_name='signalhire_usage')
    candidate=models.ForeignKey(ImportCandidate,on_delete=models.CASCADE,related_name='credit_events')
    month=models.DateField(db_index=True)
    status=models.CharField(max_length=20,choices=STATUS)
    credits=models.PositiveIntegerField(default=1)
    signalhire_remaining=models.IntegerField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        indexes=[models.Index(fields=['month','status']),models.Index(fields=['requirement','status']),models.Index(fields=['user','month','status'])]

class AuditLog(models.Model):
    user=models.ForeignKey(User,null=True,blank=True,on_delete=models.SET_NULL)
    action=models.CharField(max_length=120)
    requirement=models.ForeignKey(Requirement,null=True,blank=True,on_delete=models.SET_NULL)
    candidate=models.ForeignKey(ImportCandidate,null=True,blank=True,on_delete=models.SET_NULL)
    details=models.JSONField(default=dict,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['-created_at']

class BackgroundTask(models.Model):
    STATUS=[('PENDING','Pending'),('RUNNING','Running'),('DONE','Done'),('FAILED','Failed')]
    task_type=models.CharField(max_length=80)
    payload=models.JSONField(default=dict)
    status=models.CharField(max_length=20,choices=STATUS,default='PENDING',db_index=True)
    attempts=models.PositiveIntegerField(default=0)
    error=models.TextField(blank=True)
    available_at=models.DateTimeField(default=timezone.now)
    locked_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
