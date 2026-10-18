"""Dashboard aggregate logic - date-range resolution, category breakdown,
and spending trend. Extracted out of views.py to keep the view itself thin."""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone

from expenses.models import Category, Expense
from expenses.services import budget_progress_rows, monthly_balance
from expenses.utils import root_category_id

# Validated categorical palette (indigo, orange, teal, fuchsia, lime) — see
# the dataviz skill: passes CVD-separation and normal-vision-floor checks in
# both light and dark mode at this slot order. "Other" gets a neutral gray,
# never a 6th generated hue.
CHART_COLORS_LIGHT = ["#6366f1", "#f97316", "#14b8a6", "#d946ef", "#84cc16"]
CHART_COLORS_DARK = ["#6366f1", "#ea580c", "#0d9488", "#d946ef", "#65a30d"]
OTHER_COLOR = {"light": "#94a3b8", "dark": "#64748b"}
TOP_N_CATEGORIES = 5

RANGE_LABELS = {"today": "Today", "week": "This Week", "month": "This Month", "year": "This Year"}


def resolve_range(request):
    """Returns (start, end, label, key) for the dashboard's active period,
    from ?from=&to= (custom) or ?range=today|week|month|year (default month)."""
    today = timezone.localdate()
    raw_from, raw_to = request.GET.get("from"), request.GET.get("to")

    if raw_from and raw_to:
        try:
            start, end = date.fromisoformat(raw_from), date.fromisoformat(raw_to)
            if start > end:
                start, end = end, start
            return start, end, "Custom range", "custom"
        except ValueError:
            pass

    range_key = request.GET.get("range")
    if range_key not in RANGE_LABELS:
        range_key = "month"

    if range_key == "today":
        start = end = today
    elif range_key == "week":
        start, end = today - timedelta(days=today.weekday()), today
    elif range_key == "year":
        start, end = today.replace(month=1, day=1), today
    else:
        start, end = today.replace(day=1), today

    return start, end, RANGE_LABELS[range_key], range_key


def _date_sequence(start, end):
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _month_sequence(start, end):
    months, cur = [], start.replace(day=1)
    while cur <= end:
        months.append(cur)
        cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
    return months


def category_breakdown(qs, user, total_amount):
    categories_by_id = {c.id: c for c in Category.objects.filter(user=user)}
    totals = defaultdict(lambda: Decimal("0"))
    for category_id, amount in qs.values_list("category_id", "amount"):
        totals[root_category_id(category_id, categories_by_id)] += amount

    rows = sorted(
        (
            {"name": categories_by_id[cid].name if cid in categories_by_id else "Uncategorized", "amount": amount}
            for cid, amount in totals.items()
        ),
        key=lambda row: row["amount"],
        reverse=True,
    )

    top_rows, other_total = rows[:TOP_N_CATEGORIES], sum((row["amount"] for row in rows[TOP_N_CATEGORIES:]), Decimal("0"))
    if other_total:
        top_rows = top_rows + [{"name": "Other", "amount": other_total}]

    for i, row in enumerate(top_rows):
        row["pct"] = round(float(row["amount"] / total_amount * 100), 1) if total_amount else 0
        is_other = bool(other_total) and i == len(top_rows) - 1
        row["color_light"] = OTHER_COLOR["light"] if is_other else CHART_COLORS_LIGHT[i]
        row["color_dark"] = OTHER_COLOR["dark"] if is_other else CHART_COLORS_DARK[i]

    return top_rows


def spending_trend(qs, start, end):
    duration_days = (end - start).days + 1
    if duration_days <= 1:
        return None

    # TruncMonth/TruncDate on a DateTimeField return datetimes/dates
    # respectively - normalize both to plain `date` objects so they key
    # against _month_sequence()/_date_sequence()'s date objects correctly.
    def as_date(value):
        return value.date() if hasattr(value, "date") else value

    if duration_days > 60:
        bucketed = qs.annotate(bucket=TruncMonth("date")).values("bucket").annotate(total=Sum("amount"))
        totals_by_bucket = {as_date(row["bucket"]): row["total"] for row in bucketed}
        buckets = _month_sequence(start, end)
        labels = [b.strftime("%b %Y") for b in buckets]
    else:
        bucketed = qs.annotate(bucket=TruncDate("date")).values("bucket").annotate(total=Sum("amount"))
        totals_by_bucket = {as_date(row["bucket"]): row["total"] for row in bucketed}
        buckets = _date_sequence(start, end)
        labels = [f"{b.strftime('%b')} {b.day}" for b in buckets]

    values = [float(totals_by_bucket.get(b, 0)) for b in buckets]
    return {"labels": labels, "values": values}


def dashboard_summary(user, request):
    """Everything the dashboard needs for the active date range, plus the
    always-current-month balance/budget cards."""
    has_any_expenses = Expense.objects.filter(user=user).exists()

    start, end, range_label, range_key = resolve_range(request)
    qs = Expense.objects.filter(user=user, date__date__range=[start, end])

    totals = qs.aggregate(total=Sum("amount"), count=Count("id"), avg=Avg("amount"))
    total_amount = totals["total"] or Decimal("0")
    count = totals["count"] or 0
    avg_amount = totals["avg"] or Decimal("0")

    duration = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=duration - 1)
    prev_total = (
        Expense.objects.filter(user=user, date__date__range=[prev_start, prev_end]).aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )
    change_pct = round(float((total_amount - prev_total) / prev_total * 100), 1) if prev_total else None

    breakdown = category_breakdown(qs, user, total_amount) if count else []
    trend = spending_trend(qs, start, end) if count else None
    recent_expenses = qs.select_related("category").order_by("-date", "-created_at")[:8]

    return {
        "has_any_expenses": has_any_expenses,
        "range_label": range_label,
        "range_key": range_key,
        "range_from": start.isoformat() if range_key == "custom" else "",
        "range_to": end.isoformat() if range_key == "custom" else "",
        "total_amount": total_amount,
        "count": count,
        "avg_amount": avg_amount,
        "change_pct": change_pct,
        "category_breakdown": breakdown,
        "top_category": breakdown[0] if breakdown else None,
        "trend": trend,
        "recent_expenses": recent_expenses,
        "balance": monthly_balance(user),
        "budget_rows": budget_progress_rows(user),
    }
