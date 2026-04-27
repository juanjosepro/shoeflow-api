from django.contrib import admin
from django_tenants.admin import TenantAdminMixin
from .models import Client, Domain # Cambia esto por los nombres reales de tus modelos

@admin.register(Client)
class ClientAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = (
        'schema_name',
        'description',
        'names', 
        'email', 
        'is_active', 
        'created_on',
        'paid_until'
    )
    
    # Opcional: Agregar filtros laterales para facilitar la búsqueda
    # list_filter = ('is_active', 'on_trial', 'created_on')
    
    # Opcional: Agregar un buscador por nombre o subdominio
    search_fields = ('names', 'schema_name', 'email')

@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('domain', 'tenant', 'is_primary')