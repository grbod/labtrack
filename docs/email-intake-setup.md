# Email Intake Setup (forward lab reports to an inbox)

LabTrack can ingest forwarded lab-report PDFs by email. Forwarded reports
behave exactly like drag-and-drop uploads: same hash dedup, same LLM
extraction, same "Needs review" queue and review modal, and confirmed rows
still land as DRAFT test results.

Transport: **Cloudflare Email Routing → intake webhook**. Mail to
`labs@bodytools.work` hits a Cloudflare Email Worker that POSTs the PDF
attachments to LabTrack's webhook. Push-based, no mailbox to manage.

Uploads are attributed to `EMAIL_INTAKE_UPLOAD_USERNAME` (default
`email-intake`, a seeded READ_ONLY service account) and every sender must pass
the `EMAIL_INTAKE_ALLOWED_SENDERS` allowlist.

> **Allowlist is deny-by-default.** An empty `EMAIL_INTAKE_ALLOWED_SENDERS`
> rejects **every** sender (it does not accept all). Intake stays inert until
> you configure at least one address or `@domain`. Startup logs a loud WARNING
> if intake is reachable with an empty allowlist.

## Cloudflare Email Routing (labs@bodytools.work)

Flow: sender → Cloudflare Email Routing → Email Worker
(`deploy/cloudflare-email-worker/`) → `POST /api/v1/result-imports/intake`
on `labtrack.bodytools.work`, authenticated by a shared secret header.

Behavior:
- Only PDF attachments are ingested. A message with no PDFs, a disallowed
  sender, or PDFs the importer rejects (size/page limits) is **bounced back
  to the sender with the reason**, so the forwarder knows nothing landed.
- Re-forwarding the same PDF is safe (hash dedup).
- Sender identity is the RFC 5322 **`From:` header** address (the identity
  DMARC actually authenticates) — *not* `message.from`, which is the SMTP
  envelope MAIL FROM and is unauthenticated/spoofable. The allowlist gates on
  this header `From`.
- Cloudflare runs SPF/DKIM/DMARC on receipt and stamps the verdict in an
  `Authentication-Results` header carrying its own authserv-id
  (`mx.cloudflare.net`). The worker evaluates DMARC **only** from that
  Cloudflare-stamped header (so a sender-supplied `Authentication-Results:
  dmarc=pass` can't forge a pass) and **requires `dmarc=pass`**, rejecting
  otherwise (including a missing verdict). The trusted verdict is forwarded to
  the backend as `X-Intake-Auth-Results` (logged as an audit signal).
  - **Verify once with a spoof test:** this relies on Cloudflare stripping
    inbound `Authentication-Results` bearing its own authserv-id (RFC 8601
    §7.1). Before trusting it in production, send a test message forging
    `From: someone@bodynutrition.com` from an unrelated domain and confirm it
    is rejected (DMARC), and a genuine allowlisted, DMARC-passing sender is
    accepted.
- Rejections use a single generic bounce ("Message not accepted.") so a prober
  cannot tell whether an address is live or on the allowlist. The specific
  reason is logged (worker `console.error`, backend logs), never bounced.
- Oversize attachments (> `MAX_UPLOAD_SIZE_MB`, default 10MB) are skipped, and
  more than 5 PDFs are POSTed in batches of 5; the message succeeds if any
  batch lands.

### Backend (`backend/.env` on the VPS)

```bash
INTAKE_WEBHOOK_TOKEN=<openssl rand -hex 32>
EMAIL_INTAKE_ALLOWED_SENDERS=@bodynutrition.com,@daanelabs.com
# Optional: defaults to the seeded READ_ONLY `email-intake` service account.
EMAIL_INTAKE_UPLOAD_USERNAME=email-intake
# Optional: reject a single sender submitting more than this many PDFs/hour.
EMAIL_INTAKE_SENDER_HOURLY_CAP=20
```

With `INTAKE_WEBHOOK_TOKEN` unset (or whitespace-only) the endpoint answers
404 and the feature is inert. In production the token must be at least 32
characters or the app refuses to start (`openssl rand -hex 32` gives 64).
The endpoint is also rate-limited to 30 requests/minute per IP and to
`EMAIL_INTAKE_SENDER_HOURLY_CAP` PDFs/hour per sender. Restart the API service
after editing.

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

Implementation: worker in `deploy/cloudflare-email-worker/src/index.js`;
backend endpoint in `app/api/v1/endpoints/result_imports.py` (intake) with the
sender gate in `app/services/sender_allowlist.py`. Tests:
`tests/test_result_import_intake_endpoint.py` and `tests/test_email_intake.py`.
