from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.mail import BadHeaderError
from django.shortcuts import redirect, render
from django.views import View
from django.views.decorators.http import require_POST

from .forms import LoginForm, OTPForm, SignupForm
from .models import OTP, User
from .utils import send_otp_email

PENDING_SESSION_KEY = "pending_signup_user_id"


class SignupView(View):
    template_name = "accounts/signup.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("dashboard:home")
        return render(request, self.template_name, {"form": SignupForm()})

    def post(self, request):
        form = SignupForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        user = User.objects.create_user(
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password1"],
            full_name=form.cleaned_data["full_name"],
            is_active=False,
            signup_method="email",
        )
        otp = OTP.issue_for(user)

        try:
            send_otp_email(user, otp.code)
        except (BadHeaderError, OSError, Exception):  # noqa: BLE001 - surface as a friendly message
            messages.warning(
                request,
                "Your account was created, but we couldn't send the verification email "
                "(email isn't configured yet). Add real SMTP credentials in .env and use "
                "“Resend code” once it's set up.",
            )

        request.session[PENDING_SESSION_KEY] = user.id
        return redirect("accounts:verify_otp")


class VerifyOTPView(View):
    template_name = "accounts/verify_otp.html"

    def _pending_user(self, request):
        user_id = request.session.get(PENDING_SESSION_KEY)
        if not user_id:
            return None
        return User.objects.filter(id=user_id, is_active=False).first()

    def get(self, request):
        user = self._pending_user(request)
        if not user:
            return redirect("accounts:signup")
        return render(request, self.template_name, {"form": OTPForm(), "email": user.email})

    def post(self, request):
        user = self._pending_user(request)
        if not user:
            return redirect("accounts:signup")

        form = OTPForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "email": user.email})

        code = form.cleaned_data["code"]
        otp = OTP.objects.filter(user=user, is_used=False).order_by("-created_at").first()

        if not otp or not otp.is_valid(code):
            form.add_error("code", "That code is invalid or has expired.")
            return render(request, self.template_name, {"form": form, "email": user.email})

        otp.is_used = True
        otp.save(update_fields=["is_used"])

        user.is_active = True
        user.is_email_verified = True
        user.save(update_fields=["is_active", "is_email_verified"])

        del request.session[PENDING_SESSION_KEY]
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, f"Welcome to Finlytics, {user.display_name}!")
        return redirect("dashboard:home")


class ResendOTPView(View):
    def post(self, request):
        user_id = request.session.get(PENDING_SESSION_KEY)
        user = User.objects.filter(id=user_id, is_active=False).first() if user_id else None
        if not user:
            return redirect("accounts:signup")

        otp = OTP.issue_for(user)
        try:
            send_otp_email(user, otp.code)
            messages.info(request, "A new code has been sent to your email.")
        except Exception:  # noqa: BLE001
            messages.warning(request, "Couldn't send the email — check your SMTP settings in .env.")
        return redirect("accounts:verify_otp")


class LoginView(View):
    template_name = "accounts/login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("dashboard:home")
        return render(request, self.template_name, {"form": LoginForm()})

    def post(self, request):
        form = LoginForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        email = form.cleaned_data["email"].lower().strip()
        password = form.cleaned_data["password"]
        user = authenticate(request, username=email, password=password)

        if user is None:
            if User.objects.filter(email=email, is_active=False).exists():
                form.add_error(None, "Please verify your email before logging in.")
            else:
                form.add_error(None, "Incorrect email or password.")
            return render(request, self.template_name, {"form": form})

        login(request, user)
        return redirect(request.GET.get("next") or "dashboard:home")


@login_required
@require_POST
def logout_view(request):
    logout(request)
    return redirect("core:landing")
