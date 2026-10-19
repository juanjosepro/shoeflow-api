from django.db import transaction
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.tenants.payroll import services as payroll_services
from apps.tenants.staff.models import Specialty

from .models import Category, Color, MaterialType, Model, PlantType, Size

def _unique_name(model, message):
    """Nombre único sin distinguir mayúsculas/minúsculas."""
    return serializers.CharField(
        max_length=100,
        validators=[UniqueValidator(queryset=model.objects.all(), lookup='iexact', message=message)],
    )

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


class SizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Size
        fields = '__all__'

class ModelSizeRateSerializer(serializers.Serializer):
    """Una celda del formulario: precio por docena de una especialidad en una talla.
    price = null significa "sin precio propio" (usa la tarifa general)."""
 
    specialty = serializers.PrimaryKeyRelatedField(queryset=Specialty.objects.all())
    size = serializers.PrimaryKeyRelatedField(queryset=Size.objects.all())
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, allow_null=True)


class ModelSerializer(serializers.ModelSerializer):
    # Para MOSTRAR la categoría completa en los GET
    category = CategorySerializer(read_only=True)

    # Para RECIBIR solo el ID de la categoría en los POST/PUT
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source='category',  # OBLIGATORIO: apunta a la relación real en el modelo
        # write_only=True,
    )

    # Valida que el nombre sea único sin importar mayúsculas/minúsculas
    name = serializers.CharField(
        max_length=100,
        validators=[
            UniqueValidator(
                queryset=Model.objects.all(),
                lookup='iexact',  # Case-insensitive exact match
                message="Ya existe un modelo con este nombre",
            )
        ],
    )

    code_prefix = serializers.CharField(
        max_length=10,
        validators=[
            UniqueValidator(
                queryset=Model.objects.all(),
                lookup='iexact',
                message="Ya existe un modelo con este prefijo",
            )
        ],
    )

    # Solo escritura: precios por especialidad y talla. Al leer se agrega en to_representation.
    size_rates = ModelSizeRateSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = Model
        fields = '__all__'

    # 'validate_' + nombre del campo: se ejecuta automáticamente.
    # Quitamos espacios y pasamos a mayúsculas.
    def validate_name(self, value):
        return value.strip().upper()

    def validate_code_prefix(self, value):
        return value.strip().upper()

    # Los precios solo se devuelven al ver o guardar UN modelo (no en la lista de tarjetas)
    SIZE_RATES_ACTIONS = ("retrieve", "create", "update", "partial_update")
 
    def to_representation(self, instance):
        data = super().to_representation(instance)
        view = self.context.get("view")
        if view is not None and view.action in self.SIZE_RATES_ACTIONS:
            data["size_rates"] = [
                {"specialty": r.specialty_id, "size": r.size_id, "price": r.price}
                for r in payroll_services.get_model_size_rates(instance)
            ]
        return data
 
    def create(self, validated_data):
        size_rates = validated_data.pop("size_rates", None)
        with transaction.atomic():
            model = super().create(validated_data)
            if size_rates:
                payroll_services.sync_model_size_rates(model, size_rates)
        return model
 
    def update(self, instance, validated_data):
        size_rates = validated_data.pop("size_rates", None)
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            if size_rates:
                payroll_services.sync_model_size_rates(instance, size_rates)
        return instance

 
class MaterialTypeSerializer(serializers.ModelSerializer):
    name = _unique_name(MaterialType, "Ya existe un material con este nombre")
 
    class Meta:
        model = MaterialType
        fields = '__all__'
 
    def validate_name(self, value):
        return value.strip()
 
 
class PlantTypeSerializer(serializers.ModelSerializer):
    name = _unique_name(PlantType, "Ya existe un tipo de planta con este nombre")
 
    class Meta:
        model = PlantType
        fields = '__all__'
 
    def validate_name(self, value):
        return value.strip()
 
 
class ColorSerializer(serializers.ModelSerializer):
    name = _unique_name(Color, "Ya existe un color con este nombre")
 
    class Meta:
        model = Color
        fields = '__all__'
 
    def validate_name(self, value):
        return value.strip()
 
    def validate_hex_code(self, value):
        # El formato ya lo valida el modelo; aquí solo se normaliza a mayúsculas
        value = value.strip().upper()
        qs = Color.objects.filter(hex_code=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un color con este código hexadecimal")
        return value
 