from django.conf import settings

from .email_delivery import send_email


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
