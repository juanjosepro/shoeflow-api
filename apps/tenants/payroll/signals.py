from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django_tenants.utils import get_public_schema_name

FIXTURES = {
    "dev": "initial_payroll_dev.json",
    "prod": "initial_payroll_prod.json",
}


def load_payroll_defaults(sender, **kwargs):
    # Si este ambiente no tiene fixture (producción), no hay nada que cargar
    fixture = FIXTURES.get(settings.ENVIRONMENT)
    if fixture is None:
        return

    # En el esquema público no existen las tarifas
    if connection.schema_name == get_public_schema_name():
        return

    # Solo si todavía no hay tarifas: así nunca pisa lo que el usuario cambió
    from .models import SpecialtyRate

    if SpecialtyRate.objects.exists():
        return

    call_command("loaddata", fixture)
    print(f"✅ {fixture} cargado en '{connection.schema_name}'.")