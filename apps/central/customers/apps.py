from django.apps import AppConfig


class CustomersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.central.customers'

    def ready(self):
        # Al importar el archivo de señales, Django las registra automáticamente
        import apps.central.customers.signals
