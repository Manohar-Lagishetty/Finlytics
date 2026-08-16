from django.contrib import admin

from .models import Budget, Category, ColumnPreference, Expense, FinanceSettings, Income, RecurringIncome


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "parent", "created_at")
    list_filter = ("user",)
    search_fields = ("name",)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("user", "category", "amount", "date", "payment_type", "location", "created_at")
    list_filter = ("user", "date", "payment_type")
    search_fields = ("note", "location")


@admin.register(ColumnPreference)
class ColumnPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "hidden_columns")


@admin.register(FinanceSettings)
class FinanceSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "low_balance_threshold")


@admin.register(RecurringIncome)
class RecurringIncomeAdmin(admin.ModelAdmin):
    list_display = ("user", "label", "amount", "interval", "start_date", "next_due_date")
    list_filter = ("user", "interval")
    search_fields = ("label",)


@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "source", "date", "recurring_income", "created_at")
    list_filter = ("user", "date")
    search_fields = ("source", "note")


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ("user", "category", "monthly_cap")
    list_filter = ("user",)
