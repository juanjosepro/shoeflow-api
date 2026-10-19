from django.db.models import Prefetch, Q
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.mixins import OptionalPaginationMixin

from . import services
from .models import Dozen, DozenStageAssignment
from .pagination import ProductionPagination
from .serializers import (
    AssignStagesSerializer,
    DozenSerializer,
    DozenStageAssignmentSerializer,
)


class DozenViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    queryset = (
        Dozen.objects
        .select_related("model__category", "size", "material_type", "color", "plant_type")
        .prefetch_related(
            Prefetch(
                "assignments",
                queryset=DozenStageAssignment.objects.select_related("specialty", "worker"),
            )
        )
    )
    serializer_class = DozenSerializer
    pagination_class = ProductionPagination

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        search = params.get("search")
        if search:
            qs = qs.filter(
                Q(code__icontains=search)
                | Q(description__icontains=search)
                | Q(model__name__icontains=search)
            )

        # Filtros exactos: ?model=1&size=2&status=...&material_type=...
        for param, lookup in (
            ("model", "model_id"),
            ("size", "size_id"),
            ("status", "status"),
            ("material_type", "material_type_id"),
            ("color", "color_id"),
            ("plant_type", "plant_type_id"),
            ("priority", "priority"),
        ):
            value = params.get(param)
            if value:
                qs = qs.filter(**{lookup: value})

        if params.get("exclude_finished") == "true":
            qs = qs.exclude(status__in=[Dozen.Status.COMPLETED, Dozen.Status.REJECTED])

        return qs.order_by("-created_at", "-id")

    def perform_destroy(self, instance):
        # Borrar la docena borraría sus asignaciones: no si alguna ya se pagó
        if instance.assignments.filter(settlement__isnull=False).exists():
            raise ValidationError({"detail": "La docena tiene etapas ya pagadas y no se puede eliminar."})
        instance.delete()

    # GET /dozens/{id}/stage-options/ -> datos para pintar el diálogo de asignación
    @action(detail=True, methods=["get"], url_path="stage-options")
    def stage_options(self, request, pk=None):
        dozen = self.get_object()
        return Response(services.get_stage_options(dozen))

    def _detail_response(self, pk):
        """La docena actualizada, con sus asignaciones."""
        return Response(self.get_serializer(self.get_queryset().get(pk=pk)).data)

    # POST /dozens/{id}/assign-stages/ -> guarda varias etapas de una vez (todo o nada)
    @action(detail=True, methods=["post"], url_path="assign-stages")
    def assign_stages(self, request, pk=None):
        dozen = self.get_object()
        serializer = AssignStagesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        services.assign_stages(dozen, serializer.validated_data["assignments"])
        return self._detail_response(dozen.pk)

    # POST /dozens/{id}/complete/ | /reject/ | /reopen/ -> cambios de estado manuales
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        services.complete_dozen(self.get_object())
        return self._detail_response(pk)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        services.reject_dozen(self.get_object(), reason=request.data.get("reason"))
        return self._detail_response(pk)

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        services.reopen_dozen(self.get_object())
        return self._detail_response(pk)


class DozenStageAssignmentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Consulta y eliminación (si no está pagada). Crear = assign-stages en DozenViewSet."""

    queryset = DozenStageAssignment.objects.select_related("dozen", "specialty", "worker")
    serializer_class = DozenStageAssignmentSerializer
    pagination_class = None  # Desactiva la paginación global solo aquí

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        for param, lookup in (
            ("dozen", "dozen_id"),
            ("worker", "worker_id"),
            ("specialty", "specialty_id"),
            ("status", "status"),
            ("completed_from", "completed_at__gte"),
            ("completed_to", "completed_at__lte"),
        ):
            value = params.get(param)
            if value:
                qs = qs.filter(**{lookup: value})

        # ?unpaid=true -> pendientes de pago (sin liquidación)
        if params.get("unpaid") == "true":
            qs = qs.filter(settlement__isnull=True)

        return qs

    def perform_destroy(self, instance):
        services.remove_assignment(instance)


class DozenMetadataView(APIView):
    def get(self, request):
        # Solo las opciones fijas (estados y prioridades). Materiales, colores y plantas
        # ahora son tablas: /materials/, /colors/ y /plant-types/.
        def format_choices(choices_class):
            return [{"key": member.value, "label": member.label} for member in choices_class]

        data = {
            'statuses': format_choices(Dozen.Status),
            'priorities': format_choices(Dozen.Priority),
            'assignment_statuses': format_choices(DozenStageAssignment.Status),
        }
        return Response(data)