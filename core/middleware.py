"""
Middleware personalizado de ShoeFlow.
"""
from django_tenants.middleware.main import TenantMainMiddleware
from django_tenants.utils import remove_www


class HeaderTenantMiddleware(TenantMainMiddleware):
    """
    Decide el tenant según el header X-Tenant (ej: 'nikfort.juanjosepau.dev').
    Necesario porque todos los frontends llaman al MISMO host de API.
    Si el header no viene (ej: desarrollo con tenant.localhost), usa el Host
    de la petición, que es el comportamiento normal de django-tenants.
    """

    def hostname_from_request(self, request):
        tenant_header = request.headers.get('X-Tenant')
        if tenant_header:
            return remove_www(tenant_header.split(':')[0])
        return remove_www(request.get_host().split(':')[0])