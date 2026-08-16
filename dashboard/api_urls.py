from django.urls import path

from . import api_views

app_name = "dashboard_api"

urlpatterns = [
    path("summary/", api_views.summary, name="summary"),
]
