from django.apps import AppConfig
from django.db.models.signals import post_migrate


class StaffConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tenants.staff'

    def ready(self):
        # Importamos la función aquí para evitar problemas de carga
        from .signals import load_staff_defaults
        post_migrate.connect(load_staff_defaults, sender=self)