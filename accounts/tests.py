from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from django.urls import reverse
from google.auth.exceptions import GoogleAuthError
from rest_framework import status
from rest_framework.test import APITestCase

from .models import OTP, User

VALID_PASSWORD = "S3curePass!23"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class SignupFlowTests(APITestCase):
    def test_signup_creates_inactive_user_and_sends_otp(self):
        response = self.client.post(
            reverse("accounts_api:signup"),
            {"full_name": "Ada Lovelace", "email": "ada@example.com", "password": VALID_PASSWORD},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["email_sent"])

        user = User.objects.get(email="ada@example.com")
        self.assertFalse(user.is_active)
        self.assertTrue(OTP.objects.filter(user=user).exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_signup_rejects_duplicate_active_email(self):
        User.objects.create_user(email="ada@example.com", password=VALID_PASSWORD, is_active=True)

        response = self.client.post(
            reverse("accounts_api:signup"),
            {"full_name": "Ada", "email": "ada@example.com", "password": VALID_PASSWORD},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_signup_allows_email_stuck_in_unverified_state(self):
        User.objects.create_user(email="ada@example.com", password=VALID_PASSWORD, is_active=False)

        response = self.client.post(
            reverse("accounts_api:signup"),
            {"full_name": "Ada", "email": "ada@example.com", "password": VALID_PASSWORD},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class VerifyOTPTests(APITestCase):
    def setUp(self):
        self.client.post(
            reverse("accounts_api:signup"),
            {"full_name": "Ada", "email": "ada@example.com", "password": VALID_PASSWORD},
        )
        self.user = User.objects.get(email="ada@example.com")
        self.otp = self.user.otps.first()

    def test_verify_otp_activates_user_and_returns_tokens(self):
        response = self.client.post(
            reverse("accounts_api:verify_otp"), {"email": self.user.email, "code": self.otp.code}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["email"], "ada@example.com")

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertTrue(self.user.is_email_verified)

    def test_verify_otp_rejects_wrong_code(self):
        response = self.client.post(
            reverse("accounts_api:verify_otp"), {"email": self.user.email, "code": "000000"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_otp_rejects_reused_code(self):
        url = reverse("accounts_api:verify_otp")
        self.client.post(url, {"email": self.user.email, "code": self.otp.code})

        response = self.client.post(url, {"email": self.user.email, "code": self.otp.code})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resend_otp_issues_a_new_code(self):
        response = self.client.post(reverse("accounts_api:resend_otp"), {"email": self.user.email})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(OTP.objects.filter(user=self.user).count(), 2)


class LoginFlowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="ada@example.com", password=VALID_PASSWORD, is_active=True, is_email_verified=True
        )

    def test_login_success(self):
        response = self.client.post(
            reverse("accounts_api:login"), {"email": "ada@example.com", "password": VALID_PASSWORD}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_wrong_password(self):
        response = self.client.post(
            reverse("accounts_api:login"), {"email": "ada@example.com", "password": "wrong"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_blocks_unverified_account_with_a_helpful_message(self):
        User.objects.create_user(email="unverified@example.com", password=VALID_PASSWORD, is_active=False)

        response = self.client.post(
            reverse("accounts_api:login"), {"email": "unverified@example.com", "password": VALID_PASSWORD}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("verify your email", str(response.data))

    def test_token_refresh_returns_a_new_access_token(self):
        login = self.client.post(
            reverse("accounts_api:login"), {"email": "ada@example.com", "password": VALID_PASSWORD}
        )
        response = self.client.post(reverse("accounts_api:token_refresh"), {"refresh": login.data["refresh"]})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)


class AuthenticatedEndpointTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="ada@example.com", password=VALID_PASSWORD, is_active=True, full_name="Ada Lovelace"
        )

    def test_me_requires_authentication(self):
        response = self.client.get(reverse("accounts_api:me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_current_user(self):
        self.client.force_authenticate(self.user)

        response = self.client.get(reverse("accounts_api:me"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "ada@example.com")
        self.assertEqual(response.data["initials"], "AL")

    def test_logout_requires_authentication(self):
        response = self.client.post(reverse("accounts_api:logout"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_returns_no_content(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(reverse("accounts_api:logout"))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class GoogleLoginTests(APITestCase):
    def setUp(self):
        self.url = reverse("accounts_api:google_login")
        self.claims = {
            "email": "ada@example.com",
            "email_verified": True,
            "name": "Ada Lovelace",
            "picture": "https://example.com/ada.jpg",
        }

    @patch("accounts.api_views.google_id_token.verify_oauth2_token")
    def test_creates_and_activates_a_new_user(self, verify_oauth2_token):
        verify_oauth2_token.return_value = self.claims

        response = self.client.post(self.url, {"id_token": "fake-token"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        user = User.objects.get(email="ada@example.com")
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_email_verified)
        self.assertEqual(user.signup_method, "google")
        self.assertFalse(user.has_usable_password())

    @patch("accounts.api_views.google_id_token.verify_oauth2_token")
    def test_activates_a_user_stuck_in_unverified_email_signup(self, verify_oauth2_token):
        verify_oauth2_token.return_value = self.claims
        User.objects.create_user(email="ada@example.com", password=VALID_PASSWORD, is_active=False)

        response = self.client.post(self.url, {"id_token": "fake-token"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user = User.objects.get(email="ada@example.com")
        self.assertTrue(user.is_active)

    @patch("accounts.api_views.google_id_token.verify_oauth2_token")
    def test_logs_in_an_existing_active_user(self, verify_oauth2_token):
        verify_oauth2_token.return_value = self.claims
        existing = User.objects.create_user(email="ada@example.com", password=VALID_PASSWORD, is_active=True)

        response = self.client.post(self.url, {"id_token": "fake-token"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(response.data["user"]["email"], existing.email)

    @patch("accounts.api_views.google_id_token.verify_oauth2_token")
    def test_rejects_an_unverified_google_email(self, verify_oauth2_token):
        verify_oauth2_token.return_value = {**self.claims, "email_verified": False}

        response = self.client.post(self.url, {"id_token": "fake-token"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.exists())

    @patch("accounts.api_views.google_id_token.verify_oauth2_token")
    def test_rejects_an_invalid_token(self, verify_oauth2_token):
        verify_oauth2_token.side_effect = GoogleAuthError("bad token")

        response = self.client.post(self.url, {"id_token": "fake-token"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
