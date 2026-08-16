from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from expenses.models import Category, Expense, SyncTombstone


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
