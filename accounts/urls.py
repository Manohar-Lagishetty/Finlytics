from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("signup/", views.SignupView.as_view(), name="signup"),
    path("signup/verify/", views.VerifyOTPView.as_view(), name="verify_otp"),
    path("signup/resend/", views.ResendOTPView.as_view(), name="resend_otp"),
    path("logout/", views.logout_view, name="logout"),
]
