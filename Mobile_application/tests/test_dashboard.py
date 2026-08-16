from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from expenses.models import Category, Expense


class DashboardSummaryAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="ada@example.com", password="x", is_active=True)
        self.client.force_authenticate(self.user)
        self.url = reverse("dashboard_api:summary")

    def test_requires_authentication(self):
        self.client.force_authenticate(None)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_empty_state_reports_no_expenses(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["has_any_expenses"])
        self.assertEqual(response.data["total_amount"], "0")
        self.assertEqual(response.data["category_breakdown"], [])

    def test_totals_reflect_this_months_expenses(self):
        category = Category.objects.create(user=self.user, name="Food")
        Expense.objects.create(user=self.user, category=category, amount=Decimal("10.00"), date=timezone.now())
        Expense.objects.create(user=self.user, category=category, amount=Decimal("15.00"), date=timezone.now())

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["has_any_expenses"])
        self.assertEqual(response.data["total_amount"], "25.00")
        self.assertEqual(response.data["count"], 2)

    def test_only_the_requesting_users_expenses_are_counted(self):
        other = User.objects.create_user(email="bob@example.com", password="x", is_active=True)
        other_category = Category.objects.create(user=other, name="Food")
        Expense.objects.create(user=other, category=other_category, amount=Decimal("999.00"), date=timezone.now())

        response = self.client.get(self.url)

        self.assertEqual(response.data["total_amount"], "0")
