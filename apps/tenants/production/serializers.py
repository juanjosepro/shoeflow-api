from django.db import transaction
from rest_framework import serializers

from apps.tenants.catalog.models import Color, MaterialType, Model, PlantType, Size
from apps.tenants.catalog.serializers import (
    ColorSerializer,
    MaterialTypeSerializer,
    ModelSerializer,
    PlantTypeSerializer,
    SizeSerializer,
)
from apps.tenants.staff.models import Specialty, Worker

from . import services
from .models import Dozen, DozenStageAssignment


class WorkerMiniSerializer(serializers.Serializer):
    """Versión ligera del trabajador para listas de asignaciones (evita consultas extra)."""

    id = serializers.IntegerField()
    names = serializers.CharField()
    is_active = serializers.BooleanField()


class SpecialtyMiniSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    order = serializers.IntegerField()


class DozenStageAssignmentSerializer(serializers.ModelSerializer):
    """Solo lectura: las asignaciones se crean con POST /dozens/{id}/assign-stages/."""

    dozen_code = serializers.CharField(source='dozen.code', read_only=True)
    specialty = SpecialtyMiniSerializer(read_only=True)
    worker = WorkerMiniSerializer(read_only=True)
    week_identifier = serializers.ReadOnlyField()
    week_label = serializers.ReadOnlyField()

    class Meta:
        model = DozenStageAssignment
        fields = [
            'id', 'dozen', 'dozen_code', 'specialty', 'worker', 'status',
            'delivered_at', 'completed_at',
            'unit_price', 'amount',
            'week_identifier', 'week_label',
            'settlement', 'description', 'created_at',
        ]
        read_only_fields = fields


class DozenSerializer(serializers.ModelSerializer):
    # Lectura: objetos completos. Escritura: solo el id (model_id / size_id).
    model = ModelSerializer(read_only=True)
    model_id = serializers.PrimaryKeyRelatedField(
        queryset=Model.objects.all(), source='model', write_only=True
    )
    size = SizeSerializer(read_only=True)
    size_id = serializers.PrimaryKeyRelatedField(
        queryset=Size.objects.all(), source='size', write_only=True
    )
    material_type = MaterialTypeSerializer(read_only=True)
    material_type_id = serializers.PrimaryKeyRelatedField(
        queryset=MaterialType.objects.all(), source='material_type', write_only=True
    )
    color = ColorSerializer(read_only=True)
    color_id = serializers.PrimaryKeyRelatedField(
        queryset=Color.objects.all(), source='color', write_only=True
    )
    plant_type = PlantTypeSerializer(read_only=True)
    plant_type_id = serializers.PrimaryKeyRelatedField(
        queryset=PlantType.objects.all(), source='plant_type', write_only=True
    )
    # Fracción de docena (pairs / 12), solo lectura
    fraction = serializers.DecimalField(max_digits=5, decimal_places=4, read_only=True)
    assignments = DozenStageAssignmentSerializer(many=True, read_only=True)
    # Avance: etapas activas asignadas / etapas activas totales
    assigned_stages = serializers.SerializerMethodField()
    total_stages = serializers.SerializerMethodField()
    code = serializers.CharField(read_only=True)
    registration_group = serializers.CharField(read_only=True)
    # Solo al crear: cuántas docenas idénticas (cada una con su propio código)
    count = serializers.IntegerField(write_only=True, required=False, default=1, min_value=1, max_value=100)

    # Campos que fijan el precio de las etapas: no cambian si ya hay asignaciones
    PRICE_FIELDS = ('model', 'size', 'pairs', 'material_type', 'plant_type')

    class Meta:
        model = Dozen
        fields = [
            'id', 'model', 'model_id', 'size', 'size_id', 'code', 'pairs', 'fraction',
            'material_type', 'material_type_id', 'color', 'color_id', 'plant_type', 'plant_type_id', 'priority', 'status', 'description',
            'is_active', 'registered_at', 'registration_group', 'created_at',
            'count', 'assignments', 'assigned_stages', 'total_stages',
        ]
        # El estado solo cambia por las acciones de asignar, completar, rechazar y reabrir
        read_only_fields = ['status']

    def get_total_stages(self, obj):
        # Se calcula una sola vez por respuesta (el serializer hijo se comparte en listas)
        if not hasattr(self, '_total_stages'):
            self._total_stages = Specialty.objects.filter(is_active=True).count()
        return self._total_stages

    def get_assigned_stages(self, obj):
        # Usa las asignaciones ya precargadas, sin consultas extra
        return sum(1 for a in obj.assignments.all() if a.specialty.is_active)

    def validate(self, attrs):
        if self.instance and self.instance.assignments.exists():
            changed = [
                f for f in self.PRICE_FIELDS
                if f in attrs and attrs[f] != getattr(self.instance, f)
            ]
            if changed:
                raise serializers.ValidationError(
                    f"La docena ya tiene etapas asignadas; no se puede cambiar: {', '.join(changed)}."
                )
        return attrs

    def create(self, validated_data):
        count = validated_data.pop('count', 1)
        registration_group = services.generate_registration_group()
        created = []

        with transaction.atomic():
            for _ in range(count):
                # Un código nuevo por cada docena
                data = {
                    **validated_data,
                    'code': services.generate_dozen_code(validated_data['model']),
                    'registration_group': registration_group,
                }
                created.append(Dozen.objects.create(**data))

        # DRF espera UNA instancia; las demás se pueden leer por registration_group
        self._created_dozens = created
        return created[0]

    def update(self, instance, validated_data):
        validated_data.pop('count', None)
        return super().update(instance, validated_data)


# --- Asignación masiva (entrada) ------------------------------------------

class AssignStageItemSerializer(serializers.Serializer):
    specialty = serializers.PrimaryKeyRelatedField(queryset=Specialty.objects.all())
    worker = serializers.PrimaryKeyRelatedField(queryset=Worker.objects.all())
    delivered_at = serializers.DateField()
    completed_at = serializers.DateField()
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class AssignStagesSerializer(serializers.Serializer):
    """Cuerpo de POST /dozens/{id}/assign-stages/"""

    assignments = AssignStageItemSerializer(many=True, allow_empty=False)