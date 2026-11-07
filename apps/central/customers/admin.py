from django.contrib import admin
from django_tenants.admin import TenantAdminMixin
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

@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('domain', 'tenant', 'is_primary')