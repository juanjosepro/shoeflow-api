from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django_tenants.utils import get_public_schema_name


def load_catalog_defaults(sender, **kwargs):
    # En el esquema público no existe el catálogo
    if connection.schema_name == get_public_schema_name():
        return

    # Solo si el catálogo está vacío: así nunca pisa lo que el usuario cambió
    from .models import Category, Color, MaterialType, PlantType, Size

    if any(model.objects.exists() for model in (Category, Size, MaterialType, Color, PlantType)):
        return

    # Cada ambiente carga su propio archivo
    fixture = f"initial_catalog_{settings.ENVIRONMENT}.json"
    call_command("loaddata", fixture)
    print(f"✅ {fixture} cargado en '{connection.schema_name}'.")