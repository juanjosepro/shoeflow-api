from django.contrib import admin
from django.urls import path, include
from rest_framework.views import APIView
from rest_framework.response import Response
from django.views.generic.base import RedirectView

class APIRoot(APIView):
    """
    Esta es la 'Parte 3'. Al entrar a /api/v1/ verás este mapa de módulos.
    """
    def get(self, request, format=None):
        base_url = request.build_absolute_uri()
        return Response({
            'version': 'v1',
            'modules': {
                'catalog': f"{base_url}catalog/",
                'staff': f"{base_url}staff/",
                'production': f"{base_url}production/",
                'payroll': f"{base_url}payroll/",
            }
        })

urlpatterns = [
    path('', RedirectView.as_view(url='api/v1/', permanent=False), name='index'),

    path('admin/', admin.site.urls),
    
    # Agrupamos todo bajo v1 con un namespace para evitar errores de nombres
    path('api/v1/', include(([
        path('', APIRoot.as_view(), name='root'),
        path('', include('apps.tenants.urls'))
    ], 'v1'))),

    path('api-auth/', include('rest_framework.urls')),
]