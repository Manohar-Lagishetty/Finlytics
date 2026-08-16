from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from .models import Budget, Category, Expense, Income, RecurringIncome, SyncTombstone


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


class SyncViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="ada@example.com", password="x", is_active=True)
        self.client.force_authenticate(self.user)
        self.url = reverse("expenses_api:sync")

    def test_push_creates_a_category_and_an_expense_referencing_it_in_one_request(self):
        category_uuid = "11111111-1111-1111-1111-111111111111"
        expense_uuid = "22222222-2222-2222-2222-222222222222"

        response = self.client.post(
            self.url,
            {
                "changes": {
                    "categories": {"upserts": [{"uuid": category_uuid, "name": "Food"}]},
                    "expenses": {
                        "upserts": [
                            {"uuid": expense_uuid, "amount": "9.99", "category": category_uuid, "payment_type": "cash"}
                        ]
                    },
                }
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["errors"], {})
        self.assertTrue(Category.objects.filter(user=self.user, uuid=category_uuid).exists())
        self.assertTrue(Expense.objects.filter(user=self.user, uuid=expense_uuid).exists())

    def test_stale_push_is_ignored_last_write_wins(self):
        category = Category.objects.create(user=self.user, name="Food")
        expense = Expense.objects.create(user=self.user, category=category, amount=Decimal("10.00"), note="original")
        stale_timestamp = (expense.updated_at - timedelta(days=1)).isoformat()

        response = self.client.post(
            self.url,
            {
                "changes": {
                    "expenses": {
                        "upserts": [
                            {
                                "uuid": str(expense.uuid),
                                "amount": "10.00",
                                "category": str(category.uuid),
                                "note": "stale edit",
                                "updated_at": stale_timestamp,
                            }
                        ]
                    }
                }
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expense.refresh_from_db()
        self.assertEqual(expense.note, "original")

    def test_newer_push_overwrites_the_server_copy(self):
        category = Category.objects.create(user=self.user, name="Food")
        expense = Expense.objects.create(user=self.user, category=category, amount=Decimal("10.00"), note="original")
        future_timestamp = (expense.updated_at + timedelta(days=1)).isoformat()

        response = self.client.post(
            self.url,
            {
                "changes": {
                    "expenses": {
                        "upserts": [
                            {
                                "uuid": str(expense.uuid),
                                "amount": "10.00",
                                "category": str(category.uuid),
                                "note": "fresh edit",
                                "updated_at": future_timestamp,
                            }
                        ]
                    }
                }
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expense.refresh_from_db()
        self.assertEqual(expense.note, "fresh edit")

    def test_push_delete_removes_the_row_and_leaves_a_tombstone(self):
        category = Category.objects.create(user=self.user, name="Food")
        expense = Expense.objects.create(user=self.user, category=category, amount=Decimal("10.00"))

        response = self.client.post(
            self.url,
            {"changes": {"expenses": {"deletes": [str(expense.uuid)]}}},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Expense.objects.filter(pk=expense.pk).exists())
        self.assertTrue(SyncTombstone.objects.filter(user=self.user, model_name="expense", uuid=expense.uuid).exists())

    def test_pull_only_returns_changes_and_tombstones_since_the_given_time(self):
        category = Category.objects.create(user=self.user, name="Food")
        old_expense = Expense.objects.create(user=self.user, category=category, amount=Decimal("5.00"))
        checkpoint = timezone.now()

        new_expense = Expense.objects.create(user=self.user, category=category, amount=Decimal("7.00"))
        old_expense.delete()

        response = self.client.post(self.url, {"since": checkpoint.isoformat()}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_uuids = {row["uuid"] for row in response.data["changes"]["expenses"]}
        self.assertIn(str(new_expense.uuid), returned_uuids)

        tombstoned_uuids = {str(t["uuid"]) for t in response.data["tombstones"]}
        self.assertIn(str(old_expense.uuid), tombstoned_uuids)

    def test_sync_requires_authentication(self):
        self.client.force_authenticate(None)

        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PurgeTombstonesCommandTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="ada@example.com", password="x", is_active=True)

    def test_purges_only_tombstones_past_the_retention_window(self):
        stale = SyncTombstone.objects.create(user=self.user, model_name="expense", uuid="11111111-1111-1111-1111-111111111111")
        SyncTombstone.objects.filter(pk=stale.pk).update(
            deleted_at=timezone.now() - timedelta(days=SyncTombstone.RETENTION_DAYS + 1)
        )
        fresh = SyncTombstone.objects.create(user=self.user, model_name="expense", uuid="22222222-2222-2222-2222-222222222222")

        call_command("purge_tombstones")

        self.assertFalse(SyncTombstone.objects.filter(pk=stale.pk).exists())
        self.assertTrue(SyncTombstone.objects.filter(pk=fresh.pk).exists())
