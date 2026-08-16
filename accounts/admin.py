from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import OTP, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["-date_joined"]
    list_display = ["email", "full_name", "signup_method", "is_active", "is_email_verified", "date_joined"]
    list_filter = ["signup_method", "is_active", "is_email_verified"]
    search_fields = ["email", "full_name"]
    readonly_fields = ["date_joined"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("full_name", "avatar_url", "signup_method")}),
        ("Status", {"fields": ("is_active", "is_email_verified", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("date_joined",)}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ["user", "code", "created_at", "expires_at", "is_used"]
    list_filter = ["is_used"]
    search_fields = ["user__email"]
