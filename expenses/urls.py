from django.urls import path

from . import views

app_name = "expenses"

urlpatterns = [
    path("", views.ExpenseListView.as_view(), name="list"),
    path("add/", views.AddExpenseView.as_view(), name="add"),
    path("export/csv/", views.export_expenses_csv, name="export_csv"),
    path("export/xlsx/", views.export_expenses_xlsx, name="export_xlsx"),
    path("export/pdf/", views.export_expenses_pdf, name="export_pdf"),
    path("<int:pk>/edit/", views.EditExpenseView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.delete_expense, name="delete"),
    path("columns/", views.update_column_preference, name="update_columns"),

    path("income/", views.IncomeListView.as_view(), name="income"),
    path("income/add/", views.AddIncomeView.as_view(), name="add_income"),
    path("income/export/csv/", views.export_income_csv, name="export_income_csv"),
    path("income/export/xlsx/", views.export_income_xlsx, name="export_income_xlsx"),
    path("income/export/pdf/", views.export_income_pdf, name="export_income_pdf"),
    path("income/<int:pk>/delete/", views.delete_income, name="delete_income"),
    path("income/recurring/<int:pk>/delete/", views.delete_recurring_income, name="delete_recurring_income"),

    path("budgets/", views.BudgetsView.as_view(), name="budgets"),
    path("budgets/<int:pk>/delete/", views.delete_budget, name="delete_budget"),

    path("settings/", views.SettingsView.as_view(), name="settings"),

    path("categories/", views.CategoriesView.as_view(), name="categories"),
    path("categories/<int:pk>/delete/", views.delete_category, name="delete_category"),
    path("categories/<int:pk>/budget-status/", views.category_budget_status, name="category_budget_status"),
    path("categories/children/", views.category_children, name="category_children"),
    path("categories/create/", views.category_create, name="category_create"),
]
