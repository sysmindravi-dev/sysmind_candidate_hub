# SysMind Candidate Hub

Internal Django application for importing sourced candidates into CEIPAL while minimizing SignalHire contact-credit usage.

## Core workflow

1. Recruiter selects CEIPAL US or CEIPAL India (based on admin-granted access).
2. Enters a CEIPAL requirement ID; app retrieves job metadata and stores the encrypted CEIPAL job ID.
3. Uploads CSV with candidate Name and preferably LinkedIn URL, Current Location and Skills.
4. App checks the local synchronized CEIPAL Applicant index first and performs fuzzy duplicate matching.
5. Existing Applicants consume **zero SignalHire credits**.
6. Unmatched candidates are ranked for job fit and only selected candidates may use SignalHire, subject to company/user/requirement hard limits.
7. After SignalHire returns email/phone/profile data, the app checks CEIPAL again before creating a new Applicant.
8. Existing Applicant: update missing details/LinkedIn, add LinkedIn-profile PDF as a secondary document (configured CEIPAL endpoint), then tag to job.
9. New Applicant: Apply Without Registration creates the Applicant and job submission together.
10. Every operation is audited.

## CEIPAL documentation alignment

Documented defaults included in the application:

- V1 auth: `/v1/createAuthtoken`
- Job list/search: `/v1/getJobPostingsList`
- Applicant list/sync: `/v1/getApplicantsList`
- Submission lookup: `/v1/getSubmissionsList`
- Create Applicant: `/v1/createApplicant`
- Apply Without Registration: `/v1/applyJobWithOutRegistration`

CEIPAL documents encrypted identifiers and bearer-token authentication. Account-specific write endpoints such as Update Applicant / secondary-document upload may require CEIPAL enablement or Custom API configuration, so those paths are intentionally editable in Django Admin rather than hard-coded.

## Safety controls

- SignalHire credit reservation is atomic at company + user + requirement level.
- Paid lookups are not repeated after a successful enrichment if a later CEIPAL action fails.
- Existing Applicant tagging checks current CEIPAL submissions first.
- CEIPAL API secrets and SignalHire key are encrypted at rest using `APP_ENCRYPTION_KEY`.
- Recruiters never see API credentials.
- US and India CEIPAL IDs are namespaced by organization in the local database.
- Failed API operations remain visible and retryable instead of silently dropping candidates.

## Local developer run

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The production deployment walkthrough is in `docs/DEPLOY_DIGITALOCEAN.md`.

## Important production validation

External APIs cannot be fully integration-tested without your actual CEIPAL/SignalHire credentials and account-enabled CEIPAL write endpoints. Before real recruiter use, complete sections 11–14 of the deployment guide with sandbox/test Applicants. That validates the account-specific behavior that code alone cannot prove, especially whether Apply Without Registration safely reuses an existing Applicant.
