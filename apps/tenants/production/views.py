from apps.tenants.staff.models import Worker
from rest_framework import viewsets
from rest_framework.decorators import action
from .models import Dozen, DozenStageAssignment
from .serializers import DozenSerializer, DozenStageAssignmentSerializer
from .pagination import ProductionPagination, OptionalPaginationMixin
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q
from . import services

class DozenViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    queryset = Dozen.objects.select_related("model_variant__model").prefetch_related("assignments__worker")
    serializer_class = DozenSerializer
    pagination_class = ProductionPagination

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search")
        model = self.request.query_params.get("model")
        status_filter = self.request.query_params.get("status")
        material = self.request.query_params.get("material")
        color = self.request.query_params.get("color")
        exclude_finished = self.request.query_params.get("exclude_finished")

        if search:
            qs = qs.filter(
                Q(code__icontains=search) |
                Q(description__icontains=search) |
                Q(model_variant__model__name__icontains=search)
            )

        if model:
            qs = qs.filter(
                model_variant__model_id=model
            )

        if status_filter:
            qs = qs.filter(status=status_filter)

        if exclude_finished == "true":
            qs = qs.exclude(
                status__in=[
                    Dozen.Status.READY,
                    Dozen.Status.COMPLETED,
                    Dozen.Status.REJECTED,
                ]
            )

        if material:
            qs = qs.filter(material=material)

        if color:
            qs = qs.filter(color=color)

        return qs

class DozenStageAssignmentViewSet(viewsets.ModelViewSet):
    queryset = DozenStageAssignment.objects.select_related("dozen", "worker")
    serializer_class = DozenStageAssignmentSerializer
    pagination_class = None # Desactiva la paginación global solo aquí

    def get_queryset(self):
        qs = super().get_queryset()
        stage = self.request.query_params.get("stage")
        status_filter = self.request.query_params.get("status")
        if stage:
            qs = qs.filter(stage=stage)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    @action(detail=False, methods=["post"])
    def deliver(self, request):
        dozen = Dozen.objects.get(pk=request.data["dozen_id"])
        worker = Worker.objects.get(pk=request.data["worker_id"])
        stage = request.data["stage"]

        assignment = services.deliver_assignment(dozen, stage, worker)
        return Response(
            DozenStageAssignmentSerializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        assignment = self.get_object()
        if assignment.status == DozenStageAssignment.Status.COMPLETED:
            return Response(
                {"detail": "Ya fue completada."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        assignment = services.complete_assignment(assignment)
        return Response(DozenStageAssignmentSerializer(assignment).data)

class DozenMetadataView(APIView):
    def get(self, request):
        # Ahora devuelve un diccionario { 'NOMBRE_CONSTANTE': 'Etiqueta' }
        def format_choices(choices_class):
            return [
                {
                    "key": member.value,
                    "label": member.label
                }
                for member in choices_class
            ]

        data = {
            'statuses': format_choices(Dozen.Status),
            'materials': format_choices(Dozen.Materials),
            'colors': format_choices(Dozen.Colors),
            'assignment_statuses': format_choices(DozenStageAssignment.Status),
        }
        return Response(data)
