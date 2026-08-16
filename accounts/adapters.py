from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class AccountAdapter(DefaultAccountAdapter):
    """We don't use allauth's own signup/login pages — only its Google OAuth flow."""

    def is_open_for_signup(self, request):
        return True

    def get_login_redirect_url(self, request):
        return "/dashboard/"


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Google already verifies the email, so social signups skip the OTP step entirely."""

    def is_open_for_signup(self, request, sociallogin):
        return True

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        full_name = data.get("name") or f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
        user.full_name = full_name or user.email.split("@")[0]
        user.avatar_url = data.get("picture", "") or ""
        user.signup_method = "google"
        user.is_active = True
        user.is_email_verified = True
        return user

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        user.is_active = True
        user.is_email_verified = True
        user.signup_method = "google"
        user.save(update_fields=["is_active", "is_email_verified", "signup_method"])
        return user
