from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Budget, Category, Expense, Income, RecurringIncome, SyncTombstone

SYNCABLE_MODELS = {
    Category: "category",
    Expense: "expense",
    Income: "income",
    RecurringIncome: "recurringincome",
    Budget: "budget",
}


def _record_tombstone(sender, instance, **kwargs):
    SyncTombstone.objects.create(
        user_id=instance.user_id,
        model_name=SYNCABLE_MODELS[sender],
        uuid=instance.uuid,
    )


def connect():
    for model in SYNCABLE_MODELS:
        post_delete.connect(_record_tombstone, sender=model, dispatch_uid=f"sync_tombstone_{model.__name__}")
