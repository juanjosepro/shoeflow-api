from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    PaymentSettlementViewSet,
    SettlementAdjustmentViewSet,
    SpecialtyRateViewSet,
    WorkerRateExtraViewSet,
)

router = DefaultRouter()
router.register(r'rates', SpecialtyRateViewSet, basename='rates')
router.register(r'worker-rates', WorkerRateExtraViewSet, basename='worker-rates')
router.register(r'adjustments', SettlementAdjustmentViewSet, basename='adjustments')
router.register(r'payments', PaymentSettlementViewSet, basename='payments')

urlpatterns = [
    path('', include(router.urls)),
]