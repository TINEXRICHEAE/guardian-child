from django.apps import AppConfig
from django.db.models.signals import post_migrate


class warenessappConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = 'awarenessapp'  # Updated to include the full path
    label = 'awarenessapp'      # Added label

    def ready(self):
        from . import signals  # Import the signals module

        # Connect the post_migrate signal to create the anonymous user
        post_migrate.connect(signals.create_anonymous_user, sender=self)
