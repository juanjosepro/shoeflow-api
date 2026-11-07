from django.contrib.auth.hashers import make_password
from django.db import transaction
from rest_framework import serializers

from apps.tenants.payroll.models import SpecialtyRate, WorkerRateExtra
from apps.common.validators import ensure_unique, unique_char_field, unique_iexact

from .models import Specialty, Worker


class SpecialtySerializer(serializers.ModelSerializer):
    name = unique_char_field(Specialty, "Ya existe una especialidad con este nombre")
    # Solo al crear: precio por docena de la tarifa base de la etapa (se crea junto con ella).
    # Después se edita desde Tarifas; aquí se ignora al actualizar.
    base_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, write_only=True, required=False
    )

    class Meta:
        model = Specialty
        fields = '__all__'

    def validate_excludes(self, value):
        # Una etapa no puede excluirse a sí misma
        if self.instance and any(s.pk == self.instance.pk for s in value):
            raise serializers.ValidationError('Una etapa no puede excluirse a sí misma.')
        return value
    
    def validate(self, attrs):
        if self.instance is None and attrs.get('base_price') is None:
            raise serializers.ValidationError(
                {'base_price': 'Indica el precio base de la etapa (por docena).'}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        base_price = validated_data.pop('base_price')
        specialty = super().create(validated_data)
        # Tarifa base: sin ninguna condición, aplica a cualquier docena de la etapa.
        # Es la red de seguridad: siempre hay un precio aunque ninguna otra regla aplique.
        SpecialtyRate.objects.create(specialty=specialty, price=base_price)
        return specialty

    def update(self, instance, validated_data):
        validated_data.pop('base_price', None)
        return super().update(instance, validated_data)


# --- Extras de tarifa por trabajador (payroll.WorkerRateExtra) ---------------

class WorkerRateExtraSerializer(serializers.ModelSerializer):
    """Lectura: lo que se muestra dentro del trabajador."""

    class Meta:
        model = WorkerRateExtra
        fields = ["id", "specialty", "extra_price"]


class WorkerRateExtraInputSerializer(serializers.Serializer):
    """Escritura: {"specialty": 5, "extra_price": "1.00"}. Puede ser negativo."""

    specialty = serializers.PrimaryKeyRelatedField(queryset=Specialty.objects.all())
    extra_price = serializers.DecimalField(max_digits=10, decimal_places=2)


class WorkerSerializer(serializers.ModelSerializer):
    specialties = SpecialtySerializer(many=True, read_only=True)
    specialties_ids = serializers.PrimaryKeyRelatedField(
        source="specialties",
        queryset=Specialty.objects.all(),
        many=True,
        required=False,
        write_only=True,
    )
    dni = unique_char_field(Worker, "Ya existe un trabajador con este número de documento")
    email = serializers.EmailField(
        required=False,
        allow_blank=True,
        allow_null=True,
        validators=[unique_iexact(Worker, "Ya existe un trabajador con este email")],
    )
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
    )

    # Lectura: cuánto se le debe hoy (trabajo sin pagar +/- ajustes pendientes).
    # Viene calculado en la consulta de la lista; en crear/editar no se calcula (null).
    pending_amount = serializers.SerializerMethodField()
    # Lectura: si ya tiene PIN para el portal (el PIN en sí nunca se envía)
    has_pin = serializers.SerializerMethodField()

    # Lectura: extras que tiene el trabajador, uno por especialidad
    rate_extras = WorkerRateExtraSerializer(many=True, read_only=True)
    # Escritura: lista COMPLETA de extras deseados. Si no se envía, no se tocan.
    # Un extra en 0 equivale a no tener extra (se elimina).
    specialty_extras = WorkerRateExtraInputSerializer(
        many=True, write_only=True, required=False
    )

    class Meta:
        model = Worker
        fields = [
            "id",
            "specialties",
            "specialties_ids",
            "rate_extras",
            "specialty_extras",
            "names",
            "dni",
            "phone",
            "address",
            "email",
            "password",
            "pending_amount",
            "has_pin",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_pending_amount(self, obj):
        work = getattr(obj, "pending_work", None)
        if work is None:
            return None
        return str(work + obj.pending_adjustments_total)

    def get_has_pin(self, obj):
        return bool(obj.password)

    def validate_email(self, value):
        return value or None  # "" -> NULL

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["email"] = data.get("email") or ""  # el frontend sigue recibiendo "" si no hay correo
        return data

    def validate(self, attrs):
        extras = attrs.get("specialty_extras")
        if extras is None:
            return attrs

        # Especialidades finales del trabajador: las enviadas, o las actuales al editar
        if "specialties" in attrs:
            allowed = {s.id for s in attrs["specialties"]}
        elif self.instance:
            allowed = set(self.instance.specialties.values_list("id", flat=True))
        else:
            allowed = set()

        seen = set()
        for item in extras:
            spec = item["specialty"]
            if spec.id in seen:
                raise serializers.ValidationError(
                    {"specialty_extras": f"Especialidad repetida: {spec.name}."}
                )
            seen.add(spec.id)
            if spec.id not in allowed:
                raise serializers.ValidationError(
                    {"specialty_extras": f"El trabajador no tiene la especialidad {spec.name}."}
                )
        return attrs


    @staticmethod
    def _sync_extras(worker, extras):
        """Deja los extras del trabajador acorde a la lista y a sus especialidades."""
        current = set(worker.specialties.values_list("id", flat=True))

        # Los extras de especialidades que ya no tiene no tienen sentido
        worker.rate_extras.exclude(specialty_id__in=current).delete()

        if extras is None:
            return

        keep = {}
        for item in extras:
            if item["extra_price"] != 0:
                keep[item["specialty"].id] = item["extra_price"]

        worker.rate_extras.exclude(specialty_id__in=keep.keys()).delete()
        for specialty_id, price in keep.items():
            WorkerRateExtra.objects.update_or_create(
                worker=worker,
                specialty_id=specialty_id,
                defaults={"extra_price": price},
            )

    def create(self, validated_data):
        extras = validated_data.pop("specialty_extras", None)
        password = validated_data.pop("password", "")
        validated_data["password"] = make_password(password) if password else ""

        with transaction.atomic():
            worker = super().create(validated_data)
            self._sync_extras(worker, extras)
        return worker

    def update(self, instance, validated_data):
        extras = validated_data.pop("specialty_extras", None)
        password = validated_data.pop("password", None)
        if password:  # solo si mandaron una contraseña nueva y no vacía
            instance.password = make_password(password)
        # si no mandaron password o vino vacía, no tocamos el valor existente

        with transaction.atomic():
            instance = super().update(instance, validated_data)
            self._sync_extras(instance, extras)
        return instance