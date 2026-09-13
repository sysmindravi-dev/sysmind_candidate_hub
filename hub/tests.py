from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from unittest.mock import patch
from .models import *
from .services.matching import score_candidate, normalize_linkedin, normalize_phone
from .services.quota import reserve, QuotaError
from .services.processing import parse_csv, process_with_signalhire
from django.core.files.uploadedfile import SimpleUploadedFile

class MatchingTests(TestCase):
    def setUp(self):
        self.org=CeipalOrganization.objects.create(name='US',code='us',api_email='a@b.com')
        self.app=ApplicantIndex.objects.create(org=self.org,ceipal_applicant_id='enc1',full_name='Rajesh Kumar',city='Dallas',state='TX',skills='Java, AWS, Spring Boot')
    def test_name_location_skills_high_confidence(self):
        self.assertGreaterEqual(score_candidate('Rajesh Kumar','Dallas, TX','Java AWS Spring','',self.app),90)
    def test_normalizers(self):
        self.assertEqual(normalize_linkedin('https://www.linkedin.com/in/Test/?x=1'),'linkedin.com/in/test')
        self.assertEqual(normalize_phone('+1 (732) 555-1212'),'7325551212')

class CsvTests(TestCase):
    def test_flexible_headers(self):
        f=SimpleUploadedFile('x.csv',b'Candidate Name,LinkedIn URL,Current Location\\nJane Doe,https://linkedin.com/in/jane,Dallas TX\\n')
        rows=parse_csv(f); self.assertEqual(rows[0]['name'],'Jane Doe'); self.assertIn('linkedin.com',rows[0]['linkedin_url'])

class QuotaTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('r1',password='x'); self.user.profile.monthly_signalhire_limit=1; self.user.profile.save()
        self.org=CeipalOrganization.objects.create(name='US',code='us',api_email='a@b.com')
        self.req=Requirement.objects.create(org=self.org,created_by=self.user,entered_req_id='R1',ceipal_job_id='J1')
        self.batch=ImportBatch.objects.create(requirement=self.req,uploaded_by=self.user,filename='x.csv')
        AppSettings.get_solo()
    def test_user_limit_hard_stop(self):
        c1=ImportCandidate.objects.create(batch=self.batch,row_number=1,name='A'); c2=ImportCandidate.objects.create(batch=self.batch,row_number=2,name='B')
        reserve(self.user,self.req,c1)
        with self.assertRaises(QuotaError): reserve(self.user,self.req,c2)

class RetrySafetyTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('r2',password='x'); self.org=CeipalOrganization.objects.create(name='US',code='us2',api_email='a@b.com',use_apply_for_existing_tagging=True)
        self.req=Requirement.objects.create(org=self.org,created_by=self.user,entered_req_id='R2',ceipal_job_id='J2')
        self.batch=ImportBatch.objects.create(requirement=self.req,uploaded_by=self.user,filename='x.csv')
        self.c=ImportCandidate.objects.create(batch=self.batch,row_number=1,name='Jane Doe',linkedin_url='https://linkedin.com/in/jane',signalhire_status='success',signalhire_payload={'fullName':'Jane Doe','contacts':[{'type':'email','value':'jane@example.com'}]})
        AppSettings.get_solo()
    @patch('hub.services.processing.SignalHireClient.lookup_sync')
    @patch('hub.services.processing.CeipalClient.apply_without_registration')
    def test_retry_reuses_signalhire_payload(self,m_apply,m_lookup):
        m_apply.return_value={'applicantId':'A1','submissionId':'S1'}
        process_with_signalhire(self.c,self.user)
        m_lookup.assert_not_called()
