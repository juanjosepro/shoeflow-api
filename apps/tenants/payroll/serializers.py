from rest_framework import serializers

from apps.tenants.staff.models import Worker
from apps.tenants.production.serializers import (
    DozenStageAssignmentSerializer,
    WorkerMiniSerializer,
)

from .models import PaymentSettlement, SettlementAdjustment, SpecialtyRate, WorkerRateExtra


# --- Tarifas por regla -----------------------------------------------------

class SpecialtyRateSerializer(serializers.ModelSerializer):
    # Lectura: nombres para mostrar en la tabla. Escritura: los ids (model/size pueden ser null = "cualquiera").
    specialty_name = serializers.CharField(source='specialty.name', read_only=True)
    model_name = serializers.CharField(source='model.name', read_only=True, default=None)
    size_name = serializers.CharField(source='size.name', read_only=True, default=None)
    material_type_name = serializers.CharField(source='material_type.name', read_only=True, default=None)
    plant_type_name = serializers.CharField(source='plant_type.name', read_only=True, default=None)
    specificity = serializers.IntegerField(read_only=True)

    class Meta:
        model = SpecialtyRate
        fields = [
            'id', 'specialty', 'specialty_name',
            'model', 'model_name', 'size', 'size_name',
            'material_type', 'material_type_name', 'plant_type', 'plant_type_name',
            'price', 'specificity', 'created_at', 'updated_at',
        ]
        # Desactivamos el validador automático de unicidad: no maneja bien los NULL.
        # La repetición se valida abajo en validate().
        validators = []

    def validate(self, attrs):
        def value(name):
            if name in attrs:
                return attrs[name]
            return getattr(self.instance, name, None) if self.instance else None

        lookup = {
            'specialty': value('specialty'),
            'model': value('model'),
            'size': value('size'),
            'material_type': value('material_type'),
            'plant_type': value('plant_type'),
        }
        qs = SpecialtyRate.objects.filter(**lookup)  # filter(campo=None) se traduce a IS NULL
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe una tarifa con exactamente estas condiciones.")
        return attrs


# --- Extra por trabajador ---------------------------------------------------

class WorkerRateExtraSerializer(serializers.ModelSerializer):
    worker_name = serializers.CharField(source='worker.names', read_only=True)
    specialty_name = serializers.CharField(source='specialty.name', read_only=True)

    class Meta:
        model = WorkerRateExtra
        fields = [
            'id', 'worker', 'worker_name', 'specialty', 'specialty_name',
            'extra_price', 'created_at', 'updated_at',
        ]
        validators = []

    def validate(self, attrs):
        worker = attrs.get('worker') or (self.instance.worker if self.instance else None)
        specialty = attrs.get('specialty') or (self.instance.specialty if self.instance else None)

        if not worker.specialties.filter(pk=specialty.pk).exists():
            raise serializers.ValidationError(f"{worker.names} no tiene la especialidad {specialty.name}.")

        qs = WorkerRateExtra.objects.filter(worker=worker, specialty=specialty)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Este trabajador ya tiene un extra para esa especialidad.")
        return attrs


# --- Ajustes (bonos, descuentos, adelantos, saldos) -------------------------

class SettlementAdjustmentSerializer(serializers.ModelSerializer):
    worker_name = serializers.CharField(source='worker.names', read_only=True)
    type_label = serializers.CharField(source='get_type_display', read_only=True)
    signed_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = SettlementAdjustment
        fields = [
            'id', 'worker', 'worker_name', 'settlement',
            'type', 'type_label', 'amount', 'signed_amount', 'reason',
            'created_at',
        ]
        # settlement solo lo llena el pago semanal
        read_only_fields = ['settlement']


# --- Pagos semanales -------------------------------------------------------

class PaymentSettlementSerializer(serializers.ModelSerializer):
    """Versión de lista: solo totales."""

    worker = WorkerMiniSerializer(read_only=True)

    class Meta:
        model = PaymentSettlement
        fields = [
            'id', 'worker', 'start_date', 'end_date',
            'total_earned', 'total_adjustments', 'total_to_pay',
            'amount_paid', 'pending_balance', 'description', 'created_at',
        ]
        read_only_fields = fields


class PaymentSettlementDetailSerializer(PaymentSettlementSerializer):
    """Versión de detalle: con las etapas y ajustes que entraron en el pago."""

    items = DozenStageAssignmentSerializer(many=True, read_only=True)
    adjustments = SettlementAdjustmentSerializer(many=True, read_only=True)

    class Meta(PaymentSettlementSerializer.Meta):
        fields = PaymentSettlementSerializer.Meta.fields + ['items', 'adjustments']
        read_only_fields = fields


class SettlementRangeSerializer(serializers.Serializer):
    """Parámetros de la vista previa: trabajador y semana."""

    worker = serializers.PrimaryKeyRelatedField(queryset=Worker.objects.all())
    start_date = serializers.DateField()
    end_date = serializers.DateField()

    def validate(self, attrs):
        if attrs['end_date'] < attrs['start_date']:
            raise serializers.ValidationError("La fecha final no puede ser anterior a la inicial.")
        return attrs


class WorkerParamSerializer(serializers.Serializer):
    """Parámetro de pending-weeks: solo el trabajador."""

    worker = serializers.PrimaryKeyRelatedField(queryset=Worker.objects.all())


class SettlementCreateSerializer(SettlementRangeSerializer):
    """Cuerpo de POST /payments/: lo que se entrega realmente."""

    # None/omitido = todas las etapas pendientes del rango; lista = solo esas
    assignment_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_null=True, allow_empty=True
    )
    # Omitido = el total a pagar. Con selección parcial debe coincidir con el total.
    amount_paid = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)