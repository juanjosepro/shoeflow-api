from rest_framework import serializers
from django.db import transaction
from rest_framework.validators import UniqueValidator
from .models import Category, Model, Size, ModelVariant

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'

class SizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Size
        fields = '__all__'

# 1. Definimos una versión "ligera" del modelo (Sin el campo 'variants')
class ModelSimpleSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    
    class Meta:
        model = Model
        # Solo los campos que quieres ver del modelo, pero NO 'variants'
        fields = ['id', 'name', 'code_prefix', 'description', 'category', 'is_active']

class ModelVariantSerializer(serializers.ModelSerializer):
    size = SizeSerializer(read_only=True)
    model = ModelSimpleSerializer(read_only=True)

    class Meta:
        model = ModelVariant
        fields = '__all__'

    # Leemos si nos pasan un argumento especial llamado 'exclude_fields'
    def __init__(self, *args, exclude_fields=None, **kwargs):
        super().__init__(*args, **kwargs)
        if exclude_fields:
            for field_name in exclude_fields:
                # Si el campo existe, lo quitamos de la lista de campos que se van a serializar.
                self.fields.pop(field_name, None)

class VariantPriceField(serializers.DictField):
    """
    Valida el diccionario {"<size_id>": "<price>"} que manda el frontend.
    Reemplaza el acceso crudo a request.data: ahora pasa por validación real.
    """
    child = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)

class ModelSerializer(serializers.ModelSerializer):
    # Para MOSTRAR la categoría completa en los GET
    category = CategorySerializer(read_only=True)

    # Para RECIBIR solo el ID de la categoría en los POST/PUT
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source='category', # OBLIGATORIO: Apunta a la relación real en el modelo
        write_only=True
    )
 
    # Sobrescribimos el campo name para aplicar un validador que ignore mayúsculas/minúsculas
    # Aduana de la API: Valida que el nombre sea único sin importar mayúsculas/minúsculas
    name = serializers.CharField(
        max_length=100,
        validators=[
            UniqueValidator(
                queryset=Model.objects.all(),
                lookup='iexact',  # <--- 'iexact' significa "Case-Insensitive Exact match"
                message="Ya existe una marca con este nombre"
            )
        ]
    )
   
    code_prefix = serializers.CharField(
        max_length=10,
        validators=[
            UniqueValidator(
                queryset=Model.objects.all(),
                lookup='iexact',
                message="Ya existe un prefijo de modelo con este nombre"
            )
        ]
    )
    # -------------------------------------------------------------------------
    # CAMPO CALCULADO (SerializerMethodField)
    # -------------------------------------------------------------------------
    # 'variants' NO existe en la tabla Model de la base de datos.
    # Con SerializerMethodField() le decimos a Django REST Framework:
    # "Crea un campo artificial en el JSON final, pero calcula su valor 
    # ejecutando una función de Python".
    variants = serializers.SerializerMethodField()

    # Escritura: {"1": 120.50, "2": 135.00} — ahora SÍ validado por DRF
    model_variants = VariantPriceField(write_only=True, required=False)

    class Meta:
        model = Model
        fields = '__all__'

    # OBLIGATORIO: 'validate_' + 'nombre_del_campo'. Se ejecuta automáticamente.
    # Eliminamos los espacios en blanco y convertimos a mayúsculas
    def validate_name(self, value):
        return value.strip().upper()
    
    def validate_code_prefix(self, value):
        return value.strip().upper()

    def validate_model_variants(self, value):
        size_ids = {int(k) for k in value.keys()}
        existing_ids = set(
            Size.objects.filter(id__in=size_ids).values_list('id', flat=True)
        )
        missing = size_ids - existing_ids
        if missing:
            raise serializers.ValidationError(
                f"Las siguientes tallas no existen: {sorted(missing)}"
            )
        return value

    # OBLIGATORIO: 'get_' + 'nombre_de_la_variable_SerializerMethodField'.
    def get_variants(self, obj):
        # 1. Viajamos a la tabla 'ModelVariant' gracias al related_name='variants'
        #    y traemos todas las variantes (tallas/precios) asociadas a ESTE modelo.
        queryset = obj.variants.all()
        # 2. Pasamos esa lista de variantes por el 'ModelVariantSerializer' para convertirlas a JSON.
        #    Usamos el truco 'exclude_fields=['model']' para que la variante NO vuelva a meter
        #    la información del modelo dentro de sí misma (evitando un bucle infinito).
        return ModelVariantSerializer(queryset, many=True, exclude_fields=['model']).data

    @staticmethod
    def _sync_variants(model, variants_data):
        # bulk_create: inserta TODA la lista en UNA sola consulta SQL.
        # En vez de hacer N INSERT (uno por cada variante), hace 1 solo.
        # Mucho más rápido cuando insertas muchos registros a la vez.
        # ⚠️ No llama a save() ni dispara signals (pre_save/post_save).
        # ⚠️ No devuelve los IDs en todos los backends (salvo returning_ids=True en Django 4.0+).
        ModelVariant.objects.bulk_create([
            ModelVariant(model=model, size_id=int(size_id), standard_price=price)
            for size_id, price in variants_data.items()
        ])

    def create(self, validated_data):
        variants_data = validated_data.pop('model_variants', {})

        with transaction.atomic():
            model = Model.objects.create(**validated_data)

            self._sync_variants(model, variants_data)

        return model

    def update(self, instance, validated_data):
        variants_data = validated_data.pop('model_variants', None)

        with transaction.atomic():
            instance = super().update(instance, validated_data)

            if variants_data is not None:
                instance.variants.all().delete()
                self._sync_variants(instance, variants_data)

        return instance