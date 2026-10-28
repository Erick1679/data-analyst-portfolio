from django.apps import AppConfig


class AuditlogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'auditlog'

    def ready(self):
        # Register audit signal receivers during Django startup.
        from . import auth_signals  # noqa: F401
