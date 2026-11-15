# [PED] ARCHIVO NUEVO ─ backend/production/order_serializers.py
"""Serializers de Clientes y Pedidos."""
from django.utils import timezone
from rest_framework import serializers

from apps.tenants.catalog.models import Color, MaterialType, Model, PlantType, Size

from . import services
from .models import Customer, CustomerOrder
from apps.tenants.production.serializers import CustomerMiniSerializer, DozenSerializer


# --------------------------------------------------------------------------
# Clientes
# --------------------------------------------------------------------------

class CustomerSerializer(serializers.ModelSerializer):
    # Se llenan con annotate() en CustomerViewSet (sin consultas extra por fila)
    orders_count = serializers.IntegerField(read_only=True, default=0)
    open_orders_count = serializers.IntegerField(read_only=True, default=0)
    last_order_at = serializers.DateField(read_only=True, default=None)

    class Meta:
        model = Customer
        fields = [
            'id', 'name', 'document', 'phone', 'email', 'address', 'notes', 'is_active',
            'orders_count', 'open_orders_count', 'last_order_at', 'created_at',
        ]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('El nombre es obligatorio.')
        return value

    def validate_document(self, value):
        # Vacío = sin documento (NULL), para que varios clientes puedan no tenerlo
        value = (value or '').strip()
        return value or None


# --------------------------------------------------------------------------
# Pedidos: líneas (entrada)
# --------------------------------------------------------------------------

class OrderLineSerializer(serializers.Serializer):
    """Una línea = un tipo de docena × `count`. Mismos campos que el formulario de docena."""

    model_id = serializers.PrimaryKeyRelatedField(queryset=Model.objects.all(), source='model')
    size_id = serializers.PrimaryKeyRelatedField(queryset=Size.objects.all(), source='size')
    material_type_id = serializers.PrimaryKeyRelatedField(queryset=MaterialType.objects.all(), source='material_type')
    color_id = serializers.PrimaryKeyRelatedField(queryset=Color.objects.all(), source='color')
    plant_type_id = serializers.PrimaryKeyRelatedField(
        queryset=PlantType.objects.all(), source='plant_type', allow_null=True, required=False
    )
    pairs = serializers.IntegerField(min_value=1, max_value=12, default=12)
    size_run = serializers.JSONField(required=False, allow_null=True)
    count = serializers.IntegerField(min_value=1, max_value=100, default=1)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    # Misma validación de serie de tallas que la docena (se reutiliza, no se duplica)
    validate_size_run = DozenSerializer.validate_size_run

    def validate(self, attrs):
        size_run = attrs.get('size_run')
        if size_run and sum(size_run.values()) != attrs['pairs']:
            raise serializers.ValidationError(
                {'size_run': f"La serie suma {sum(size_run.values())} pares y la docena tiene {attrs['pairs']}."}
            )
        return attrs


class AddDozensSerializer(serializers.Serializer):
    """Cuerpo de POST /orders/{id}/add-dozens/"""

    lines = OrderLineSerializer(many=True, allow_empty=False)


class OrderWriteSerializer(serializers.Serializer):
    """Crear (con `lines`) o editar (solo cabecera) un pedido."""

    customer_id = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all(), source='customer')
    ordered_at = serializers.DateField(default=timezone.localdate)
    due_date = serializers.DateField(required=False, allow_null=True)
    priority = serializers.ChoiceField(choices=CustomerOrder.Priority.choices, default=CustomerOrder.Priority.NORMAL)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    lines = OrderLineSerializer(many=True, required=False, allow_empty=False)

    def validate_customer_id(self, customer):
        # No se le crean pedidos nuevos a un cliente desactivado (sí se puede conservar en uno existente)
        if not customer.is_active and (not self.instance or self.instance.customer_id != customer.id):
            raise serializers.ValidationError('El cliente está desactivado.')
        return customer

    def validate(self, attrs):
        if self.instance is None and not attrs.get('lines'):
            raise serializers.ValidationError({'lines': 'Agrega al menos una línea al pedido.'})
        ordered_at = attrs.get('ordered_at') or (self.instance.ordered_at if self.instance else None)
        due = attrs.get('due_date', self.instance.due_date if self.instance else None)
        if due and ordered_at and due < ordered_at:
            raise serializers.ValidationError({'due_date': 'La entrega no puede ser anterior a la fecha del pedido.'})
        return attrs


# --------------------------------------------------------------------------
# Pedidos: lectura
# --------------------------------------------------------------------------

class OrderSerializer(serializers.ModelSerializer):
    """Lista: cabecera + avance. Usa las anotaciones de services.annotate_orders()."""

    customer = CustomerMiniSerializer(read_only=True)
    status = serializers.CharField(read_only=True)
    n_total = serializers.IntegerField(read_only=True)
    n_done = serializers.IntegerField(read_only=True)
    n_busy = serializers.IntegerField(read_only=True)
    n_rejected = serializers.IntegerField(read_only=True)
    pairs_total = serializers.IntegerField(read_only=True, default=0)
    progress = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = CustomerOrder
        fields = [
            'id', 'code', 'customer', 'ordered_at', 'due_date', 'priority', 'notes',
            'status', 'closure', 'closed_at',
            'n_total', 'n_done', 'n_busy', 'n_rejected', 'pairs_total', 'progress', 'is_overdue',
            'created_at',
        ]
        read_only_fields = fields

    def get_progress(self, obj):
        # Porcentaje de docenas completadas (0-100)
        return round(obj.n_done * 100 / obj.n_total) if obj.n_total else 0

    def get_is_overdue(self, obj):
        # Atrasado: pasó la fecha de entrega y aún no está entregado ni cancelado
        return bool(
            obj.due_date and obj.status in services.OPEN_STATUSES and obj.due_date < timezone.localdate()
        )


class OrderDetailSerializer(OrderSerializer):
    """Detalle: además, todas sus docenas (con asignaciones y avance)."""

    dozens = DozenSerializer(many=True, read_only=True)

    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields + ['dozens']
        read_only_fields = fields
