from django.contrib.auth.hashers import make_password
from django.db import transaction
from rest_framework import serializers

from apps.tenants.payroll.models import WorkerRateExtra

from .models import Specialty, Worker


class SpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = '__all__'


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
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
    )

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
            "is_active",
            "created_at",
            "updated_at",
        ]

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