from rest_framework import serializers

from .models import (
    EXPENSE_COLUMNS,
    Budget,
    Category,
    ColumnPreference,
    Expense,
    FinanceSettings,
    Income,
    RecurringIncome,
)


class UserScopedUUIDField(serializers.SlugRelatedField):
    """Relates by `uuid` (not the internal integer id) and scopes the
    lookup queryset to the requesting user. Mobile clients work entirely in
    uuid-space - they never see/generate internal ids, which matters for
    records created offline before the server has assigned one."""

    def __init__(self, model, **kwargs):
        self._related_model = model
        kwargs.setdefault("slug_field", "uuid")
        super().__init__(queryset=model.objects.none(), **kwargs)

    def get_queryset(self):
        request = self.context.get("request")
        qs = self._related_model.objects.all()
        if request is not None:
            qs = qs.filter(user=request.user)
        return qs


class SyncableSerializer(serializers.ModelSerializer):
    """Base for the 5 models that sync to the phone. `uuid` is writable on
    create (the client may already have generated one offline) but never
    changes on update."""

    uuid = serializers.UUIDField(required=False)

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("uuid", None)
        return super().update(instance, validated_data)


class CategorySerializer(SyncableSerializer):
    parent = UserScopedUUIDField(Category, required=False, allow_null=True)

    class Meta:
        model = Category
        fields = ["uuid", "name", "parent", "created_at", "updated_at"]

    def validate(self, attrs):
        name = attrs.get("name", getattr(self.instance, "name", None))
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        request = self.context["request"]
        qs = Category.objects.filter(user=request.user, parent=parent, name__iexact=name)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError({"name": "You already have a category with this name at this level."})
        return attrs


class ExpenseSerializer(SyncableSerializer):
    category = UserScopedUUIDField(Category)

    class Meta:
        model = Expense
        fields = [
            "uuid", "amount", "category", "date", "note", "location",
            "payment_type", "payment_source", "created_at", "updated_at",
        ]


class RecurringIncomeSerializer(SyncableSerializer):
    class Meta:
        model = RecurringIncome
        fields = ["uuid", "label", "amount", "interval", "start_date", "next_due_date", "created_at", "updated_at"]
        extra_kwargs = {"next_due_date": {"required": False}}

    def create(self, validated_data):
        validated_data.setdefault("next_due_date", validated_data["start_date"])
        return super().create(validated_data)


class IncomeSerializer(SyncableSerializer):
    recurring_income = UserScopedUUIDField(RecurringIncome, required=False, allow_null=True)

    class Meta:
        model = Income
        fields = ["uuid", "amount", "date", "source", "note", "recurring_income", "created_at", "updated_at"]


class BudgetSerializer(SyncableSerializer):
    category = UserScopedUUIDField(Category)

    class Meta:
        model = Budget
        fields = ["uuid", "category", "monthly_cap", "created_at", "updated_at"]

    def validate_category(self, category):
        request = self.context["request"]
        qs = Budget.objects.filter(user=request.user, category=category)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This category already has a budget. Edit it instead of creating a new one.")
        return category


class FinanceSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinanceSettings
        fields = ["low_balance_threshold"]


class ColumnPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ColumnPreference
        fields = ["hidden_columns"]

    def validate_hidden_columns(self, hidden):
        return [c for c in hidden if c in EXPENSE_COLUMNS]
