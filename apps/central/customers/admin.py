from django.contrib import admin
from django.db import transaction
from django_tenants.admin import TenantAdminMixin
from django_tenants.signals import post_schema_sync

from .models import Client, Domain


@admin.register(Client)
class ClientAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = (
        'schema_name',
        'business_name',
        'business_legal_name',
        'business_ruc',
        'business_address',
        'business_phone',
        'business_email',
        'owner_names',
        'owner_last_names',
        'owner_dni',
        'owner_email',
        'owner_phone',
        'paid_until',
        'on_trial',
        'is_active',
        'comments',
        'created_on',
    )

    # Opcional: Agregar filtros laterales para facilitar la búsqueda
    # list_filter = ('is_active', 'on_trial', 'created_on')

    # Opcional: Agregar un buscador por nombre o subdominio
    search_fields = ('business_name', 'schema_name', 'owner_dni')

    def save_model(self, request, obj, form, change):
        # Al editar, comportamiento normal
        if change:
            return super().save_model(request, obj, form, change)

        # Al crear: guardar SIN crear el schema (evita el error de la transacción)
        obj.auto_create_schema = False
        super().save_model(request, obj, form, change)

        # Crear el schema cuando la transacción ya terminó
        def _create():
            obj.create_schema(check_if_exists=True, verbosity=1)
            post_schema_sync.send(sender=type(obj), tenant=obj.serializable_fields())

        transaction.on_commit(_create)


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('domain', 'tenant', 'is_primary')