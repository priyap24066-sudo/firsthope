import logging

from django.conf import settings
from django.core.mail import get_connection, send_mail
from django.core.mail.backends.base import BaseEmailBackend


logger = logging.getLogger(__name__)

EMAIL_SEND_FAILURE_MESSAGE = 'We could not send the email right now. Please try again in a minute.'
ADMIN_EMAIL_WARNING = 'Saved, but the email could not be sent.'


class FailSafeEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        try:
            backend = get_connection(backend=settings.EMAIL_TRANSPORT_BACKEND)
            return backend.send_messages(email_messages)
        except Exception as exc:
            logger.error('Email delivery failed (%s)', type(exc).__name__)
            return 0


def send_email(subject, message, from_email, recipient_list):
    try:
        return bool(send_mail(
            subject,
            message,
            from_email,
            recipient_list,
            fail_silently=False,
        ))
    except Exception as exc:
        logger.error('Email delivery failed (%s)', type(exc).__name__)
        return False
