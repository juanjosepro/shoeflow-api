# apps/tenants/urls.py (o el archivo que agrupa tus módulos)
from django.urls import path, include
from rest_framework.authtoken import views
from apps.tenants.staff.views import LogoutView

urlpatterns = [
    # Ruta de login específica para cada Tenant
    path('login/', views.obtain_auth_token, name='tenant_login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    
    # El resto de tus módulos que ya configuramos
    path('catalog/', include('apps.tenants.catalog.urls')),
    path('staff/', include('apps.tenants.staff.urls')),
    path('production/', include('apps.tenants.production.urls')),
    path('payroll/', include('apps.tenants.payroll.urls')),
]