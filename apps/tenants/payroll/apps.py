from django.apps import AppConfig
from django.db.models.signals import post_migrate

class PayrollConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tenants.payroll'

    def ready(self):
        # Importamos la función aquí para evitar problemas de carga
        from .signals import load_payroll_defaults
        post_migrate.connect(load_payroll_defaults, sender=self)