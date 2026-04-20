from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CatalogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tenants.catalog'

    def ready(self):
        # Importamos la función aquí para evitar problemas de carga
        from .signals import load_catalog_defaults
        post_migrate.connect(load_catalog_defaults, sender=self)
