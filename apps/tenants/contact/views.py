from django.db.models import Count, Max, Prefetch, Q  # [PED] CAMBIO: + Count, Max
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from . import services
from .models import Customer, CustomerOrder
from apps.common.mixins import OptionalPaginationMixin
from apps.tenants.production.models import Dozen, DozenStageAssignment
from apps.tenants.production.pagination import ProductionPagination
from .serializers import (
    AddDozensSerializer,
    CustomerSerializer,
    OrderDetailSerializer,
    OrderSerializer,
    OrderWriteSerializer,
)

class CustomerViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    """Clientes. No se borran si tienen pedidos o docenas: se desactivan."""

    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    pagination_class = ProductionPagination

    def get_queryset(self):
        # Pedidos del cliente (total y abiertos) en una sola consulta
        open_q = Q(orders__closure__isnull=True)
        qs = Customer.objects.annotate(
            orders_count=Count("orders", distinct=True),
            open_orders_count=Count("orders", filter=open_q, distinct=True),
            last_order_at=Max("orders__ordered_at"),
        )
        params = self.request.query_params

        search = params.get("search")
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(document__icontains=search)
                | Q(phone__icontains=search) | Q(email__icontains=search)
            )
        is_active = params.get("is_active")
        if is_active in ("true", "false"):
            qs = qs.filter(is_active=(is_active == "true"))
        return qs.order_by("name", "id")

    def _refetch(self, pk):
        return Response(self.get_serializer(self.get_queryset().get(pk=pk)).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = serializer.save()
        response = self._refetch(customer.pk)
        response.status_code = 201
        return response

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        customer = serializer.save()
        return self._refetch(customer.pk)

    def perform_destroy(self, instance):
        if instance.orders.exists() or instance.dozens.exists():
            raise ValidationError({"detail": "El cliente tiene pedidos o docenas. Desactívalo en lugar de eliminarlo."})
        instance.delete()


class OrderViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    """Pedidos. El estado se calcula (services.annotate_orders); la creación expande las líneas en docenas."""

    queryset = CustomerOrder.objects.all()
    pagination_class = ProductionPagination

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return OrderWriteSerializer
        if self.action == "retrieve":
            return OrderDetailSerializer
        if self.action == "add_dozens":
            return AddDozensSerializer
        return OrderSerializer

    def get_queryset(self):
        qs = services.annotate_orders(CustomerOrder.objects.select_related("customer"))
        if self.action in ("retrieve", "create", "update", "partial_update", "add_dozens", "deliver", "cancel", "reopen"):
            # El detalle incluye sus docenas con asignaciones
            qs = qs.prefetch_related(
                Prefetch(
                    "dozens",
                    queryset=Dozen.objects.select_related(
                        "model__category", "size", "material_type", "color", "plant_type", "customer", "customer_order"
                    )
                    .prefetch_related(
                        Prefetch("assignments", queryset=DozenStageAssignment.objects.select_related("specialty", "worker"))
                    )
                    .order_by("code"),
                )
            )
        params = self.request.query_params

        search = params.get("search")
        if search:
            qs = qs.filter(
                Q(code__icontains=search) | Q(customer__name__icontains=search)
                | Q(customer__document__icontains=search) | Q(notes__icontains=search)
            )
        for param, lookup in (("customer", "customer_id"), ("priority", "priority"), ("status", "status")):
            value = params.get(param)
            if value:
                qs = qs.filter(**{lookup: value})
        # ?open=true -> solo los no cerrados (pendiente, en producción, listo)
        if params.get("open") == "true":
            qs = qs.filter(closure__isnull=True)
        # ?closed=true -> solo entregados y cancelados
        if params.get("closed") == "true":
            qs = qs.filter(closure__isnull=False)
        return qs.order_by("-created_at", "-id")

    def _detail_response(self, pk, status_code=200):
        data = OrderDetailSerializer(self.get_queryset().get(pk=pk), context=self.get_serializer_context()).data
        return Response(data, status=status_code)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = services.create_order(dict(serializer.validated_data))
        return self._detail_response(order.pk, 201)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        order = self.get_object()
        serializer = self.get_serializer(order, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data.pop("lines", None)  # las líneas se agregan con add-dozens
        services.update_order(order, data)
        return self._detail_response(order.pk)

    def perform_destroy(self, instance):
        services.delete_order(instance)

    # POST /orders/{id}/add-dozens/  {lines: [...]}
    @action(detail=True, methods=["post"], url_path="add-dozens")
    def add_dozens(self, request, pk=None):
        order = self.get_object()
        serializer = AddDozensSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.add_dozens(order, serializer.validated_data["lines"])
        return self._detail_response(order.pk)

    # POST /orders/{id}/deliver/ | /cancel/ | /reopen/
    @action(detail=True, methods=["post"])
    def deliver(self, request, pk=None):
        services.deliver_order(self.get_object())
        return self._detail_response(pk)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        services.cancel_order(self.get_object())
        return self._detail_response(pk)

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        services.reopen_order(self.get_object())
        return self._detail_response(pk)