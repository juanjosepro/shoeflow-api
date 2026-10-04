from rest_framework import serializers
from .models import WorkerRateOverride, PaymentSettlement
from apps.tenants.staff.serializers import WorkerSerializer
from apps.tenants.catalog.serializers import ModelVariantSerializer
from apps.tenants.production.models import DozenStageAssignment

class WorkerRateOverrideSerializer(serializers.ModelSerializer):
    worker = WorkerSerializer(read_only=True)
    model_variant = ModelVariantSerializer(read_only=True)

    class Meta:
        model = WorkerRateOverride
        fields = '__all__'

class PaymentSettlementSerializer(serializers.ModelSerializer):
    worker = WorkerSerializer(read_only=True)
    class Meta:
        model = PaymentSettlement
        fields = '__all__'

    # Ejemplo de cómo se llenaría ese campo en el futuro
    def liquidar_semana(worker_id):
        # 1. Creamos el registro de pago
        nuevo_pago = PaymentSettlement.objects.create(
            worker_id=worker_id,
            # ... fechas y totales ...
        )
        
        # 2. "Atamos" las docenas terminadas a ese pago
        DozenStageAssignment.objects.filter(
            worker_id=worker_id, 
            status='COMPLETED', 
            settlement__isnull=True # Solo las que no se han pagado antes
        ).update(settlement=nuevo_pago) # <--- AQUÍ ES DONDE SE LLENA EL CAMPO