from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def send_otp_email(user, code):
    """Email a signup OTP code to the user. Fails loudly if SMTP creds are placeholders."""
    context = {"user": user, "code": code, "app_name": "Finlytics"}
    html_body = render_to_string("accounts/email/otp_email.html", context)
    text_body = strip_tags(html_body)

    send_mail(
        subject="Your Finlytics verification code",
        message=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_body,
        fail_silently=False,
    )
