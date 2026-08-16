from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api_views

app_name = "expenses_api"

router = DefaultRouter()
router.register("categories", api_views.CategoryViewSet, basename="category")
router.register("expenses", api_views.ExpenseViewSet, basename="expense")
router.register("income", api_views.IncomeViewSet, basename="income")
router.register("recurring-incomes", api_views.RecurringIncomeViewSet, basename="recurringincome")
router.register("budgets", api_views.BudgetViewSet, basename="budget")

urlpatterns = [
    path("settings/", api_views.finance_settings, name="finance_settings"),
    path("columns/", api_views.column_preference, name="column_preference"),
    path("sync/", api_views.SyncView.as_view(), name="sync"),
    path("", include(router.urls)),
]
