import uuid
from rest_framework import serializers
from .models import Dozen, DozenStageAssignment
from decimal import Decimal
from django.db import transaction
from apps.tenants.catalog.models import ModelVariant
from apps.tenants.staff.serializers import WorkerSerializer
from apps.tenants.catalog.serializers import ModelVariantSerializer


class DozenStageAssignmentSerializer(serializers.ModelSerializer):
    worker = WorkerSerializer(read_only=True)
    # dozen = DozenSerializer(read_only=True)
    week_identifier = serializers.ReadOnlyField()
    week_label = serializers.ReadOnlyField()
    total_payment = serializers.ReadOnlyField(source='calculate_payment')

    class Meta:
        model = DozenStageAssignment
        # 'dozen',
        fields = [
            'id', 'worker',  'stage', 'status', 
            'delivered_at', 'completed_at',
            'week_identifier', 'week_label', 'total_payment',
            'created_at', 'settlement'
        ]


class DozenSerializer(serializers.ModelSerializer):
    variant = ModelVariantSerializer(source='model_variant', read_only=True)
    assignments = DozenStageAssignmentSerializer(
        many=True,
        read_only=True
    )
    model_variant_id = serializers.PrimaryKeyRelatedField(
        queryset=ModelVariant.objects.all(),
        source='model_variant',
        write_only=True
    )
    worker_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    code = serializers.CharField(read_only=True)
    registration_group = serializers.CharField(read_only=True)

    class Meta:
        model = Dozen
        fields = [
            'id', 'model_variant_id', 'variant', 'code', 'quantity', 
            'material', 'color', 'status', 'description', 
            'is_active', 'registered_at', 'registration_group', 'created_at', 'worker_id', 'assignments'
        ]

    def create(self, validated_data):
        print("REQUEST DATA:", self.initial_data)
        # 1. Extraemos los datos necesarios
        worker_id = validated_data.pop('worker_id', None)
        model_variant = validated_data.get('model_variant')
        
        # 2. Determinamos cuántas veces vamos a crear el registro
        # Si es 0.5, creamos 1. Si es 3.0, creamos 3.
        total_quantity = validated_data.get('quantity', Decimal('1.0'))
        
        # Convertimos a entero para el rango (ej: 3.0 -> 3 vueltas)
        # Si es 0.5, int(0.5) es 0, así que usamos max(1, ...)
        iterations = max(1, int(total_quantity)) if total_quantity >= 1 else 1
        
        # Generamos UN SOLO grupo para toda esta operación asi sea una docena o más
        registration_group = generate_registration_group()
        created_dozens = []

        with transaction.atomic():
            for _ in range(iterations):
                # Generamos un código nuevo para CADA vuelta
                current_code = generate_dozen_code(model_variant.id)
                
                # Creamos la docena individual
                # Usamos una copia para no alterar los datos originales en cada vuelta
                temp_data = validated_data.copy()
                
                # Si la cantidad era por ejemplo 5.0, cada registro individual vale 1.0
                # Pero si era 0.5, el registro vale 0.5
                temp_data['quantity'] = Decimal('1.0') if total_quantity >= 1 else Decimal('0.5')
                temp_data['code'] = current_code
                temp_data['registration_group'] = registration_group

                # Si existe un worker_id, significa que la docena está en estado 'CORTADO'
                if worker_id:
                    temp_data['status'] = Dozen.Status.CUTTING
                
                dozen = Dozen.objects.create(**temp_data)
                created_dozens.append(dozen)

                # 3. En caso de que exista un worker_id de tipo 'Cortador', creamos la asignación
                if worker_id:
                    DozenStageAssignment.objects.create(
                        dozen=dozen,
                        worker_id=worker_id,
                        stage=DozenStageAssignment.Stage.CUTTING,
                        delivered_at=dozen.registered_at
                    )
            
            # DRF espera que el método create devuelva UNA instancia.
            # Devolvemos la última o la primera (esto es normal para ViewSets)
            self._created_dozens = created_dozens
            return created_dozens[0]

    def update(self, instance, validated_data):
        # 1. Extraemos el worker_id (el paracaídas None evita errores)
        worker_id = validated_data.pop('worker_id', None)
        
        with transaction.atomic():
            # 2. Actualizamos la Docena (instance)
            # super().update se encarga de guardar cambios en cantidad, material, color, etc.
            instance = super().update(instance, validated_data)
            
            # 3. Lógica de re-asignación
            if worker_id:
                # Buscamos si ya existe una asignación para esta docena
                # Nota: En ShoeFlow, podrías tener varias asignaciones (cortador, aparador, etc.)
                # Aquí buscamos la que sea de tipo 'PENDIENTE' o 'EN PROCESO' para cambiarla
                assignment = DozenStageAssignment.objects.filter(
                    dozen=instance,
                    # Evitamos cambiar asignaciones que ya están PAGADAS (con settlement)
                    settlement__isnull=True 
                ).first()
                
                if assignment:
                    # Si ya existía una, simplemente cambiamos el dueño
                    assignment.worker_id = worker_id
                    assignment.save()
                else:
                    # Si por alguna razón la docena no tenía asignación, la creamos
                    DozenStageAssignment.objects.create(
                        dozen=instance,
                        worker_id=worker_id,
                        status=DozenStageAssignment.Status.PENDING
                    )
            
            return instance


def generate_dozen_code(model_variant_id):
    from apps.tenants.production.models import Dozen
    from apps.tenants.catalog.models import ModelVariant

    # 1. Obtener directamente el prefijo guardado en el modelo
    variant = ModelVariant.objects.select_related('model').get(id=model_variant_id)
    base_prefix = variant.model.code_prefix.upper()  # Ej: "DOM" o "AIR"

    # 2. Buscar el último código que empiece exactamente con ese prefijo
    last_dozen = Dozen.objects.filter(
        code__startswith=f"{base_prefix}-"
    ).order_by('-code').first()

    new_sequence_number = 1

    if last_dozen:
        # Extraemos la parte numérica de forma súper segura. 
        # Como 'base_prefix' no tiene guiones controlados por el usuario, 
        # rsplit('-', 1) corta únicamente el último guion donde está el número.
        last_code = last_dozen.code
        try:
            last_sequence = int(last_code.rsplit('-', 1)[-1])
            new_sequence_number = last_sequence + 1
        except (ValueError, IndexError):
            new_sequence_number = 1

    # 3. Padding dinámico (mínimo 4 ceros)
    formatted_sequence = f"{new_sequence_number:04d}" 

    return f"{base_prefix}-{formatted_sequence}"

def generate_registration_group():
    return f"BATCH-{uuid.uuid4().hex[:8].upper()}"