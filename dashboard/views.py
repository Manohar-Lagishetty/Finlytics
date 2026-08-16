from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse

from expenses.forms import ExpenseForm
from expenses.models import Category

from .services import dashboard_summary


@login_required
def home(request):
    user = request.user
    summary = dashboard_summary(user, request)

    category_chart_data = [
        {"name": row["name"], "pct": row["pct"], "color_light": row["color_light"], "color_dark": row["color_dark"]}
        for row in summary["category_breakdown"]
    ]

    root_categories = list(
        Category.objects.filter(user=user, parent=None).order_by("name").values("id", "name")
    )

    context = {
        "active_nav": "dashboard",
        # Quick-add expense modal (see dashboard/home.html) - reuses the same
        # form partial as the standalone Add Expense page.
        "form": ExpenseForm(user=user),
        "root_categories": root_categories,
        "initial_path_ids": [],
        "submit_label": "Add Expense",
        "form_action": reverse("expenses:add"),
        "next_url": request.get_full_path(),
        "category_chart_data": category_chart_data,
        "has_budgets": bool(summary["budget_rows"]),
        **summary,
    }
    return render(request, "dashboard/home.html", context)
