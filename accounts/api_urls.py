from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import api_views

app_name = "accounts_api"

urlpatterns = [
    path("signup/", api_views.signup, name="signup"),
    path("verify-otp/", api_views.verify_otp, name="verify_otp"),
    path("resend-otp/", api_views.resend_otp, name="resend_otp"),
    path("login/", api_views.login, name="login"),
    path("google/", api_views.google_login, name="google_login"),
    path("logout/", api_views.logout, name="logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", api_views.me, name="me"),
]
