from rest_framework import serializers
from .models import WorkerRateOverride, PaymentSettlement
from apps.tenants.staff.serializers import WorkerSerializer
from apps.tenants.catalog.serializers import BrandVariantSerializer

class WorkerRateOverrideSerializer(serializers.ModelSerializer):
    worker = WorkerSerializer(read_only=True)
    brand_variant = BrandVariantSerializer(read_only=True)

    class Meta:
        model = WorkerRateOverride
        fields = '__all__'

class PaymentSettlementSerializer(serializers.ModelSerializer):
    worker = WorkerSerializer(read_only=True)
    class Meta:
        model = PaymentSettlement
        fields = '__all__'