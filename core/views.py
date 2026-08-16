from django.shortcuts import redirect, render


def landing(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    return render(request, "core/landing.html")
