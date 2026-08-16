from django import forms
from django.contrib.auth import password_validation

from .models import User

INPUT_CLASSES = (
    "w-full rounded-xl border border-slate-200 dark:border-slate-700 "
    "bg-white/70 dark:bg-slate-900/60 px-4 py-3 text-sm text-slate-900 dark:text-slate-100 "
    "placeholder:text-slate-400 dark:placeholder:text-slate-500 outline-none transition "
    "focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15"
)


class SignupForm(forms.Form):
    full_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={"class": INPUT_CLASSES, "placeholder": "Full name", "autocomplete": "name"}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": INPUT_CLASSES, "placeholder": "you@example.com", "autocomplete": "email"}),
    )
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASSES, "placeholder": "Create a password", "autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASSES, "placeholder": "Confirm password", "autocomplete": "new-password"}),
    )

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email=email, is_active=True).exists():
            raise forms.ValidationError("An account with this email already exists. Try logging in.")
        return email

    def clean_password1(self):
        password1 = self.cleaned_data.get("password1")
        password_validation.validate_password(password1)
        return password1

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Passwords do not match.")
        return cleaned_data


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": INPUT_CLASSES, "placeholder": "you@example.com", "autocomplete": "email"}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASSES, "placeholder": "Your password", "autocomplete": "current-password"}),
    )


class OTPForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(
            attrs={
                "class": "otp-input",
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "pattern": "[0-9]*",
            }
        ),
    )

    def clean_code(self):
        code = self.cleaned_data["code"]
        if not code.isdigit():
            raise forms.ValidationError("Enter the 6-digit code.")
        return code
