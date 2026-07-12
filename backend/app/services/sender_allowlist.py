"""Sender allowlist gate for the email intake webhook.

The Cloudflare Email Worker forwards a lab-report PDF along with the SMTP
`From` address; this is the only sender gate on the webhook path, so it fails
closed: an empty/unconfigured allowlist rejects EVERY sender (Fix #1).
"""

from __future__ import annotations

from app.config import settings


def sender_allowed(sender: str) -> bool:
    """Return True only if `sender` matches the configured allowlist.

    The allowlist is a comma-separated list of exact addresses and/or
    `@domain` suffixes. Deny-by-default: an empty allowlist returns False.
    """
    allowed = [
        entry.strip().lower()
        for entry in settings.email_intake_allowed_senders.split(",")
        if entry.strip()
    ]
    if not allowed:
        # Deny-by-default: an unconfigured allowlist must reject every sender
        # rather than accept all — see module docstring.
        return False
    sender = sender.lower()
    return any(
        sender == entry or (entry.startswith("@") and sender.endswith(entry))
        for entry in allowed
    )
