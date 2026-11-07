from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .portal import (
    PortalAssignmentsView,
    PortalLoginView,
    PortalPaymentDetailView,
    PortalPaymentsView,
    PortalSummaryView,
)

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

# Portal del trabajador (acceso con DNI, solo lectura)
portal_urls = [
    path('portal/login/', PortalLoginView.as_view()),
    path('portal/summary/', PortalSummaryView.as_view()),
    path('portal/assignments/', PortalAssignmentsView.as_view()),
    path('portal/payments/', PortalPaymentsView.as_view()),
    path('portal/payments/<int:pk>/', PortalPaymentDetailView.as_view()),
]

urlpatterns = [
    *portal_urls,
    path('', include(router.urls)),
]