from collections import defaultdict
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import ProtectedError, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_GET, require_POST

from .exports import csv_response, pdf_summary_response, xlsx_response
from .services import budget_progress_rows, sync_recurring_incomes
from .forms import (
    BudgetForm,
    CategoryForm,
    ExpenseFilterForm,
    ExpenseForm,
    FinanceSettingsForm,
    IncomeFilterForm,
    IncomeForm,
    RecurringIncomeForm,
)
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
from .utils import (
    build_category_tree,
    category_path_ids,
    descendant_ids,
    group_amounts_by_root,
    nearest_budgeted_category_id,
)

ALLOWED_SORTS = {"date", "-date", "amount", "-amount"}


def _date_range_subtitle(date_from, date_to):
    if date_from and date_to:
        return f"{date_from:%b %d, %Y} – {date_to:%b %d, %Y}"
    if date_from:
        return f"From {date_from:%b %d, %Y}"
    if date_to:
        return f"Through {date_to:%b %d, %Y}"
    return "All time"


def _expense_form_context(request, form):
    """Context shared by Add/Edit: root categories for the picker's first
    level, plus the ancestor-id path of whatever category is currently
    selected (from POSTed data on a validation error, or from the instance
    being edited) so the cascading picker can pre-populate every level."""
    root_categories = list(
        Category.objects.filter(user=request.user, parent=None).order_by("name").values("id", "name")
    )
    category = None
    if form.is_bound:
        raw_id = form.data.get("category")
        if raw_id:
            category = Category.objects.filter(user=request.user, pk=raw_id).first()
    elif getattr(form.instance, "pk", None) and form.instance.category_id:
        category = form.instance.category
    return {
        "root_categories": root_categories,
        "initial_path_ids": category_path_ids(category) if category else [],
    }


class AddExpenseView(LoginRequiredMixin, View):
    template_name = "expenses/add.html"

    def get(self, request):
        return self._render(request, ExpenseForm(user=request.user))

    def post(self, request):
        form = ExpenseForm(request.POST, user=request.user)
        if not form.is_valid():
            return self._render(request, form)

        expense = form.save(commit=False)
        expense.user = request.user
        expense.save()
        messages.success(request, f"Added {expense.amount} to {expense.category.name}.")
        next_url = request.POST.get("next")
        return redirect(next_url if next_url and next_url.startswith("/") else "expenses:list")

    def _render(self, request, form):
        context = {
            "active_nav": "expenses",
            "form": form,
            "page_title": "Add Expense",
            "page_subtitle": "Log a new expense against one of your categories.",
            "submit_label": "Add Expense",
            "cancel_url": reverse("expenses:list"),
        }
        context.update(_expense_form_context(request, form))
        return render(request, self.template_name, context)


class EditExpenseView(LoginRequiredMixin, View):
    template_name = "expenses/edit.html"

    def get(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk, user=request.user)
        return self._render(request, ExpenseForm(instance=expense, user=request.user))

    def post(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk, user=request.user)
        form = ExpenseForm(request.POST, instance=expense, user=request.user)
        if not form.is_valid():
            return self._render(request, form)

        form.save()
        messages.success(request, f"Updated expense of {form.instance.amount}.")
        return redirect("expenses:list")

    def _render(self, request, form):
        context = {
            "active_nav": "expenses",
            "form": form,
            "page_title": "Edit Expense",
            "page_subtitle": "Update the details of this expense.",
            "submit_label": "Save Changes",
            "cancel_url": reverse("expenses:list"),
        }
        context.update(_expense_form_context(request, form))
        return render(request, self.template_name, context)


@login_required
@require_POST
def delete_expense(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    amount, category_name = expense.amount, expense.category.name
    expense.delete()
    messages.success(request, f"Deleted {amount} expense in {category_name}.")
    next_url = request.POST.get("next")
    return redirect(next_url if next_url and next_url.startswith("/") else "expenses:list")


def _filtered_expenses(request):
    filter_form = ExpenseFilterForm(request.GET or None, user=request.user)
    qs = Expense.objects.filter(user=request.user).select_related("category")

    if filter_form.is_valid():
        data = filter_form.cleaned_data
        if data.get("date_from"):
            qs = qs.filter(date__date__gte=data["date_from"])
        if data.get("date_to"):
            qs = qs.filter(date__date__lte=data["date_to"])
        if data.get("category"):
            category = data["category"]
            qs = qs.filter(category_id__in=[category.id, *descendant_ids(category)])
        if data.get("amount_min") is not None:
            qs = qs.filter(amount__gte=data["amount_min"])
        if data.get("amount_max") is not None:
            qs = qs.filter(amount__lte=data["amount_max"])
        if data.get("q"):
            qs = qs.filter(note__icontains=data["q"])

    return qs, filter_form


class ExpenseListView(LoginRequiredMixin, View):
    template_name = "expenses/list.html"
    page_size = 25

    def get(self, request):
        qs, filter_form = _filtered_expenses(request)

        sort = request.GET.get("sort", "-date")
        if sort not in ALLOWED_SORTS:
            sort = "-date"
        qs = qs.order_by(sort, "-created_at")

        total_amount = qs.aggregate(total=Sum("amount"))["total"] or 0
        paginator = Paginator(qs, self.page_size)
        page_obj = paginator.get_page(request.GET.get("page"))

        prefs, _ = ColumnPreference.objects.get_or_create(user=request.user)
        filter_fields = ["date_from", "date_to", "category", "amount_min", "amount_max", "q"]

        return render(
            request,
            self.template_name,
            {
                "active_nav": "expenses",
                "filter_form": filter_form,
                "page_obj": page_obj,
                "total_amount": total_amount,
                "total_count": paginator.count,
                "current_sort": sort,
                "date_sort": "date" if sort == "-date" else "-date",
                "amount_sort": "amount" if sort == "-amount" else "-amount",
                "hidden_columns": prefs.hidden_columns,
                "columns": EXPENSE_COLUMNS,
                "has_filters": any(request.GET.get(f) for f in filter_fields),
            },
        )


EXPENSE_EXPORT_HEADERS = ["Date", "Category", "Amount", "Payment Type", "Payment Source", "Location", "Note"]


def _expense_export_rows(qs):
    return [
        [
            timezone.localtime(expense.date).strftime("%Y-%m-%d %H:%M"),
            expense.category.name,
            str(expense.amount),
            expense.get_payment_type_display(),
            expense.payment_source,
            expense.location,
            expense.note,
        ]
        for expense in qs.order_by("-date")
    ]


@login_required
@require_GET
def export_expenses_csv(request):
    qs, _ = _filtered_expenses(request)
    return csv_response("expenses.csv", EXPENSE_EXPORT_HEADERS, _expense_export_rows(qs))


@login_required
@require_GET
def export_expenses_xlsx(request):
    qs, _ = _filtered_expenses(request)
    return xlsx_response("expenses.xlsx", EXPENSE_EXPORT_HEADERS, _expense_export_rows(qs), sheet_title="Expenses")


@login_required
@require_GET
def export_expenses_pdf(request):
    qs, filter_form = _filtered_expenses(request)
    total = qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    count = qs.count()

    categories_by_id = {c.id: c for c in Category.objects.filter(user=request.user)}
    totals_by_root = group_amounts_by_root(qs.values_list("category_id", "amount"), categories_by_id)
    breakdown_pairs = sorted(
        (
            (categories_by_id[cid].name if cid in categories_by_id else "Uncategorized", amount)
            for cid, amount in totals_by_root.items()
        ),
        key=lambda pair: pair[1],
        reverse=True,
    )
    breakdown_rows = [
        [name, f"{amount:.2f}", f"{(amount / total * 100):.1f}%" if total else "0.0%"]
        for name, amount in breakdown_pairs
    ]

    date_from = filter_form.cleaned_data.get("date_from") if filter_form.is_valid() else None
    date_to = filter_form.cleaned_data.get("date_to") if filter_form.is_valid() else None

    return pdf_summary_response(
        "expenses-summary.pdf",
        title="Expense Summary",
        subtitle=_date_range_subtitle(date_from, date_to),
        total_label="Total spent",
        total_amount=total,
        count=count,
        breakdown_title="By category",
        breakdown_rows=breakdown_rows,
    )


@login_required
@require_POST
def update_column_preference(request):
    hidden = [c for c in request.POST.getlist("hidden") if c in EXPENSE_COLUMNS]
    prefs, _ = ColumnPreference.objects.update_or_create(user=request.user, defaults={"hidden_columns": hidden})
    return JsonResponse({"hidden_columns": prefs.hidden_columns})


# --- Income (ad-hoc credits) -------------------------------------------------


class AddIncomeView(LoginRequiredMixin, View):
    template_name = "expenses/income_add.html"

    def get(self, request):
        return render(request, self.template_name, {"active_nav": "income", "form": IncomeForm(user=request.user)})

    def post(self, request):
        form = IncomeForm(request.POST, user=request.user)
        if not form.is_valid():
            return render(request, self.template_name, {"active_nav": "income", "form": form})
        income = form.save()
        suffix = f" from {income.source}" if income.source else ""
        messages.success(request, f"Added {income.amount} credit{suffix}.")
        return redirect("expenses:income")


def _filtered_income(request):
    filter_form = IncomeFilterForm(request.GET or None)
    qs = Income.objects.filter(user=request.user)

    if filter_form.is_valid():
        data = filter_form.cleaned_data
        if data.get("date_from"):
            qs = qs.filter(date__date__gte=data["date_from"])
        if data.get("date_to"):
            qs = qs.filter(date__date__lte=data["date_to"])
        if data.get("q"):
            qs = qs.filter(Q(source__icontains=data["q"]) | Q(note__icontains=data["q"]))

    return qs, filter_form


class IncomeListView(LoginRequiredMixin, View):
    """Also owns the Recurring Income add-form on the same page (list +
    add, same pattern as Budgets/Categories) - the ad-hoc "Add Credit" form
    lives on its own page (AddIncomeView) so there's no POST conflict."""

    template_name = "expenses/income_list.html"
    page_size = 25

    def get(self, request):
        sync_recurring_incomes(request.user)
        return self._render(request, RecurringIncomeForm(user=request.user))

    def post(self, request):
        form = RecurringIncomeForm(request.POST, user=request.user)
        if not form.is_valid():
            return self._render(request, form)
        recurring = form.save()
        sync_recurring_incomes(request.user)
        messages.success(request, f"Recurring income “{recurring.label}” added.")
        return redirect("expenses:income")

    def _render(self, request, recurring_form):
        qs, filter_form = _filtered_income(request)
        qs = qs.order_by("-date", "-created_at")

        total_amount = qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        paginator = Paginator(qs, self.page_size)
        page_obj = paginator.get_page(request.GET.get("page"))
        filter_fields = ["date_from", "date_to", "q"]

        return render(
            request,
            self.template_name,
            {
                "active_nav": "income",
                "filter_form": filter_form,
                "recurring_form": recurring_form,
                "recurring_incomes": RecurringIncome.objects.filter(user=request.user),
                "page_obj": page_obj,
                "total_amount": total_amount,
                "total_count": paginator.count,
                "has_filters": any(request.GET.get(f) for f in filter_fields),
            },
        )


@login_required
@require_POST
def delete_recurring_income(request, pk):
    recurring = get_object_or_404(RecurringIncome, pk=pk, user=request.user)
    label = recurring.label
    recurring.delete()
    messages.success(request, f"Stopped “{label}”. Past credits it already generated are kept.")
    return redirect("expenses:income")


@login_required
@require_POST
def delete_income(request, pk):
    income = get_object_or_404(Income, pk=pk, user=request.user)
    amount = income.amount
    income.delete()
    messages.success(request, f"Deleted {amount} credit.")
    next_url = request.POST.get("next")
    return redirect(next_url if next_url and next_url.startswith("/") else "expenses:income")


INCOME_EXPORT_HEADERS = ["Date", "Amount", "Source", "Note"]


def _income_export_rows(qs):
    return [
        [timezone.localtime(income.date).strftime("%Y-%m-%d %H:%M"), str(income.amount), income.source, income.note]
        for income in qs.order_by("-date")
    ]


@login_required
@require_GET
def export_income_csv(request):
    qs, _ = _filtered_income(request)
    return csv_response("income.csv", INCOME_EXPORT_HEADERS, _income_export_rows(qs))


@login_required
@require_GET
def export_income_xlsx(request):
    qs, _ = _filtered_income(request)
    return xlsx_response("income.xlsx", INCOME_EXPORT_HEADERS, _income_export_rows(qs), sheet_title="Income")


@login_required
@require_GET
def export_income_pdf(request):
    qs, filter_form = _filtered_income(request)
    total = qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    count = qs.count()

    totals_by_source = defaultdict(lambda: Decimal("0"))
    for source, amount in qs.values_list("source", "amount"):
        totals_by_source[source or "Other"] += amount
    breakdown_pairs = sorted(totals_by_source.items(), key=lambda pair: pair[1], reverse=True)
    breakdown_rows = [
        [name, f"{amount:.2f}", f"{(amount / total * 100):.1f}%" if total else "0.0%"]
        for name, amount in breakdown_pairs
    ]

    date_from = filter_form.cleaned_data.get("date_from") if filter_form.is_valid() else None
    date_to = filter_form.cleaned_data.get("date_to") if filter_form.is_valid() else None

    return pdf_summary_response(
        "income-summary.pdf",
        title="Income Summary",
        subtitle=_date_range_subtitle(date_from, date_to),
        total_label="Total received",
        total_amount=total,
        count=count,
        breakdown_title="By source",
        breakdown_rows=breakdown_rows,
        breakdown_columns=("Source", "Amount", "% of total"),
    )


# --- Budgets ------------------------------------------------------------


class BudgetsView(LoginRequiredMixin, View):
    template_name = "expenses/budgets.html"

    def get(self, request):
        return self._render(request, BudgetForm(user=request.user))

    def post(self, request):
        form = BudgetForm(request.POST, user=request.user)
        if not form.is_valid():
            return self._render(request, form)
        form.save()
        messages.success(request, f"Budget set for “{form.instance.category.name}”.")
        return redirect("expenses:budgets")

    def _render(self, request, form):
        rows = budget_progress_rows(request.user)
        return render(
            request,
            self.template_name,
            {"active_nav": "budgets", "form": form, "rows": rows, "has_budgets": bool(rows)},
        )


@login_required
@require_POST
def delete_budget(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    name = budget.category.name
    budget.delete()
    messages.success(request, f"Removed the budget for “{name}”.")
    return redirect("expenses:budgets")


@login_required
@require_GET
def category_budget_status(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    budgeted_ids = set(Budget.objects.filter(user=request.user).values_list("category_id", flat=True))
    target_id = nearest_budgeted_category_id(category, budgeted_ids)
    if target_id is None:
        return JsonResponse({"has_budget": False})

    budget = Budget.objects.select_related("category").get(user=request.user, category_id=target_id)
    today = timezone.localdate()
    month_start = today.replace(day=1)
    ids = [target_id, *descendant_ids(budget.category)]
    spent = (
        Expense.objects.filter(
            user=request.user, category_id__in=ids, date__date__gte=month_start, date__date__lte=today
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )

    return JsonResponse(
        {
            "has_budget": True,
            "category_name": budget.category.name,
            "cap": str(budget.monthly_cap),
            "spent": str(spent),
        }
    )


# --- Finance settings -----------------------------------------------------


class SettingsView(LoginRequiredMixin, View):
    template_name = "expenses/settings.html"

    def get(self, request):
        finance_settings, _ = FinanceSettings.objects.get_or_create(user=request.user)
        form = FinanceSettingsForm(instance=finance_settings)
        return render(request, self.template_name, {"active_nav": "settings", "form": form})

    def post(self, request):
        finance_settings, _ = FinanceSettings.objects.get_or_create(user=request.user)
        form = FinanceSettingsForm(request.POST, instance=finance_settings)
        if not form.is_valid():
            return render(request, self.template_name, {"active_nav": "settings", "form": form})
        form.save()
        messages.success(request, "Settings saved.")
        return redirect("expenses:settings")


# --- Categories -------------------------------------------------------------


class CategoriesView(LoginRequiredMixin, View):
    template_name = "expenses/categories.html"

    def get(self, request):
        return self._render(request, CategoryForm(user=request.user))

    def post(self, request):
        form = CategoryForm(request.POST, user=request.user)
        if not form.is_valid():
            return self._render(request, form)
        form.save()
        messages.success(request, f"Category “{form.instance.name}” created.")
        return redirect("expenses:categories")

    def _render(self, request, form):
        categories = list(Category.objects.filter(user=request.user))
        tree = build_category_tree(categories)
        return render(
            request,
            self.template_name,
            {"active_nav": "categories", "form": form, "tree": tree, "has_categories": bool(categories)},
        )


@login_required
@require_POST
def delete_category(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    if category.children.exists():
        messages.error(request, f"Delete “{category.name}”’s subcategories first.")
    else:
        try:
            category.delete()
            messages.success(request, f"Deleted “{category.name}”.")
        except ProtectedError:
            messages.error(request, f"“{category.name}” has expenses recorded against it and can't be deleted.")
    return redirect("expenses:categories")


@login_required
@require_GET
def category_children(request):
    parent_id = request.GET.get("parent_id") or None
    children = list(
        Category.objects.filter(user=request.user, parent_id=parent_id)
        .order_by("name")
        .values("id", "name")
    )
    return JsonResponse({"children": children})


@login_required
@require_POST
def category_create(request):
    name = (request.POST.get("name") or "").strip()
    parent_id = request.POST.get("parent_id") or None

    if not name:
        return JsonResponse({"error": "Enter a category name."}, status=400)

    parent = None
    if parent_id:
        parent = get_object_or_404(Category, pk=parent_id, user=request.user)

    if Category.objects.filter(user=request.user, parent=parent, name__iexact=name).exists():
        return JsonResponse({"error": "You already have a category with this name at this level."}, status=400)

    category = Category(user=request.user, parent=parent, name=name)
    try:
        category.full_clean()
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=400)
    category.save()
    return JsonResponse({"id": category.id, "name": category.name})
