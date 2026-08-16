import uuid as uuid_lib
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class SyncableModel(models.Model):
    """Common fields for models the Flutter app syncs to local SQLite.

    `uuid` is the client-stable identity offline-created records are
    matched on (the integer `id` stays autoincrement, used internally and
    by FKs/the web app - switching PKs to UUID would ripple through every
    FK and existing migration). `updated_at` drives last-write-wins
    conflict resolution in the sync endpoint.
    """

    uuid = models.UUIDField(default=uuid_lib.uuid4, unique=True, editable=False, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(SyncableModel):
    """A user-defined expense category. Self-referential so users can nest
    subcategories to any depth (e.g. Food -> Dining Out -> Coffee)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="categories")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="children")
    name = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["user", "parent", "name"], name="unique_category_name_per_parent"),
        ]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def clean(self):
        if self.parent_id is None:
            return
        if self.parent_id == self.id:
            raise ValidationError("A category cannot be its own parent.")
        node = self.parent
        while node is not None:
            if node.id == self.id:
                raise ValidationError("A category cannot be nested under one of its own subcategories.")
            node = node.parent


#: Toggleable columns on the expense list. "Actions" (edit/delete) is
#: always shown and isn't part of this set.
EXPENSE_COLUMNS = ["date", "category", "amount", "payment", "location", "note"]

PAYMENT_TYPE_CHOICES = [
    ("cash", "Cash"),
    ("card", "Card"),
    ("upi", "UPI"),
    ("bank_transfer", "Bank Transfer"),
    ("wallet", "Wallet"),
    ("other", "Other"),
]


class ColumnPreference(models.Model):
    """Which expense-list columns a user has chosen to hide."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="expense_column_preference")
    hidden_columns = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"ColumnPreference({self.user.email})"


class Expense(SyncableModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="expenses")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="expenses")
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    date = models.DateTimeField(default=timezone.now)
    note = models.CharField(max_length=255, blank=True)
    location = models.CharField(max_length=255, blank=True)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default="cash")
    payment_source = models.CharField(max_length=100, blank=True, help_text="e.g. bank or card name")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.amount} - {self.category.name}"

    def get_payment_type_display_short(self):
        return dict(PAYMENT_TYPE_CHOICES).get(self.payment_type, self.payment_type)


class FinanceSettings(models.Model):
    """Per-user account-level settings: the balance level below which the
    app should warn the user. Expected income is no longer a flat number
    here - see RecurringIncome, which generates real dated Income rows."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="finance_settings")
    low_balance_threshold = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))

    def __str__(self):
        return f"FinanceSettings({self.user.email})"


class RecurringIncome(SyncableModel):
    """A repeating income schedule (salary, retainer, ...) with an exact
    anchor date - e.g. "credited on the 1st of every month". Materializes
    into real Income rows lazily (see services.sync_recurring_incomes),
    since this app has no background task scheduler."""

    INTERVAL_CHOICES = [
        ("weekly", "Weekly"),
        ("biweekly", "Every 2 weeks"),
        ("monthly", "Monthly"),
        ("yearly", "Yearly"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recurring_incomes")
    label = models.CharField(max_length=100, help_text="e.g. Salary, Retainer")
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    interval = models.CharField(max_length=10, choices=INTERVAL_CHOICES, default="monthly")
    start_date = models.DateField(help_text="First credit date - later credits repeat on the same day/weekday.")
    next_due_date = models.DateField(help_text="Next occurrence still to be generated as an Income row.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["next_due_date"]

    def __str__(self):
        return f"{self.label} ({self.get_interval_display()})"


class Income(SyncableModel):
    """A credit: either ad-hoc (a bonus, gift, refund, one-off payment) or
    generated from a RecurringIncome schedule."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="incomes")
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    date = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=100, blank=True, help_text="e.g. Freelance, Gift, Refund")
    note = models.CharField(max_length=255, blank=True)
    recurring_income = models.ForeignKey(
        RecurringIncome, on_delete=models.SET_NULL, null=True, blank=True, related_name="generated_incomes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name_plural = "income"

    def __str__(self):
        return f"{self.amount} - {self.source or 'Income'}"


class Budget(SyncableModel):
    """A monthly spending cap on a category. Spend against the cap is
    computed across the category and all of its subcategories."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="budgets")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="budgets")
    monthly_cap = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category__name"]
        constraints = [
            models.UniqueConstraint(fields=["user", "category"], name="unique_budget_per_category"),
        ]

    def __str__(self):
        return f"Budget({self.category.name}: {self.monthly_cap})"


#: Keep in sync with the SyncableModel subclasses above - this is exactly
#: the set of models the mobile sync endpoint pulls/pushes.
SYNCABLE_MODEL_NAMES = ["category", "expense", "income", "recurringincome", "budget"]


class SyncTombstone(models.Model):
    """Records a delete of a SyncableModel row so the mobile app's pull
    knows what to remove locally - a hard-deleted row would otherwise just
    silently vanish from the sync feed with no signal. Populated by a
    post_delete signal (see signals.py), so it catches every delete path:
    the existing delete views, the Django admin, and cascade deletes (e.g.
    deleting a Category cascades to its Budgets).

    `db_constraint=False`: deleting a User cascades to their categories/
    expenses/etc, and the post_delete signal writes a fresh tombstone row
    for each mid-cascade - with a real FK, that insert can lose a race
    against the User row itself being deleted in the same transaction and
    fail with a FK violation. No real DB constraint sidesteps that; a
    tombstone briefly outliving its user is harmless (there's no user left
    to sync for, and the row ages out with the 90-day retention window,
    purged by the `purge_tombstones` management command)."""

    #: Any client that hasn't synced in longer than this has bigger problems
    #: than a missed delete - a fresh full pull will resync it from scratch.
    RETENTION_DAYS = 90

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sync_tombstones", db_constraint=False
    )
    model_name = models.CharField(max_length=20, choices=[(n, n) for n in SYNCABLE_MODEL_NAMES])
    uuid = models.UUIDField(db_index=True)
    deleted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-deleted_at"]
        indexes = [models.Index(fields=["user", "deleted_at"])]

    def __str__(self):
        return f"Tombstone({self.model_name}:{self.uuid})"
