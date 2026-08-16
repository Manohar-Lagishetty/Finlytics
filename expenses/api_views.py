from django.db.models import ProtectedError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .api_serializers import (
    BudgetSerializer,
    CategorySerializer,
    ColumnPreferenceSerializer,
    ExpenseSerializer,
    FinanceSettingsSerializer,
    IncomeSerializer,
    RecurringIncomeSerializer,
)
from .models import Budget, Category, ColumnPreference, Expense, FinanceSettings, Income, RecurringIncome, SyncTombstone
from .services import sync_recurring_incomes


class UserScopedModelViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_value_regex = "[0-9a-f-]{36}"

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)


class CategoryViewSet(UserScopedModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        if category.children.exists():
            return Response(
                {"detail": f"Delete “{category.name}”’s subcategories first."},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            category.delete()
        except ProtectedError:
            return Response(
                {"detail": f"“{category.name}” has expenses recorded against it and can't be deleted."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExpenseViewSet(UserScopedModelViewSet):
    queryset = Expense.objects.select_related("category").all()
    serializer_class = ExpenseSerializer


class RecurringIncomeViewSet(UserScopedModelViewSet):
    queryset = RecurringIncome.objects.all()
    serializer_class = RecurringIncomeSerializer


class IncomeViewSet(UserScopedModelViewSet):
    queryset = Income.objects.all()
    serializer_class = IncomeSerializer

    def list(self, request, *args, **kwargs):
        sync_recurring_incomes(request.user)
        return super().list(request, *args, **kwargs)


class BudgetViewSet(UserScopedModelViewSet):
    queryset = Budget.objects.select_related("category").all()
    serializer_class = BudgetSerializer


@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def finance_settings(request):
    obj, _ = FinanceSettings.objects.get_or_create(user=request.user)
    if request.method == "GET":
        return Response(FinanceSettingsSerializer(obj).data)
    serializer = FinanceSettingsSerializer(obj, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def column_preference(request):
    obj, _ = ColumnPreference.objects.get_or_create(user=request.user)
    if request.method == "GET":
        return Response(ColumnPreferenceSerializer(obj).data)
    serializer = ColumnPreferenceSerializer(obj, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


# --- Unified delta sync ------------------------------------------------
#
# One endpoint instead of 5 separate polling ones (friendlier to a phone's
# battery/network). Order matters for applying pushed changes: categories
# and recurring incomes must land before the rows that reference them
# (budgets/expenses -> categories, income -> recurring_incomes).

SYNC_GROUPS = [
    ("categories", "category", Category, CategorySerializer),
    ("recurring_incomes", "recurringincome", RecurringIncome, RecurringIncomeSerializer),
    ("budgets", "budget", Budget, BudgetSerializer),
    ("expenses", "expense", Expense, ExpenseSerializer),
    ("income", "income", Income, IncomeSerializer),
]


class SyncView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        since_raw = request.data.get("since")
        since = parse_datetime(since_raw) if since_raw else None

        server_time = timezone.now()
        errors = {}

        incoming = request.data.get("changes", {})
        for key, model_name, model, serializer_class in SYNC_GROUPS:
            group = incoming.get(key) or {}

            for row in group.get("upserts", []):
                row_uuid = row.get("uuid")
                instance = model.objects.filter(user=user, uuid=row_uuid).first() if row_uuid else None

                if instance is not None:
                    client_updated_at = parse_datetime(row.get("updated_at", "")) if row.get("updated_at") else None
                    if client_updated_at and client_updated_at <= instance.updated_at:
                        continue  # server copy is newer or equal - last-write-wins, skip

                serializer = serializer_class(instance=instance, data=row, partial=True, context={"request": request})
                if serializer.is_valid():
                    serializer.save()
                else:
                    errors.setdefault(key, []).append({"uuid": row_uuid, "errors": serializer.errors})

            for row_uuid in group.get("deletes", []):
                model.objects.filter(user=user, uuid=row_uuid).delete()

        # Recurring incomes pushed above may have introduced/changed due
        # occurrences - materialize before building the pull response.
        sync_recurring_incomes(user)

        changes = {}
        for key, model_name, model, serializer_class in SYNC_GROUPS:
            qs = model.objects.filter(user=user)
            if since:
                qs = qs.filter(updated_at__gt=since)
            changes[key] = serializer_class(qs, many=True, context={"request": request}).data

        tombstones = []
        if since:
            tombstones = list(
                SyncTombstone.objects.filter(user=user, deleted_at__gt=since).values("model_name", "uuid", "deleted_at")
            )

        return Response(
            {
                "server_time": server_time.isoformat(),
                "changes": changes,
                "tombstones": tombstones,
                "errors": errors,
            }
        )
