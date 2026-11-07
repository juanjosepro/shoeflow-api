from decimal import Decimal
from django.db.models import Case, DecimalField, F, OuterRef, ProtectedError, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.common.mixins import OptionalPaginationMixin, ActiveFilterMixin
from apps.tenants.payroll.models import SettlementAdjustment
from apps.tenants.production.models import DozenStageAssignment

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


def _sum_by_worker(qs, expression):
    """Subconsulta: suma por trabajador (0 si no tiene). No usa joins, así que no duplica filas."""
    zero = Value(Decimal("0"), output_field=DecimalField(max_digits=12, decimal_places=2))
    total = qs.filter(worker=OuterRef("pk")).order_by().values("worker").annotate(t=Sum(expression)).values("t")
    return Coalesce(Subquery(total, output_field=DecimalField(max_digits=12, decimal_places=2)), zero)


class WorkerViewSet(OptionalPaginationMixin, ActiveFilterMixin, viewsets.ModelViewSet):
    queryset = Worker.objects.prefetch_related("specialties", "rate_extras")
    serializer_class = WorkerSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        # Lo que se le debe hoy: etapas terminadas sin pagar + ajustes pendientes con su signo
        # (descuentos y adelantos restan). Es el mismo cálculo del pago semanal.
        if self.action in ("list", "retrieve"):
            qs = qs.annotate(
                pending_work=_sum_by_worker(
                    DozenStageAssignment.objects.filter(
                        status=DozenStageAssignment.Status.COMPLETED, settlement__isnull=True
                    ),
                    "amount",
                ),
                pending_adjustments_total=_sum_by_worker(
                    SettlementAdjustment.objects.filter(settlement__isnull=True),
                    Case(
                        When(type__in=SettlementAdjustment.NEGATIVE_TYPES, then=-F("amount")),
                        default=F("amount"),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    ),
                ),
            )

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

    # POST /workers/{id}/set-pin/  {"pin": "1234"} -> PIN de 4 dígitos para el portal del trabajador
    @action(detail=True, methods=["post"], url_path="set-pin")
    def set_pin(self, request, pk=None):
        # Import aquí para no crear un ciclo de imports entre staff y payroll
        from apps.tenants.payroll.portal import set_worker_pin

        worker = self.get_object()
        set_worker_pin(worker, str(request.data.get("pin", "")))
        return Response({"has_pin": True})