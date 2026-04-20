from rest_framework import viewsets
from .models import WorkerRateOverride, PaymentSettlement
from .serializers import WorkerRateOverrideSerializer, PaymentSettlementSerializer

class WorkerRateOverrideViewSet(viewsets.ModelViewSet):
    queryset = WorkerRateOverride.objects.all()
    serializer_class = WorkerRateOverrideSerializer

class PaymentSettlementViewSet(viewsets.ModelViewSet):
    queryset = PaymentSettlement.objects.all()
    serializer_class = PaymentSettlementSerializer
