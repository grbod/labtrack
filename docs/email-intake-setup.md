# Email Intake Setup (forward lab reports to an inbox)

LabTrack can ingest forwarded lab-report PDFs by email. Forwarded reports
behave exactly like drag-and-drop uploads: same hash dedup, same LLM
extraction, same "Needs review" queue and review modal, and confirmed rows
still land as DRAFT test results.

Two transports are supported; enable either or both:

1. **Cloudflare Email Routing → intake webhook** (production setup):
   mail to `labs@bodytools.work` hits a Cloudflare Email Worker that POSTs
   the PDF attachments to LabTrack. Push-based, no mailbox to manage.
2. **Microsoft 365 mailbox poller**: the backend polls a shared mailbox via
   Graph. Useful if you'd rather keep everything in M365.

Both paths attribute uploads to `EMAIL_INTAKE_UPLOAD_USERNAME` (default
`admin`) and enforce the same `EMAIL_INTAKE_ALLOWED_SENDERS` allowlist.

## Option 1: Cloudflare Email Routing (labs@bodytools.work)

Flow: sender → Cloudflare Email Routing → Email Worker
(`deploy/cloudflare-email-worker/`) → `POST /api/v1/result-imports/intake`
on `labtrack.bodytools.work`, authenticated by a shared secret header.

Behavior:
- Only PDF attachments are ingested. A message with no PDFs, a disallowed
  sender, or PDFs the importer rejects (size/page limits) is **bounced back
  to the sender with the reason**, so the forwarder knows nothing landed.
- Re-forwarding the same PDF is safe (hash dedup).
- Sender identity is the SMTP `From` address; Cloudflare validates
  SPF/DKIM on receipt before the worker runs.

### Backend (`backend/.env` on the VPS)

```bash
INTAKE_WEBHOOK_TOKEN=<openssl rand -hex 32>
EMAIL_INTAKE_ALLOWED_SENDERS=@bodynutrition.com,@daanelabs.com
EMAIL_INTAKE_UPLOAD_USERNAME=admin
```

With `INTAKE_WEBHOOK_TOKEN` unset the endpoint answers 404 and the feature
is inert. Restart the API service after editing.

### Worker (one-time)

```bash
cd deploy/cloudflare-email-worker
npm install
npx wrangler login                       # Cloudflare account with bodytools.work
npx wrangler secret put INTAKE_TOKEN     # paste the same token as the VPS .env
npx wrangler deploy
```

Then in the Cloudflare dashboard for **bodytools.work**:
1. **Email → Email Routing → Get started** (adds the MX/SPF records).
2. **Routing rules → Create address**: `labs@bodytools.work` → action
   **Send to a Worker** → `labtrack-email-intake`.

Watch it live with `npx wrangler tail`. To test end-to-end, email a lab
report PDF to `labs@bodytools.work` from an allowed address and check the
Lab Test Import queue.

## Option 2: Microsoft 365 mailbox poller

## How it behaves

- The backend polls the mailbox inbox (default every 120s) for **unread
  messages with attachments**.
- PDF attachments are ingested; the message is marked read and moved to the
  **"LabTrack Processed"** folder.
- Messages that can't be used (sender not on the allowlist, no PDF attachment,
  or every PDF rejected, e.g. over the page/size limit) are marked read and
  moved to **"LabTrack Rejected"** so a human can see what was dropped.
- Re-forwarding the same PDF is harmless: the importer's content-hash dedup
  points at the existing import instead of creating a new one.
- Uploads are attributed to the user in `EMAIL_INTAKE_UPLOAD_USERNAME`
  (default `admin`) in the import ledger.
- Transient Graph errors leave the message unread; it is retried on the next
  poll.

## One-time Azure setup

1. **Create the mailbox** (e.g. `results@bodynutrition.com`) — a shared
   mailbox is fine (no license needed).
2. **Register an app** in Entra ID (Azure portal → App registrations → New).
   Single tenant. No redirect URI.
3. **Grant application permission** Microsoft Graph → Application →
   `Mail.ReadWrite`, then click **Grant admin consent**.
4. **Create a client secret** (Certificates & secrets) and note the value.
5. **(Recommended) Scope the app to just this mailbox** so the credential
   cannot read other mail. In Exchange Online PowerShell:

   ```powershell
   New-DistributionGroup -Name "LabTrack Intake Scope" -Type Security -Members results@bodynutrition.com
   New-ApplicationAccessPolicy -AppId <client-id> -PolicyScopeGroupId "LabTrack Intake Scope" -AccessRight RestrictAccess
   Test-ApplicationAccessPolicy -AppId <client-id> -Identity results@bodynutrition.com   # should say Granted
   ```

## Backend configuration (`backend/.env`)

```bash
EMAIL_INTAKE_ENABLED=true
EMAIL_INTAKE_TENANT_ID=<directory (tenant) id>
EMAIL_INTAKE_CLIENT_ID=<application (client) id>
EMAIL_INTAKE_CLIENT_SECRET=<client secret value>
EMAIL_INTAKE_MAILBOX=results@bodynutrition.com
# Optional hardening / tuning:
EMAIL_INTAKE_ALLOWED_SENDERS=reports@daanelabs.com,@bodynutrition.com
EMAIL_INTAKE_POLL_SECONDS=120
EMAIL_INTAKE_UPLOAD_USERNAME=admin
```

The app refuses to start if `EMAIL_INTAKE_ENABLED=true` and any credential is
missing. With `EMAIL_INTAKE_ENABLED` unset/false the feature is completely
inert.

The poller runs inside the FastAPI process (started from the app lifespan, see
`app/main.py`), so on the VPS nothing extra is needed beyond the `.env` keys
and a service restart. Implementation: `app/services/email_intake_service.py`;
tests: `tests/test_email_intake.py`.
