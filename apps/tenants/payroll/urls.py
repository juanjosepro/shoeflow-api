from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WorkerRateOverrideViewSet, PaymentSettlementViewSet

router = DefaultRouter()
router.register(r'worker-rates', WorkerRateOverrideViewSet, basename='payroll')
router.register(r'payments', PaymentSettlementViewSet, basename='payments')

urlpatterns = [
    path('', include(router.urls)),
]