from django.conf import settings
from django.core.mail import BadHeaderError
from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import OTP, User
from accounts.utils import send_otp_email

from ..serializers.accounts import (
    GoogleAuthSerializer,
    LoginSerializer,
    ResendOTPSerializer,
    SignupSerializer,
    UserSerializer,
    VerifyOTPSerializer,
)


def _tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


@api_view(["POST"])
@permission_classes([AllowAny])
def signup(request):
    serializer = SignupSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    # validate_email() lets a still-unverified signup retry with the same
    # address - reuse that row instead of inserting a second one, which
    # would trip the email column's DB-level unique constraint.
    user = User.objects.filter(email=data["email"], is_active=False).first()
    if user is not None:
        user.full_name = data["full_name"]
        user.set_password(data["password"])
        user.signup_method = "email"
        user.save(update_fields=["full_name", "password", "signup_method"])
    else:
        user = User.objects.create_user(
            email=data["email"],
            password=data["password"],
            full_name=data["full_name"],
            is_active=False,
            signup_method="email",
        )
    otp = OTP.issue_for(user)

    email_sent = True
    try:
        send_otp_email(user, otp.code)
    except (BadHeaderError, OSError, Exception):  # noqa: BLE001 - surface as a friendly message
        email_sent = False

    return Response(
        {"email": user.email, "email_sent": email_sent},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_otp(request):
    serializer = VerifyOTPSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    user = User.objects.filter(email=data["email"].lower().strip(), is_active=False).first()
    if not user:
        return Response({"detail": "No pending signup for this email."}, status=status.HTTP_400_BAD_REQUEST)

    otp = OTP.objects.filter(user=user, is_used=False).order_by("-created_at").first()
    if not otp or not otp.is_valid(data["code"]):
        return Response({"detail": "That code is invalid or has expired."}, status=status.HTTP_400_BAD_REQUEST)

    otp.is_used = True
    otp.save(update_fields=["is_used"])
    user.is_active = True
    user.is_email_verified = True
    user.save(update_fields=["is_active", "is_email_verified"])

    return Response({**_tokens_for(user), "user": UserSerializer(user).data})


@api_view(["POST"])
@permission_classes([AllowAny])
def resend_otp(request):
    serializer = ResendOTPSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = User.objects.filter(email=serializer.validated_data["email"].lower().strip(), is_active=False).first()
    if not user:
        return Response({"detail": "No pending signup for this email."}, status=status.HTTP_400_BAD_REQUEST)

    otp = OTP.issue_for(user)
    email_sent = True
    try:
        send_otp_email(user, otp.code)
    except Exception:  # noqa: BLE001
        email_sent = False

    return Response({"email_sent": email_sent})


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data["user"]

    return Response({**_tokens_for(user), "user": UserSerializer(user).data})


@api_view(["POST"])
@permission_classes([AllowAny])
def google_login(request):
    """Sign in/up via Google on the mobile app. The client (google_sign_in
    package) is configured with `serverClientId` = GOOGLE_CLIENT_ID, so the
    id_token it hands us is verifiable here with that same audience - no
    OTP needed, Google already verified the email."""
    serializer = GoogleAuthSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        claims = google_id_token.verify_oauth2_token(
            serializer.validated_data["id_token"], google_requests.Request(), audience=settings.GOOGLE_CLIENT_ID
        )
    except (ValueError, GoogleAuthError):
        return Response({"detail": "That Google sign-in couldn't be verified."}, status=status.HTTP_400_BAD_REQUEST)

    if not claims.get("email_verified"):
        return Response({"detail": "Your Google account's email isn't verified."}, status=status.HTTP_400_BAD_REQUEST)

    email = claims["email"].lower().strip()
    full_name = claims.get("name") or f"{claims.get('given_name', '')} {claims.get('family_name', '')}".strip()

    user = User.objects.filter(email=email).first()
    if user is None:
        user = User.objects.create_user(
            email=email,
            password=None,
            full_name=full_name or email.split("@")[0],
            avatar_url=claims.get("picture", "") or "",
            is_active=True,
            is_email_verified=True,
            signup_method="google",
        )
    elif not user.is_active:
        user.is_active = True
        user.is_email_verified = True
        user.full_name = user.full_name or full_name
        user.save(update_fields=["is_active", "is_email_verified", "full_name"])

    return Response({**_tokens_for(user), "user": UserSerializer(user).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    # No refresh-token blacklist for v1 (see plan) - the app just discards
    # its stored tokens locally; the refresh token expires naturally.
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(UserSerializer(request.user).data)
