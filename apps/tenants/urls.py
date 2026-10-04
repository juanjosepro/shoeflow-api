# apps/tenants/urls.py (o el archivo que agrupa tus módulos)
from django.urls import path, include
from rest_framework.authtoken import views
from .views import LogoutView, CurrentUserView

urlpatterns = [
    # Login route for each Tenant
    path('auth/login/', views.obtain_auth_token, name='tenant_login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/me/', CurrentUserView.as_view(), name='current-user'),
    
    # Rest of your modules
    path('catalog/', include('apps.tenants.catalog.urls')),
    path('staff/', include('apps.tenants.staff.urls')),
    path('production/', include('apps.tenants.production.urls')),
    path('payroll/', include('apps.tenants.payroll.urls')),
]