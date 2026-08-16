from django.apps import AppConfig


class MobileApplicationConfig(AppConfig):
    """All logic and routing for the Flutter mobile app's JSON API lives
    here, kept apart from the web app's server-rendered views (accounts/
    core/dashboard/expenses). It reads and writes the same models as the
    web app - it's a second API surface over shared data, not a separate
    data store."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "Mobile_application"
    label = "mobile_application"
