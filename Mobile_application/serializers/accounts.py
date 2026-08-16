from django.contrib.auth import authenticate, password_validation
from rest_framework import serializers

from accounts.models import User


class SignupSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate_email(self, email):
        email = email.lower().strip()
        if User.objects.filter(email=email, is_active=True).exists():
            raise serializers.ValidationError("An account with this email already exists. Try logging in.")
        return email

    def validate_password(self, password):
        password_validation.validate_password(password)
        return password


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(min_length=6, max_length=6)

    def validate_code(self, code):
        if not code.isdigit():
            raise serializers.ValidationError("Enter the 6-digit code.")
        return code


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()


class GoogleAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs["email"].lower().strip()
        user = authenticate(username=email, password=attrs["password"])
        if user is None:
            if User.objects.filter(email=email, is_active=False).exists():
                raise serializers.ValidationError("Please verify your email before logging in.")
            raise serializers.ValidationError("Incorrect email or password.")
        attrs["user"] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name", "display_name", "initials", "avatar_url"]
