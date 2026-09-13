# SysMind Candidate Hub — DigitalOcean Deployment

This guide assumes you do not write code. The safest production layout is:

- DigitalOcean App Platform web service: 1 shared vCPU / 1 GB to start.
- DigitalOcean Managed PostgreSQL: 1 GB / 1 vCPU.
- DigitalOcean Spaces: optional but recommended for candidate profile PDFs.
- Optional $5 worker only if you switch SignalHire from Sync to Async mode.

## 1. Create a private GitHub repository

1. Sign in to GitHub.
2. Create a **Private** repository called `sysmind-candidate-hub`.
3. Upload every file and folder from this project ZIP to the repository root.
4. Never upload `.env` or your CEIPAL/SignalHire keys.

## 2. Create PostgreSQL in DigitalOcean

1. DigitalOcean → **Create** → **Databases** → PostgreSQL.
2. Choose the same region you will use for the app (New York is a practical choice for the US workload).
3. Choose the smallest production PostgreSQL plan initially (1 GB / 1 vCPU).
4. Create the cluster.
5. Open **Connection Details** and copy the connection URI. You will add it to App Platform as `DATABASE_URL`.
6. Add the App Platform application as a trusted source after the app exists.

Do not use a development database for production candidate data.

## 3. Optional: create DigitalOcean Spaces for PDFs

1. DigitalOcean → **Create** → **Spaces Object Storage**.
2. Create a private Space, for example `sysmind-candidate-hub`.
3. Create a Spaces access key.
4. Keep the Access Key and Secret Key private.

If you skip Spaces initially, files are stored on local disk. For production, Spaces is recommended because App Platform containers are replaceable.

## 4. Create secrets locally

Generate a Django secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Generate the encryption key used to protect CEIPAL and SignalHire credentials stored in PostgreSQL:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Save both in a password manager. **Do not change `APP_ENCRYPTION_KEY` later unless the stored integration secrets are first re-encrypted**, or the app will no longer be able to decrypt them.

## 5. Create the App Platform app

1. DigitalOcean → **Create** → **App Platform**.
2. Connect GitHub and select the private `sysmind-candidate-hub` repository.
3. Select **Dockerfile** deployment.
4. Choose **1 shared vCPU / 1 GB** (`$12/month`) initially.
5. HTTP port: `8080`.
6. Run command is already in the Dockerfile. Do not replace it.

Add these environment variables under **Settings → App-Level Environment Variables**:

| Variable | Type | Value |
|---|---|---|
| `DEBUG` | General | `0` |
| `DJANGO_SECRET_KEY` | Secret | generated above |
| `APP_ENCRYPTION_KEY` | Secret | generated above |
| `DATABASE_URL` | Secret | PostgreSQL connection URI |
| `ALLOWED_HOSTS` | General | your `.ondigitalocean.app` hostname |
| `CSRF_TRUSTED_ORIGINS` | General | `https://your-hostname.ondigitalocean.app` |
| `TIME_ZONE` | General | `America/New_York` |

If using Spaces also add `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_ENDPOINT_URL`, and `AWS_S3_REGION_NAME` from `.env.example`.

## 6. Run database migrations and create the first admin

After the first deployment, open the App Platform console for the web component.

Run:

```bash
python manage.py migrate
python manage.py createsuperuser
```

For the superuser, use your own admin email/username and a strong password.

Then open:

`https://YOUR-APP/admin/`

## 7. Configure global application settings

Admin → **App settings** → Add Application Settings (only one record is allowed).

Set:

- Company monthly SignalHire limit: `2000`
- Default requirement limit: `10`
- Auto-match threshold: `90`
- Possible-match threshold: `70`
- SignalHire API key: paste your key
- SignalHire mode: **Sync** for the first deployment
- Applicant sync lookback: start with `365` days

Sync mode is intentionally recommended first because it is simpler to validate. SignalHire documents that sync/`withoutWaterfall` returns immediately but can have lower contact coverage than async waterfall mode.

## 8. Configure CEIPAL US

Admin → **Ceipal organizations** → Add.

Suggested values:

- Name: `CEIPAL US`
- Code: `us`
- Base URL: `https://api.ceipal.com`
- API email: your CEIPAL API administrator email
- API password: your CEIPAL API password
- API key: your CEIPAL API key
- Keep the documented V1 defaults already supplied for Auth, Jobs, Applicants, Submissions, Create Applicant, and Apply Without Registration.

Then select the CEIPAL US row → **Actions → Test selected CEIPAL connection(s)**.

You also need to enter your account-enabled endpoints for:

- **Update Applicant path** — the CEIPAL V2/Custom PATCH endpoint enabled for your account for updating LinkedIn/contact fields.
- **Secondary document path** — the CEIPAL endpoint you confirmed can add a secondary Applicant document without replacing the primary resume.
- **Existing tag path**, if CEIPAL supplies a direct submit/tag-existing-Applicant endpoint.

If you intend to use `Apply Without Registration` to tag an already-existing Applicant, first perform the sandbox test described in section 11. Only after it passes should you enable **Use apply for existing tagging**.

## 9. Configure CEIPAL India

Repeat section 8 as a second organization:

- Name: `CEIPAL India`
- Code: `india`
- Use the separate CEIPAL India API credentials.

The app keeps Applicant IDs, job IDs and activity separated by CEIPAL organization.

## 10. Populate the local CEIPAL Applicant matching index

From the application dashboard, click **Sync CEIPAL US** and **Sync CEIPAL India** as an administrator/manager.

The application stores only searchable metadata needed for matching (name, email, phone, location, skills, title, LinkedIn URL and CEIPAL Applicant identifiers). CEIPAL remains the system of record.

For a large historical CEIPAL database, start with a shorter sync lookback (for example 90 or 180 days), validate performance, then expand.

## 11. Mandatory sandbox test: tagging an existing Applicant

This is the single CEIPAL behavior that must be proven with your account before enabling it in production.

1. In CEIPAL sandbox, choose an Applicant who already exists.
2. Record that Applicant's CEIPAL ID and email.
3. Choose a sandbox job to which that Applicant is not tagged.
4. Call CEIPAL **Apply Without Registration** with the same email/name and the selected job.
5. Check CEIPAL.

Pass condition:

- The existing Applicant is reused.
- Exactly one new job submission/pipeline record appears.
- Applicant count does not increase.

If that happens, enable **Use apply for existing tagging** for that CEIPAL organization.

If CEIPAL creates a duplicate Applicant, leave the option disabled and enter CEIPAL's direct existing-Applicant submission/tag endpoint in **Existing tag path** instead.

## 12. Test secondary attachment behavior

Using a sandbox Applicant who already has a primary resume:

1. Configure **Secondary document path** and the CEIPAL document field name/ID.
2. Process one test candidate.
3. Confirm the generated `*_LinkedIn_Profile.pdf` appears as an additional Applicant document.
4. Confirm the original primary resume is unchanged.

Do not proceed to production until this passes.

## 13. Create recruiters later

When ready:

1. `/admin/` → Users → Add user.
2. Create username/password and user details.
3. Save.
4. Admin → User Profiles → open the new user.
5. Assign `CEIPAL US`, `CEIPAL India`, or both.
6. Set the user's monthly SignalHire limit.
7. Set **Manager** only for users who should see utilization reporting and trigger CEIPAL index synchronization.

Normal users do not see or edit API keys.

## 14. First end-to-end production validation

Use one test requirement and 3–5 candidates only.

Validate all cases separately:

1. Applicant already in CEIPAL and already tagged → no duplicate submission and no SignalHire call.
2. Applicant already in CEIPAL but not tagged → tagged once, no SignalHire call.
3. Candidate is uncertain, SignalHire finds contact, second check finds existing Applicant → enrich existing Applicant, add secondary PDF, tag once.
4. Candidate is truly new → SignalHire returns contact → Apply Without Registration creates the Applicant and submission.
5. SignalHire returns `failed` → no credit is marked consumed internally.
6. CEIPAL intentionally fails after a successful SignalHire call → Retry must reuse the saved SignalHire payload and must not call SignalHire again.
7. Requirement limit is 1 → two simultaneous users must not be able to reserve two paid calls.

## 15. When to move SignalHire to Async mode

SignalHire's async waterfall mode offers higher/fresher contact coverage. To enable it:

1. Admin → App Settings → SignalHire mode → `Async`.
2. Set a long random callback secret.
3. Add App Platform environment variable:
   `SIGNALHIRE_CALLBACK_BASE_URL=https://YOUR-APP.ondigitalocean.app`
4. Add a DigitalOcean App Platform worker from the same repository.
5. Worker command:
   `python manage.py process_tasks`
6. Smallest 512 MB worker is enough to start.

The callback endpoint acknowledges SignalHire quickly and places CEIPAL work into the database-backed task queue.

## 16. Backups and maintenance

- Enable/retain DigitalOcean managed PostgreSQL backups.
- Keep the GitHub repository private.
- Rotate CEIPAL API passwords periodically and update them through Django Admin.
- Do not rotate `APP_ENCRYPTION_KEY` casually.
- Run `python manage.py cleanup_reservations` periodically if using async SignalHire mode; it releases stale reservations older than 24 hours.
- Review `/admin/hub/auditlog/` for troubleshooting.

## 17. Scaling to 100 users

Do not scale based on registered-user count alone. Scale when CPU/RAM or response-time metrics justify it.

Recommended path:

1. Start: web 1 vCPU / 1 GB.
2. If memory or concurrent request pressure rises: web 1 vCPU / 2 GB.
3. Keep PostgreSQL at the smallest plan until metrics show database pressure.
4. Async mode: add a separate 512 MB worker.

No code changes are required to vertically scale App Platform.
