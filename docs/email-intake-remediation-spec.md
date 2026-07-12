# Email Intake Remediation — Implementation Spec

Derived from the 2026-07-12 adversarial review (Opus). Fixes the findings on the
email-intake feature (commits `102db85` + `375da92`). REVIEW verified every claim
in code; this spec is the implementation contract.

Ground rules:
- Backend Python: use `backend/.venv`. Run `make format` (black+isort) and the
  affected pytest files when done. Baseline suite ~4,914 green — don't regress.
- Nothing is pushed; local-only. Do NOT push or deploy.
- Keep the two intake paths (Cloudflare webhook + M365 poller) behaviourally
  consistent where they share code (`_sender_allowed`, `create_uploads`).
- Add/extend tests for each fix's adversarial case — not just happy path.
- Update `docs/email-intake-setup.md` wherever behaviour or defaults change.

Key files:
- `backend/app/api/v1/endpoints/result_imports.py` — intake endpoint
- `backend/app/config.py` — settings + validators
- `backend/app/services/email_intake_service.py` — M365 poller + `_sender_allowed`
- `backend/app/services/result_import_service.py` — `create_uploads` validation
- `backend/app/core/rate_limit.py` — `limiter`
- `deploy/cloudflare-email-worker/src/index.js` — worker
- `backend/app/seed.py` — seed users
- tests: `backend/tests/test_email_intake.py`, intake-endpoint tests

---

## Fix #1 (HIGH) — Allowlist deny-by-default

Problem: `EmailIntakeService._sender_allowed` returns `True` when the allowlist is
empty (`email_intake_service.py:134-135`). Empty allowlist = accept every sender.
This is the ONLY sender gate on the webhook path.

Change:
- `_sender_allowed`: when the parsed allowlist is empty, return `False` (deny all).
- Add a startup check in `config.py`: if intake is reachable (either
  `intake_webhook_token` is set OR `email_intake_enabled` is true) AND
  `email_intake_allowed_senders` is empty, log a loud WARNING at startup that
  intake will reject ALL senders until an allowlist is configured. (Warn, don't
  hard-fail — a deny-all default is safe.)
- Update the `config.py` comment (`:122`) and `email-intake-setup.md` — empty now
  means deny-all, not allow-all.

Tests: flip `test_sender_allowlist_empty_allows_all` to assert empty ⇒ deny.
Add a case: configured allowlist still matches address + `@domain`.

## Fix #2 (HIGH) — Enforce DMARC/SPF verdict in the worker

Problem: worker forwards `message.from` verbatim; nothing checks Cloudflare's
auth verdict, so `From:` is spoofable and defeats the allowlist.

Change (`deploy/cloudflare-email-worker/src/index.js`):
- Read `message.headers.get("authentication-results")` (Cloudflare sets it after
  running SPF/DKIM/DMARC). Parse for `dmarc=pass`. If DMARC is not `pass`,
  `message.setReject("Message failed sender authentication (DMARC).")` and return
  BEFORE forwarding. If the header is missing entirely, treat as fail (reject).
- Defense in depth: also forward the verdict to the backend as header
  `X-Intake-Auth-Results` so the backend has an audit signal (backend does not
  need to hard-require it in this pass, but log it).
- Document the exact reject behaviour in `email-intake-setup.md` (replace the
  inaccurate "Cloudflare validates SPF/DKIM on receipt" line with what the worker
  actually enforces).

Note: Email Workers can read `message.headers`; verify the property name against
Cloudflare's current Email Worker API (it is a standard `Headers` object).

## Fix #3 (MEDIUM) — Rate limit + per-sender cap on /intake

Problem: `/intake` has no limiter; each accepted PDF is a paid LLM call.

Change (`result_imports.py`):
- Add `request: Request` param to `intake_result_imports` and decorate with
  `@limiter.limit("30/minute")` (per-IP floor — note the caller is Cloudflare's
  IPs, so this is coarse; keep it as a backstop).
- Add a lightweight per-sender hourly cap: reject (HTTP 429) when a single
  `sender` has submitted more than N (default 20) PDFs in the trailing hour.
  Implement as a small in-process counter keyed by normalized sender with a
  time window, OR a query over `ResultImport` created in the last hour
  attributable to intake — choose the simpler correct option and document the
  choice. Make the cap a setting (`EMAIL_INTAKE_SENDER_HOURLY_CAP`, default 20).

Tests: token-valid + allowlisted sender exceeding the cap gets 429; under the cap
succeeds.

## Fix #4 (MEDIUM) — Production guard on token strength + whitespace token

Problem: `_guard_production_secrets` (`config.py:164`) checks only SECRET_KEY /
JWT_SECRET_KEY. A short/weak `intake_webhook_token` passes in prod; a
whitespace-only token (`" "`) leaves the endpoint ACTIVE (`not " "` is False)
with a guessable secret.

Change (`config.py`):
- Normalize: treat a whitespace-only `intake_webhook_token` as unset (strip; if
  empty after strip, set to None) so the endpoint is inert, matching the empty
  case. Do this in the `after` validator.
- In `_guard_production_secrets`: if `environment == production` and the token is
  set, require `len(token) >= 32`; raise ValueError otherwise (same style as the
  secret-key guard).

Tests: whitespace token ⇒ endpoint 404; prod + short token ⇒ startup raises;
prod + 64-hex token ⇒ ok.

## Fix #5 (MEDIUM) — Kill bounce backscatter / enumeration

Problem: worker echoes the backend's 403 detail (which names the sender and
config) into `setReject`, confirming the address is live and probing the
allowlist.

Change:
- Backend (`result_imports.py`): make the 403 for a disallowed sender return a
  GENERIC detail (e.g. "Message not accepted.") — do not echo the sender or the
  word "allowlist". Log the real reason server-side only.
- Worker (`index.js`): do not echo backend `detail` for auth/allowlist failures.
  Use a single generic reject string for any non-2xx that is not a
  content-problem (400). Keep a specific reason only for the local
  "no PDF attachments" case. Prefer a generic message overall to avoid
  enumeration. Log the real status/detail via `console.error` (server-side only).

Tests: disallowed sender ⇒ backend detail contains no sender string / no
"allow".

## Fix #6 (MEDIUM) — De-privilege the upload user + tag email origin

Problem: both paths default `EMAIL_INTAKE_UPLOAD_USERNAME=admin`; the audit row
is indistinguishable from a real admin UI upload.

Change:
- Seed a dedicated low-privilege service user (username `email-intake`, role
  READ_ONLY, unusable/random password, active) in `backend/app/seed.py`. Confirm
  `create_uploads` does not gate on role (it takes `user_id` only) so READ_ONLY
  works for attribution. If any downstream step needs a higher role, use LAB_TECH
  instead and note why.
- Change the config default `email_intake_upload_username` from `admin` to
  `email-intake`.
- Add an optional `source` param (e.g. `source: str = "ui"`) and optional
  `sender: Optional[str]` to `create_uploads`; when `source == "email"`, set the
  audit `reason` to something like `"Result import via email intake"` and include
  `source` + `sender` in the audit `new_values`. Both intake callers
  (`result_imports.py` intake endpoint and `email_intake_service._ingest_pdf`)
  pass `source="email"` and the sender. The UI path keeps the default.
- Update `email-intake-setup.md` (default user changed; note the READ_ONLY
  service account).

Tests: intake upload's audit row records source=email + sender and a non-admin
user; UI upload unchanged.

## Fix #7 (MEDIUM) — Poller: transient vs permanent + poison-message dead-letter + ordering

Problems (`email_intake_service.py:178-263`):
(a) A missing `OPENROUTER_API_KEY` raises `ValueError` from `create_uploads`,
    caught per-attachment as permanent ⇒ legit report filed to Rejected and lost.
(b) A message that always errors reappears every poll; `FETCH_TOP=10` with no
    ordering lets ≥10 bad messages starve new mail.

Change:
- Distinguish transient from permanent. Simplest robust approach: BEFORE the
  per-message loop, check the operational preconditions that `create_uploads`
  would raise on (e.g. `settings.openrouter_api_key` missing while provider !=
  mock) and if so, abort the poll early leaving all messages unread (transient) —
  do not classify as rejected. Keep genuine bad-PDF ValueErrors (page count,
  size, not-a-PDF, magic bytes) as permanent.
- Add `&$orderby=receivedDateTime asc` to the inbox query so oldest mail is
  processed first and new mail isn't starved.
- Poison-message dead-letter: track a per-message attempt count (in-process dict
  keyed by Graph message id is acceptable given the process-lifetime poller;
  document the tradeoff that it resets on restart). After N (default 5) transient
  failures for the same message id, move it to REJECTED with a
  "repeated processing failure" log so it stops blocking the window.

Tests: missing API key ⇒ messages left unread, none moved to Rejected; a message
that raises httpx errors N times ⇒ dead-lettered to Rejected on attempt N;
ordering param present in the request.

## Fix #8 (LOW) — PDF magic-byte validation

Problem: `create_uploads` type gate is extension/content-type only
(`result_import_service.py:127-131`); both intake paths force
`content_type=application/pdf`, so anything passes.

Change: after the content-type/extension check, reject content whose first bytes
are not `%PDF-` (`b"%PDF-"`). Applies to ALL upload paths (UI + email). Raise the
existing `ValueError("Only PDF files are allowed")` style message.

Tests: a `.pdf`-named non-PDF payload ⇒ ValueError; a real `%PDF-` payload passes
the check.

## Fix #9 (LOW) — Worker: chunk >5 PDFs + per-attachment size cap

Problem: worker POSTs all attachments in one request; >5 PDFs makes
`create_uploads` raise (whole message bounced). No per-attachment size cap.

Change (`index.js`):
- Skip attachments larger than a cap (default 10MB, matching backend
  `MAX_UPLOAD_SIZE_MB`); if all are skipped, reject with a generic size reason.
- Chunk the remaining PDFs into batches of ≤5 and POST each batch sequentially;
  aggregate ingested/duplicate counts across batches for the log line. Only
  reject the message if EVERY batch failed; otherwise succeed (partial success is
  fine — dedup makes a re-forward safe).

Tests: worker code isn't in the pytest suite; add a comment documenting the batch
size + cap and keep the logic simple/reviewable.

---

## Deliverable
- All code changes above, `make format` clean, affected pytest green.
- New/updated tests for each fix's adversarial case.
- `docs/email-intake-setup.md` updated for #1, #2, #6 (and #4 token guidance).
- A short CHANGES.md-style summary at the end of your run: per-fix, what changed
  and which tests cover it.
