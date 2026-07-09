# Credential Rotation Checklist (user actions)

These are the manual steps the remediation plan hands off to you (decisions 8 + Phase 0 item 4).
None of these can be done by the tooling; each is a few minutes. Do them before go-live.

## 1. OpenRouter API key (exposed in backend/.env)
- Log in at https://openrouter.ai/keys
- Revoke the key starting `sk-or-v1-2f42…`
- Create a new key; put it in `backend/.env` as `OPENROUTER_API_KEY=...` (local) and later in `/opt/labtrack/backend/.env` on the VPS.

## 2. DigitalOcean Postgres password (was in a comment in backend/.env)
- The commented-out DSN containing `AVNS_PTZ6…` has been removed from `.env`, but treat the password as burned.
- In the DO control panel: Databases → your cluster → Users → reset the password for that user (or delete the user if unused).

## 3. LabTrack default account passwords (documented publicly in this repo)
- `admin/admin123`, `qcmanager/qc123`, `labtech/lab123` are in CLAUDE.md and git history.
- After deploy, log in as admin → Settings → Users and set strong passwords for admin + qcmanager (and labtech if kept).
- Do the same on the VPS instance at go-live (its DB seeds the same defaults).

## 4. Production app secrets (enforced at startup now)
- Generate two strong values, e.g. `openssl rand -hex 32` twice.
- On the VPS set in `/opt/labtrack/backend/.env`:
  - `SECRET_KEY=<value1>`
  - `JWT_SECRET_KEY=<value2>`
  - `APP_ENV=production`
- The app now refuses to boot in production with the shipped defaults, and refuses `AI_PROVIDER=mock` in production.

## 5. VPS access hardening
- Current access is root + password (the password also sits in the project memory file — treat as burned once rotated).
- `ssh-keygen -t ed25519` (if you have no key), then `ssh-copy-id root@155.138.211.71`
- Verify key login works, then in `/etc/ssh/sshd_config` set `PasswordAuthentication no` and `systemctl restart sshd`.
- Change the root password afterward regardless: `passwd`.

## 6. After rotating
- Delete the plaintext VPS password from the Claude project memory (ask Claude to update its memory file).
- Confirm `backend/.env` is still gitignored: `git check-ignore backend/.env`.
