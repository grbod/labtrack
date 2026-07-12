"""Tests for the email intake webhook config + sender allowlist.

The Microsoft 365 mailbox poller was removed; the Cloudflare Email Worker
webhook (POST /api/v1/result-imports/intake) is the only intake path. Endpoint
behaviour is covered in tests/test_result_import_intake_endpoint.py; this file
covers the config guards and the relocated sender-allowlist helper.
"""

import pytest
from pydantic import ValidationError

from app.config import Settings, settings
from app.services.sender_allowlist import sender_allowed

# -- Fix #4: intake token normalization + production strength guard -----

_PROD_SECRETS = dict(
    app_env="production",
    ai_provider="openrouter",
    secret_key="a-strong-unique-secret-key-for-tests-1234567890",
    jwt_secret_key="a-strong-unique-jwt-secret-key-for-tests-1234567890",
)


def test_whitespace_only_token_normalizes_to_none():
    # A whitespace-only token must leave the endpoint inert (treated as unset),
    # not active with a guessable secret.
    assert Settings(intake_webhook_token="   ").intake_webhook_token is None
    assert Settings(intake_webhook_token="\t\n").intake_webhook_token is None


def test_token_is_stripped():
    config = Settings(intake_webhook_token="  " + "a" * 40 + "  ")
    assert config.intake_webhook_token == "a" * 40


def test_production_short_token_raises():
    with pytest.raises(ValidationError) as exc_info:
        Settings(intake_webhook_token="short", **_PROD_SECRETS)
    assert "INTAKE_WEBHOOK_TOKEN" in str(exc_info.value)


def test_production_strong_token_ok():
    token = "a" * 64
    config = Settings(intake_webhook_token=token, **_PROD_SECRETS)
    assert config.intake_webhook_token == token


def test_production_no_token_ok():
    # No intake token configured is fine in production (feature is inert).
    assert Settings(**_PROD_SECRETS).intake_webhook_token is None


# -- Fix #1: sender allowlist deny-by-default ---------------------------


def test_sender_allowlist_empty_denies_all(monkeypatch):
    # Deny-by-default: an empty allowlist must reject every sender, not accept
    # all — it is the only sender gate on the webhook path.
    monkeypatch.setattr(settings, "email_intake_allowed_senders", "")
    assert not sender_allowed("anyone@anywhere.com")


def test_sender_allowlist_whitespace_only_denies_all(monkeypatch):
    monkeypatch.setattr(settings, "email_intake_allowed_senders", " , ,  ")
    assert not sender_allowed("anyone@anywhere.com")


def test_sender_allowlist_matches_address_and_domain(monkeypatch):
    monkeypatch.setattr(
        settings,
        "email_intake_allowed_senders",
        "reports@daanelabs.com, @bodynutrition.com",
    )
    assert sender_allowed("reports@daanelabs.com")
    assert sender_allowed("Reports@DaaneLabs.com")
    assert sender_allowed("greg@bodynutrition.com")
    assert not sender_allowed("spoof@evil.com")
    assert not sender_allowed("other@daanelabs.com")
