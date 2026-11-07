from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django_tenants.utils import get_public_schema_name


def load_staff_defaults(sender, **kwargs):
    # En el esquema público no existe el catálogo
    if connection.schema_name == get_public_schema_name():
        return

    # Solo si el catálogo está vacío: así nunca pisa lo que el usuario cambió
    from .models import Specialty, Worker

    if any(model.objects.exists() for model in (Specialty, Worker)):
        return

    # Cada ambiente carga su propio archivo
    fixture = f"initial_staff_{settings.ENVIRONMENT}.json"
    call_command("loaddata", fixture)
    print(f"✅ {fixture} cargado en '{connection.schema_name}'.")