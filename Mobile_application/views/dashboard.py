from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from dashboard.services import dashboard_summary


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def summary(request):
    data = dashboard_summary(request.user, request)
    balance = data["balance"]

    return Response(
        {
            "has_any_expenses": data["has_any_expenses"],
            "range_label": data["range_label"],
            "range_key": data["range_key"],
            "range_from": data["range_from"],
            "range_to": data["range_to"],
            "total_amount": str(data["total_amount"]),
            "count": data["count"],
            "avg_amount": str(data["avg_amount"]),
            "change_pct": data["change_pct"],
            "category_breakdown": [
                {
                    "name": row["name"],
                    "amount": str(row["amount"]),
                    "pct": row["pct"],
                    "color_light": row["color_light"],
                    "color_dark": row["color_dark"],
                }
                for row in data["category_breakdown"]
            ],
            "trend": data["trend"],
            "recent_expenses": [
                {
                    "uuid": str(expense.uuid),
                    "amount": str(expense.amount),
                    "category": expense.category.name,
                    "category_uuid": str(expense.category.uuid),
                    "date": expense.date.isoformat(),
                    "note": expense.note,
                    "location": expense.location,
                    "payment_type": expense.payment_type,
                }
                for expense in data["recent_expenses"]
            ],
            "balance": {
                "is_configured": balance["is_configured"],
                "recurring_total": str(balance["recurring_total"]),
                "adhoc_total": str(balance["adhoc_total"]),
                "income_total": str(balance["income_total"]),
                "expenses_total": str(balance["expenses_total"]),
                "balance": str(balance["balance"]),
                "low_balance_threshold": str(balance["low_balance_threshold"]),
                "is_low": balance["is_low"],
            },
            "budget_rows": [
                {
                    "category": row["budget"].category.name,
                    "category_uuid": str(row["budget"].category.uuid),
                    "monthly_cap": str(row["budget"].monthly_cap),
                    "spent": str(row["spent"]),
                    "bar_pct": row["bar_pct"],
                    "pct": row["pct"],
                    "status": row["status"],
                }
                for row in data["budget_rows"]
            ],
        }
    )
