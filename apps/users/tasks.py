"""Celery tasks for the users application."""
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from apps.users.models import PasswordResetToken

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_email(self, user_email: str, reset_token: str) -> None:  # noqa: ANN001
    """Send a password reset email to the user.

    Retries up to 3 times with a 60-second delay on failure.

    Args:
        self: The task instance (automatically passed by Celery).
        user_email: The recipient's email address.
        reset_token: The plaintext password reset token.
    """
    try:
        reset_url = f"{settings.FRONTEND_URL}/password-reset/confirm?token={reset_token}"
        context = {'reset_url': reset_url, 'user_email': user_email}
        text_body = render_to_string('emails/password_reset.txt', context)
        html_body = render_to_string('emails/password_reset.html', context)
        send_mail(
            subject="Password Reset Request",
            message=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            html_message=html_body,
            fail_silently=False,
        )
        logger.info("Password reset email sent to %s", user_email)
    except Exception as exc:
        logger.exception("Failed to send password reset email to %s", user_email)
        raise self.retry(exc=exc) from exc


@shared_task
def cleanup_expired_reset_tokens() -> int:
    """Delete expired (older than 1 hour) password reset tokens.

    Returns:
        int: Number of deleted tokens.
    """
    cutoff = timezone.now() - timedelta(hours=1)
    count, _ = PasswordResetToken.objects.filter(created_at__lt=cutoff).delete()
    logger.info("Deleted %d expired password reset tokens", count)
    return count
