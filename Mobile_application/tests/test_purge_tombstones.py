from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from expenses.models import SyncTombstone


class PurgeTombstonesCommandTests(TestCase):
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
