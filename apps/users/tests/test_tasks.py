"""Tests for users Celery tasks."""
from datetime import timedelta
from unittest.mock import patch

import pytest
from celery.exceptions import Retry
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from apps.users.models import PasswordResetToken
from apps.users.tasks import cleanup_expired_reset_tokens, send_password_reset_email

User = get_user_model()

TOKEN = "abc123deadbeef"
EMAIL = "user@example.com"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def user(db):
    return User.objects.create_user(email=EMAIL, username="user1", password="StrongPass123")


def _make_token(user, *, hours_ago: int = 0, used: bool = False) -> PasswordResetToken:
    token = PasswordResetToken.objects.create(user=user, token=f"tok_{hours_ago}_{used}", used=used)
    if hours_ago:
        # auto_now_add prevents setting created_at at creation time, so update directly
        PasswordResetToken.objects.filter(pk=token.pk).update(
            created_at=timezone.now() - timedelta(hours=hours_ago)
        )
        token.refresh_from_db()
    return token


# ---------------------------------------------------------------------------
# send_password_reset_email
# ---------------------------------------------------------------------------

@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="noreply@example.com",
    FRONTEND_URL="http://localhost:3000",
)
def test_send_password_reset_email_sends_email():
    """Task delivers exactly one email to the correct recipient."""
    # pyright don't understand that Celery's eager test mode runs tasks synchronously
    # and re-raises exceptions, so we have to ignore the reportCallIssue here
    send_password_reset_email.apply(args=[EMAIL, TOKEN])  # pyright: ignore[reportCallIssue]

    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    assert sent.to == [EMAIL]
    assert sent.from_email == "noreply@example.com"


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="noreply@example.com",
    FRONTEND_URL="http://localhost:3000",
)
def test_send_password_reset_email_subject():
    """Task uses 'Password Reset Request' as the email subject."""
    send_password_reset_email.apply(args=[EMAIL, TOKEN])  # pyright: ignore[reportCallIssue]

    assert mail.outbox[0].subject == "Password Reset Request"


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="noreply@example.com",
    FRONTEND_URL="http://localhost:3000",
)
def test_send_password_reset_email_url_in_body():
    """Both the plain-text and HTML bodies contain the correct reset URL."""
    send_password_reset_email.apply(args=[EMAIL, TOKEN])  # pyright: ignore[reportCallIssue]

    expected_url = f"http://localhost:3000/password-reset/confirm?token={TOKEN}"
    sent = mail.outbox[0]
    assert expected_url in sent.body
    # html_message is stored in alternatives as (content, mime_type)
    html_body = sent.alternatives[0][0]  # pyright: ignore[reportAttributeAccessIssue]
    assert expected_url in html_body


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="noreply@example.com",
    FRONTEND_URL="http://localhost:3000",
)
def test_send_password_reset_email_retries_on_smtp_failure():
    """Task exhausts all retries and fails when send_mail always raises."""
    with patch("apps.users.tasks.send_mail", side_effect=Exception("SMTP connection failed")):
        result = send_password_reset_email.apply(args=[EMAIL, TOKEN])  # pyright: ignore[reportCallIssue]

    assert result.failed()
    # In eager (test) mode Celery re-raises the original exception rather than MaxRetriesExceededError
    assert "SMTP connection failed" in str(result.result)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="noreply@example.com",
    FRONTEND_URL="http://localhost:3000",
)
def test_send_password_reset_email_succeeds_after_transient_failure():
    """Task succeeds on subsequent attempt if only the first call raises."""
    call_count = 0

    def flaky_send_mail(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Transient SMTP error")

    with patch("apps.users.tasks.send_mail", side_effect=flaky_send_mail):
        result = send_password_reset_email.apply(args=[EMAIL, TOKEN])  # pyright: ignore[reportCallIssue]

    assert result.successful()
    assert call_count == 2  # failed once, succeeded on retry


# ---------------------------------------------------------------------------
# cleanup_expired_reset_tokens
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_cleanup_returns_zero_when_no_tokens(user):
    """Returns 0 and leaves the table untouched when there is nothing to delete."""
    count = cleanup_expired_reset_tokens.apply().get()  # pyright: ignore[reportFunctionMemberAccess]
    assert count == 0


@pytest.mark.django_db
def test_cleanup_deletes_only_expired_tokens(user):
    """Deletes tokens older than 1 hour but keeps fresh ones."""
    fresh = _make_token(user, hours_ago=0)
    expired_1 = _make_token(user, hours_ago=2)
    expired_2 = _make_token(user, hours_ago=24)

    count = cleanup_expired_reset_tokens.apply().get()  # pyright: ignore[reportFunctionMemberAccess]

    assert count == 2
    assert PasswordResetToken.objects.filter(pk=fresh.pk).exists()
    assert not PasswordResetToken.objects.filter(pk=expired_1.pk).exists()
    assert not PasswordResetToken.objects.filter(pk=expired_2.pk).exists()


@pytest.mark.django_db
def test_cleanup_deletes_used_expired_tokens(user):
    """Used tokens that are also expired are deleted, not preserved."""
    used_expired = _make_token(user, hours_ago=3, used=True)

    count = cleanup_expired_reset_tokens.apply().get()  # pyright: ignore[reportFunctionMemberAccess]

    assert count == 1
    assert not PasswordResetToken.objects.filter(pk=used_expired.pk).exists()


@pytest.mark.django_db
def test_cleanup_preserves_all_fresh_tokens(user):
    """No tokens are deleted when all of them are within the 1-hour window."""
    _make_token(user, hours_ago=0)

    count = cleanup_expired_reset_tokens.apply().get()  # pyright: ignore[reportFunctionMemberAccess]

    assert count == 0
    assert PasswordResetToken.objects.count() == 1
