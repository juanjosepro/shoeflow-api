from django.db.models import Q, ProtectedError
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from apps.common.mixins import OptionalPaginationMixin, ActiveFilterMixin

from .models import Specialty, Worker
from .serializers import SpecialtySerializer, WorkerSerializer


class SpecialtyViewSet(OptionalPaginationMixin, ActiveFilterMixin, viewsets.ModelViewSet):
    queryset = Specialty.objects.all()  # ya viene ordenado por (order, name)
    serializer_class = SpecialtySerializer

    # Una especialidad con etapas ya asignadas en docenas no se puede borrar:
    # responde 400 con un mensaje claro en vez de un error 500.
    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError(
                {"detail": "No se puede eliminar porque ya tiene etapas asignadas en docenas. Puedes desactivarla en su lugar."}
            )


class WorkerViewSet(OptionalPaginationMixin, ActiveFilterMixin, viewsets.ModelViewSet):
    queryset = Worker.objects.prefetch_related("specialties", "rate_extras")
    serializer_class = WorkerSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        # ?specialty=5 -> solo trabajadores que tienen esa especialidad
        # (filtro estricto de la asignación masiva)
        specialty = params.get("specialty")
        if specialty and specialty.isdigit():
            qs = qs.filter(specialties__id=int(specialty))

        search = params.get("search")
        if search:
            qs = qs.filter(
                Q(names__icontains=search)
                | Q(dni__icontains=search)
                | Q(phone__icontains=search)
                | Q(specialties__name__icontains=search)
            )

        # distinct porque specialties es many-to-many y duplicaría filas
        return qs.distinct()