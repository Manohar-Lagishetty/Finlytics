from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from expenses.models import Budget, Category, Expense, Income, RecurringIncome, SyncTombstone


class CategoryAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="ada@example.com", password="x", is_active=True)
        self.client.force_authenticate(self.user)

    def test_create_category(self):
        response = self.client.post(reverse("expenses_api:category-list"), {"name": "Food"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Category.objects.get().user, self.user)

    def test_duplicate_name_at_same_level_is_rejected(self):
        Category.objects.create(user=self.user, name="Food")

        response = self.client.post(reverse("expenses_api:category-list"), {"name": "Food"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_leaf_category(self):
        category = Category.objects.create(user=self.user, name="Food")

        response = self.client.delete(reverse("expenses_api:category-detail", kwargs={"uuid": category.uuid}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Category.objects.exists())

    def test_delete_category_with_children_is_blocked(self):
        parent = Category.objects.create(user=self.user, name="Food")
        Category.objects.create(user=self.user, name="Dining Out", parent=parent)

        response = self.client.delete(reverse("expenses_api:category-detail", kwargs={"uuid": parent.uuid}))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(Category.objects.filter(pk=parent.pk).exists())

    def test_delete_category_with_expenses_is_blocked(self):
        category = Category.objects.create(user=self.user, name="Food")
        Expense.objects.create(user=self.user, category=category, amount=Decimal("10.00"))

        response = self.client.delete(reverse("expenses_api:category-detail", kwargs={"uuid": category.uuid}))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_categories_are_scoped_to_the_requesting_user(self):
        other = User.objects.create_user(email="bob@example.com", password="x", is_active=True)
        Category.objects.create(user=other, name="Food")

        response = self.client.get(reverse("expenses_api:category-list"))
        self.assertEqual(response.data, [])


class ExpenseAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="ada@example.com", password="x", is_active=True)
        self.client.force_authenticate(self.user)
        self.category = Category.objects.create(user=self.user, name="Food")

    def test_create_expense(self):
        response = self.client.post(
            reverse("expenses_api:expense-list"),
            {"amount": "12.50", "category": str(self.category.uuid), "payment_type": "cash"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Expense.objects.get().amount, Decimal("12.50"))

    def test_cannot_use_another_users_category(self):
        other = User.objects.create_user(email="bob@example.com", password="x", is_active=True)
        other_category = Category.objects.create(user=other, name="Food")

        response = self.client.post(
            reverse("expenses_api:expense-list"),
            {"amount": "12.50", "category": str(other_category.uuid)},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_expenses_are_scoped_to_the_requesting_user(self):
        other = User.objects.create_user(email="bob@example.com", password="x", is_active=True)
        other_category = Category.objects.create(user=other, name="Food")
        Expense.objects.create(user=other, category=other_category, amount=Decimal("5.00"))

        response = self.client.get(reverse("expenses_api:expense-list"))
        self.assertEqual(response.data, [])

    def test_deleting_an_expense_records_a_tombstone(self):
        expense = Expense.objects.create(user=self.user, category=self.category, amount=Decimal("5.00"))

        self.client.delete(reverse("expenses_api:expense-detail", kwargs={"uuid": expense.uuid}))

        self.assertTrue(
            SyncTombstone.objects.filter(user=self.user, model_name="expense", uuid=expense.uuid).exists()
        )


class BudgetAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="ada@example.com", password="x", is_active=True)
        self.client.force_authenticate(self.user)
        self.category = Category.objects.create(user=self.user, name="Food")

    def test_second_budget_on_same_category_is_rejected(self):
        Budget.objects.create(user=self.user, category=self.category, monthly_cap=Decimal("500"))

        response = self.client.post(
            reverse("expenses_api:budget-list"),
            {"category": str(self.category.uuid), "monthly_cap": "300"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class IncomeAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="ada@example.com", password="x", is_active=True)
        self.client.force_authenticate(self.user)

    def test_listing_income_materializes_due_recurring_income(self):
        RecurringIncome.objects.create(
            user=self.user,
            label="Salary",
            amount=Decimal("1000"),
            interval="monthly",
            start_date=timezone.localdate() - timedelta(days=1),
            next_due_date=timezone.localdate() - timedelta(days=1),
        )
        self.assertFalse(Income.objects.exists())

        response = self.client.get(reverse("expenses_api:income-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Income.objects.filter(user=self.user, source="Salary").exists())
