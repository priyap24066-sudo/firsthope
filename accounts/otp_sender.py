import logging
from django.conf import settings

from .email_delivery import send_email

logger = logging.getLogger(__name__)


def send_email_otp(user, code, purpose):
    """
    Send an OTP via email using Django's email framework.
    In local development with no EMAIL_HOST set, console backend prints to console.
    """
    subject = "FirstHope Verification Code"
    action = "complete your registration" if purpose == "register" else "sign in to your account"
    message = (
        f"Hello {user.username},\n\n"
        f"Your FirstHope verification code to {action} is: {code}\n\n"
        f"This code is valid for 10 minutes.\n"
        f"If you did not request this, ignore this email.\n\n"
        f"- The FirstHope Team"
    )
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'FirstHope <noreply@firsthope.com>')
    return send_email(subject, message, from_email, [user.email])


def send_sms_otp(user, code, purpose):
    """
    Provider-agnostic stub for sending OTP via SMS.
    If SMS_PROVIDER is not configured, this stub will not crash and returns False.

    PLUG-IN INSTRUCTIONS:
    To plug in an SMS gateway such as MSG91, Twilio, or Fast2SMS:
    1. Set SMS_PROVIDER in environment variables (e.g. 'twilio' or 'msg91').
    2. Configure credentials in environment variables (e.g. TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER).
    3. Implement the API call below, e.g.:

       if provider == 'twilio':
           from twilio.rest import Client
           client = Client(os.environ['TWILIO_ACCOUNT_SID'], os.environ['TWILIO_AUTH_TOKEN'])
           client.messages.create(
               body=f"Your FirstHope verification code is {code}. Valid for 10 minutes.",
               from_=os.environ['TWILIO_FROM_NUMBER'],
               to=user.phone
           )
           return True
    """
    provider = getattr(settings, 'SMS_PROVIDER', None)
    if not provider:
        # Provider not configured - return False gracefully without crashing
        return False

    phone = getattr(user, 'phone', None)
    if not phone:
        return False

    # SMS gateway logic goes here when provider is configured
    return True


def is_sms_configured():
    return bool(getattr(settings, 'SMS_PROVIDER', None))
