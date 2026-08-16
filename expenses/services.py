"""Small cross-view business-logic helpers shared between the expenses app
(Budgets page, inline budget warning, Income page) and the dashboard
(Balance banner, Budgets progress card) - kept out of views.py so neither
app has to import the other's views module."""

from datetime import datetime, time as dtime
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from .models import Budget, Expense, FinanceSettings, Income, RecurringIncome
from .utils import add_interval, descendant_ids


def budget_progress_rows(user):
    """This calendar month's spend vs cap for every budget the user has
    set, sorted by how close to (or past) the cap each one is."""
    budgets = list(Budget.objects.filter(user=user).select_related("category"))
    today = timezone.localdate()
    month_start = today.replace(day=1)

    rows = []
    for budget in budgets:
        category_ids = [budget.category_id, *descendant_ids(budget.category)]
        spent = (
            Expense.objects.filter(
                user=user, category_id__in=category_ids, date__date__gte=month_start, date__date__lte=today
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )
        pct = round(float(spent / budget.monthly_cap * 100), 1) if budget.monthly_cap else 0
        status = "over" if pct >= 100 else "near" if pct >= 80 else "ok"
        rows.append({"budget": budget, "spent": spent, "bar_pct": min(pct, 100), "pct": pct, "status": status})

    return sorted(rows, key=lambda row: row["pct"], reverse=True)


def sync_recurring_incomes(user):
    """Materialize any due RecurringIncome occurrences into real, dated
    Income rows. There's no background scheduler in this app, so this runs
    lazily whenever the user views a screen that depends on income data -
    it catches up on every missed occurrence since the last visit, not
    just the most recent one."""
    today = timezone.localdate()
    due = RecurringIncome.objects.filter(user=user, next_due_date__lte=today)

    for recurring in due:
        occurrence = recurring.next_due_date
        while occurrence <= today:
            occurrence_dt = timezone.make_aware(datetime.combine(occurrence, dtime(9, 0)))
            Income.objects.create(
                user=user,
                amount=recurring.amount,
                date=occurrence_dt,
                source=recurring.label,
                recurring_income=recurring,
            )
            occurrence = add_interval(occurrence, recurring.interval)
        recurring.next_due_date = occurrence
        recurring.save(update_fields=["next_due_date"])


def monthly_balance(user):
    """This calendar month's balance: income (recurring + ad-hoc) minus
    expenses, scoped to the current month only (resets each month). Syncs
    due recurring income first so the figures are always current."""
    sync_recurring_incomes(user)

    today = timezone.localdate()
    month_start = today.replace(day=1)

    finance_settings = FinanceSettings.objects.filter(user=user).first()
    low_balance_threshold = finance_settings.low_balance_threshold if finance_settings else Decimal("0")

    month_incomes = Income.objects.filter(user=user, date__date__gte=month_start, date__date__lte=today)
    recurring_total = (
        month_incomes.filter(recurring_income__isnull=False).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    )
    adhoc_total = (
        month_incomes.filter(recurring_income__isnull=True).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    )
    income_total = recurring_total + adhoc_total
    expenses_total = (
        Expense.objects.filter(user=user, date__date__gte=month_start, date__date__lte=today).aggregate(
            total=Sum("amount")
        )["total"]
        or Decimal("0")
    )
    balance = income_total - expenses_total

    return {
        "is_configured": finance_settings is not None,
        "recurring_total": recurring_total,
        "adhoc_total": adhoc_total,
        "income_total": income_total,
        "expenses_total": expenses_total,
        "balance": balance,
        "low_balance_threshold": low_balance_threshold,
        "is_low": finance_settings is not None and balance < low_balance_threshold,
    }
