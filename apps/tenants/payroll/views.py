from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.common.mixins import OptionalPaginationMixin
from apps.tenants.production.serializers import DozenStageAssignmentSerializer

from . import services
from .models import PaymentSettlement, SettlementAdjustment, SpecialtyRate, WorkerRateExtra
from .serializers import (
    PaymentSettlementDetailSerializer,
    PaymentSettlementSerializer,
    SettlementAdjustmentSerializer,
    SettlementCreateSerializer,
    SettlementRangeSerializer,
    SpecialtyRateSerializer,
    WorkerParamSerializer,
    WorkerRateExtraSerializer,
)


def _filter_by_params(qs, params, mapping):
    """Aplica filtros exactos: mapping = {nombre_del_parametro: campo_del_modelo}."""
    for param, lookup in mapping.items():
        value = params.get(param)
        if value:
            qs = qs.filter(**{lookup: value})
    return qs


class SpecialtyRateViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    """Reglas de tarifa. ?specialty=&model=&size=&material_type=&plant_type="""

    queryset = SpecialtyRate.objects.select_related("specialty", "model", "size", "material_type", "plant_type")
    serializer_class = SpecialtyRateSerializer

    def get_queryset(self):
        return _filter_by_params(
            super().get_queryset(),
            self.request.query_params,
            {
                "specialty": "specialty_id",
                "model": "model_id",
                "size": "size_id",
                "material_type": "material_type_id",
                "plant_type": "plant_type_id",
            },
        )


class WorkerRateExtraViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    """Extra de tarifa por trabajador y especialidad. ?worker=&specialty="""

    queryset = WorkerRateExtra.objects.select_related("worker", "specialty")
    serializer_class = WorkerRateExtraSerializer

    def get_queryset(self):
        return _filter_by_params(
            super().get_queryset(),
            self.request.query_params,
            {"worker": "worker_id", "specialty": "specialty_id"},
        )


class SettlementAdjustmentViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    """Bonos, descuentos, adelantos y saldos. ?worker=&type=&settlement=&pending=true"""

    queryset = SettlementAdjustment.objects.select_related("worker")
    serializer_class = SettlementAdjustmentSerializer

    def get_queryset(self):
        qs = _filter_by_params(
            super().get_queryset(),
            self.request.query_params,
            {"worker": "worker_id", "type": "type", "settlement": "settlement_id"},
        )
        if self.request.query_params.get("pending") == "true":
            qs = qs.filter(settlement__isnull=True)
        return qs

    # Un ajuste ya aplicado a un pago es historia: no se edita ni se borra
    def perform_update(self, serializer):
        if serializer.instance.settlement_id:
            raise ValidationError({"detail": "Este ajuste ya fue aplicado a un pago y no se puede modificar."})
        serializer.save()

    def perform_destroy(self, instance):
        if instance.settlement_id:
            raise ValidationError({"detail": "Este ajuste ya fue aplicado a un pago y no se puede eliminar."})
        instance.delete()


class PaymentSettlementViewSet(
    OptionalPaginationMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Pagos semanales. Se consultan aquí; se crean con POST (create) tras ver /preview/."""

    queryset = PaymentSettlement.objects.select_related("worker")
    serializer_class = PaymentSettlementSerializer

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PaymentSettlementDetailSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        qs = _filter_by_params(qs, params, {
            "worker": "worker_id",
            "date_from": "start_date__gte",
            "date_to": "end_date__lte",
        })
        # ?with_balance=true -> pagos que dejaron deuda
        if params.get("with_balance") == "true":
            qs = qs.filter(pending_balance__gt=0)

        if self.action == "retrieve":
            qs = qs.prefetch_related("adjustments__worker", "items__dozen", "items__specialty", "items__worker")
        return qs

    # GET /payments/preview/?worker=1&start_date=2026-10-05&end_date=2026-10-10
    @action(detail=False, methods=["get"])
    def preview(self, request):
        params = SettlementRangeSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        worker = params.validated_data["worker"]

        items, adjustments, totals = services.preview_settlement(
            worker, params.validated_data["start_date"], params.validated_data["end_date"]
        )
        return Response({
            "worker": {"id": worker.id, "names": worker.names},
            "start_date": params.validated_data["start_date"],
            "end_date": params.validated_data["end_date"],
            "items": DozenStageAssignmentSerializer(items, many=True).data,
            "adjustments": SettlementAdjustmentSerializer(adjustments, many=True).data,
            **totals,
        })

    # GET /payments/pending-weeks/?worker=1  -> semanas (lun-dom) con etapas sin pagar
    @action(detail=False, methods=["get"], url_path="pending-weeks")
    def pending_weeks(self, request):
        params = WorkerParamSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        return Response(services.pending_weeks(params.validated_data["worker"]))

    # POST /payments/  {worker, start_date, end_date, assignment_ids?, amount_paid?, description}
    def create(self, request):
        data = SettlementCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data

        settlement = services.create_settlement(
            worker=v["worker"],
            start_date=v["start_date"],
            end_date=v["end_date"],
            amount_paid=v.get("amount_paid"),
            description=v.get("description") or None,
            assignment_ids=v.get("assignment_ids"),
        )
        settlement = PaymentSettlement.objects.select_related("worker").prefetch_related(
            "adjustments__worker", "items__dozen", "items__specialty", "items__worker"
        ).get(pk=settlement.pk)
        return Response(PaymentSettlementDetailSerializer(settlement).data, status=status.HTTP_201_CREATED)