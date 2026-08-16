"""Combined routing for the mobile API - included once, at /api/v1/, by
Expense_Tracker/urls.py. Namespaces (accounts_api/expenses_api/dashboard_api)
and paths are unchanged from before this app existed, so nothing on the
client side needs to know this moved."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import accounts as accounts_views
from .views import dashboard as dashboard_views
from .views import expenses as expenses_views

accounts_patterns = (
    [
        path("signup/", accounts_views.signup, name="signup"),
        path("verify-otp/", accounts_views.verify_otp, name="verify_otp"),
        path("resend-otp/", accounts_views.resend_otp, name="resend_otp"),
        path("login/", accounts_views.login, name="login"),
        path("google/", accounts_views.google_login, name="google_login"),
        path("logout/", accounts_views.logout, name="logout"),
        path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
        path("me/", accounts_views.me, name="me"),
    ],
    "accounts_api",
)

expenses_router = DefaultRouter()
expenses_router.register("categories", expenses_views.CategoryViewSet, basename="category")
expenses_router.register("expenses", expenses_views.ExpenseViewSet, basename="expense")
expenses_router.register("income", expenses_views.IncomeViewSet, basename="income")
expenses_router.register("recurring-incomes", expenses_views.RecurringIncomeViewSet, basename="recurringincome")
expenses_router.register("budgets", expenses_views.BudgetViewSet, basename="budget")

expenses_patterns = (
    [
        path("settings/", expenses_views.finance_settings, name="finance_settings"),
        path("columns/", expenses_views.column_preference, name="column_preference"),
        path("sync/", expenses_views.SyncView.as_view(), name="sync"),
        path("", include(expenses_router.urls)),
    ],
    "expenses_api",
)

dashboard_patterns = (
    [
        path("summary/", dashboard_views.summary, name="summary"),
    ],
    "dashboard_api",
)

urlpatterns = [
    path("auth/", include(accounts_patterns)),
    path("dashboard/", include(dashboard_patterns)),
    path("", include(expenses_patterns)),
]
