# Handoff: Adversarial Review of the Email Intake Feature

For a fresh Claude session. Goal: give the email-intake pipeline the same adversarial
review treatment every other importer surface received during the 2026-07 remediation
program. It was built AFTER that program (2026-07-10) and has never been reviewed.

## What to review

Two intake paths feeding the results importer, both landed in two commits:

1. `102db85` — **M365 poller**: polls a Microsoft 365 mailbox (Graph client-credentials
   flow) from the app lifespan, feeds PDF attachments into `create_uploads`, files mail
   into "LabTrack Processed"/"LabTrack Rejected" folders. `EMAIL_INTAKE_*` settings,
   off by default.
2. `375da92` — **Cloudflare Email Worker** (`deploy/cloudflare-email-worker/`,
   postal-mime): receives mail to labs@bodytools.work, extracts PDF attachments, POSTs
   them to `POST /api/v1/result-imports/intake` (shared-secret header,
   `INTAKE_WEBHOOK_TOKEN`, unset ⇒ endpoint inert/404). Non-PDF or rejected mail
   bounces back to the sender with a reason.

Key files: `backend/app/api/v1/endpoints/result_imports.py` (intake endpoint, ~+80
lines), `backend/app/config.py` (~L103-130 intake settings + startup guard),
`backend/app/services/` (find the email-intake poller service added by 102db85),
`deploy/cloudflare-email-worker/src/`, `wrangler.toml`, `docs/email-intake-setup.md`.
Start with `git show 102db85` and `git show 375da92` for the full file lists.

## Why this deserves a hard look

This is an **internet-facing, unauthenticated-by-design surface** (anyone can email
labs@bodytools.work) that injects attacker-controllable PDFs into the LLM-extraction →
lot-matching → DRAFT-results pipeline. The prior audit accepted PDF prompt-injection
residual risk because uploads required an authenticated lab_tech; email removes that
gate. The downstream protections that contain it (deterministic lot binding, human
confirm, DRAFT-only, release gate) were verified for UI uploads — verify they hold
end-to-end for the email path too.

## Review dimensions (adapt the wave-1 importer audit style: verify in code, quote
behavior, file:line refs, severity per finding)

1. **Webhook auth**: timing-safe token comparison? Token in a header (not URL)?
   Any bypass when misconfigured (empty-string token, whitespace)? Rate limiting /
   payload size caps on the endpoint? Does the "unset ⇒ 404/inert" claim hold?
2. **Sender allowlist**: shared with the M365 path — how is the sender determined on
   the Cloudflare path (SMTP envelope vs From header — From is trivially spoofable;
   does the worker forward SPF/DKIM/DMARC verdicts and does the backend check them)?
   Empty allowlist behavior = accept all?
3. **Bounce behavior**: bouncing rejection reasons to arbitrary senders can be a
   backscatter/enumeration vector (confirms the address is live + leaks config).
   Assess and recommend (e.g. silent drop for unallowlisted senders).
4. **Upload attribution + dedup**: which user do intake uploads run as ("upload-user
   attribution")? Does that user's audit trail distinguish email-sourced uploads? Does
   the file_hash dedup (partial unique index, active statuses) hold under concurrent
   webhook retries? What happens on Cloudflare Worker retries (at-least-once delivery)?
5. **Poller correctness (M365 path)**: poll loop failure modes (Graph 429/5xx, token
   expiry), the unread-for-retry semantics (poison-message loop risk — a message that
   crashes processing forever?), folder-move race, allowlist parity with the webhook.
6. **Worker code** (`deploy/cloudflare-email-worker/src`): attachment size limits,
   multiple attachments, zip/nested content, content-type spoofing (backend re-checks
   magic bytes? — the prior audit noted PDF magic-byte validation was DEFERRED;
   email intake raises its priority), secrets handling in wrangler.toml (is the token
   a secret binding or plaintext?).
7. **Tests**: 11 poller tests + 7 endpoint tests exist — check they cover the
   adversarial cases above, not just happy paths (esp. bad token, spoofed sender,
   oversized/multi attachment, duplicate redelivery).

## Ground rules & baselines (as of main `375da92`)

- Read `CLAUDE.md` first (accurate as of the remediation), plus
  `docs/results-importer-handoff.md` for pipeline invariants (LLM never picks the lot;
  confirm is atomic; DRAFT-only) and `docs/remediation-plan.md` for architecture.
- Backend suite baseline: ~4,914 expected green (run
  `cd backend && .venv/bin/python -m pytest tests/ -q --no-cov` first to capture the
  actual baseline before judging anything). Frontend: 92 passed / 2 pre-existing
  failures in spec-validation.test.ts; lint 65 problems. ALWAYS `backend/.venv`.
- Nothing is pushed to origin (~95 commits ahead) — local-only review, no deploy risk.
- Review-only first: produce a findings report (severity, file:line, failure scenario)
  BEFORE fixing anything; the user decides what gets fixed.
- Dev-drive quirks if you exercise the running app: Chrome-extension synthetic clicks
  don't reach this app — drive via DOM-level clicks (javascript_tool); TanStack pauses
  query retries in hidden tabs (stuck "Loading" is an automation artifact). Backend
  8009, frontend `npm run dev` (5173+; API_TARGET env can point the proxy elsewhere).

## Also worth checking while in there

- Does the intake endpoint respect the read_only middleware / role model coherently
  (it authenticates by token, not JWT — confirm middleware ordering doesn't break it)?
- Is `INTAKE_WEBHOOK_TOKEN` covered by the production startup guards (should prod
  refuse a weak/short token when the feature is enabled)?
- docs/email-intake-setup.md accuracy vs the actual code.
