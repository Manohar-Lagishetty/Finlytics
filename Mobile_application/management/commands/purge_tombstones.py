from django.core.management.base import BaseCommand
from django.utils import timezone

from expenses.models import SyncTombstone


class Command(BaseCommand):
    help = (
        "Delete sync tombstones older than SyncTombstone.RETENTION_DAYS. "
        "Meant to run on a daily schedule (cron/systemd timer)."
    )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timezone.timedelta(days=SyncTombstone.RETENTION_DAYS)
        deleted, _ = SyncTombstone.objects.filter(deleted_at__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f"Purged {deleted} tombstone(s) older than {cutoff.isoformat()}."))
