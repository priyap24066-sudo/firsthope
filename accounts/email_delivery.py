import logging

from django.core.mail import send_mail

logger = logging.getLogger(__name__)

EMAIL_SEND_FAILURE_MESSAGE = 'We could not send the email right now. Please try again in a minute.'


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
