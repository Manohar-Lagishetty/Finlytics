from django.apps import AppConfig


class ExpensesConfig(AppConfig):
    name = 'expenses'

    def ready(self):
        from . import signals
        signals.connect()
