# [PED] ARCHIVO NUEVO ─ backend/production/order_services.py
"""Lógica de pedidos: código, estado calculado, creación y cierres.

Mismo criterio que services.py: las reglas viven aquí y no en vistas ni serializers.
"""
from datetime import datetime, time

from django.db import transaction
from django.db.models import Case, Count, F, IntegerField, Q, Sum, Value, When
from django.db.models.functions import Length
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.tenants.production import services
from .models import CustomerOrder
from apps.tenants.production.models import Dozen


# Estados calculados (los dos últimos son el cierre manual guardado en `closure`)
PENDING = "PENDIENTE"  # nada empezado
IN_PRODUCTION = "EN_PRODUCCION"  # al menos una docena empezó
READY = "LISTO"  # todas las docenas completadas, falta entregar
DELIVERED = CustomerOrder.Closure.DELIVERED
CANCELED = CustomerOrder.Closure.CANCELED

OPEN_STATUSES = (PENDING, IN_PRODUCTION, READY)


# --------------------------------------------------------------------------
# Código y estado
# --------------------------------------------------------------------------

def generate_order_code():
    """Siguiente código: PED-0001, PED-0002... También es el registration_group de sus docenas."""
    last = (
        CustomerOrder.objects.filter(code__startswith="PED-")
        .annotate(code_len=Length("code"))
        .order_by("-code_len", "-code")
        .first()
    )
    sequence = 1
    if last:
        try:
            sequence = int(last.code.rsplit("-", 1)[-1]) + 1
        except (ValueError, IndexError):
            sequence = 1
    return f"PED-{sequence:04d}"


def annotate_orders(qs):
    """Agrega el avance y el estado a un queryset de pedidos (una sola consulta).

    - n_total: docenas del pedido sin contar las rechazadas (esas ya no se fabrican)
    - n_done / n_busy: completadas / en proceso
    - status: cierre manual > LISTO > EN_PRODUCCION > PENDIENTE
    """
    D = "dozens"
    qs = qs.annotate(
        n_total=Count(D, filter=~Q(**{f"{D}__status": Dozen.Status.REJECTED})),
        n_done=Count(D, filter=Q(**{f"{D}__status": Dozen.Status.COMPLETED})),
        n_busy=Count(D, filter=Q(**{f"{D}__status": Dozen.Status.IN_PROGRESS})),
        n_rejected=Count(D, filter=Q(**{f"{D}__status": Dozen.Status.REJECTED})),
        pairs_total=Sum(
            f"{D}__pairs", filter=~Q(**{f"{D}__status": Dozen.Status.REJECTED}), output_field=IntegerField()
        ),
    )
    return qs.annotate(
        status=Case(
            When(closure__isnull=False, then=F("closure")),
            When(n_total__gt=0, n_done=F("n_total"), then=Value(READY)),
            When(Q(n_done__gt=0) | Q(n_busy__gt=0), then=Value(IN_PRODUCTION)),
            default=Value(PENDING),
        )
    )


def get_order(pk):
    """Pedido con su estado calculado (para responder tras cada cambio)."""
    return annotate_orders(CustomerOrder.objects.select_related("customer")).get(pk=pk)


# --------------------------------------------------------------------------
# Creación
# --------------------------------------------------------------------------

def order_registered_at(order):
    """registered_at de sus docenas: ahora si el pedido es de hoy; si no, 08:00 de su fecha."""
    today = timezone.localdate()
    if order.ordered_at == today:
        return timezone.now()
    return timezone.make_aware(datetime.combine(order.ordered_at, time(8, 0)))


def _create_dozens(order, lines):
    """Cada línea se expande en `count` docenas, cada una con su propio código (igual que el formulario simple)."""
    registered_at = order_registered_at(order)
    created = []
    for line in lines:
        data = dict(line)
        count = data.pop("count", 1)
        for _ in range(count):
            created.append(
                Dozen.objects.create(
                    **data,
                    code=services.generate_dozen_code(data["model"]),
                    customer=order.customer,
                    customer_order=order,
                    registration_group=order.code,
                    priority=order.priority,
                    registered_at=registered_at,
                )
            )
    return created


@transaction.atomic
def create_order(data):
    """data = campos del pedido + `lines` (lista de líneas ya validadas). Todo o nada."""
    lines = data.pop("lines")
    order = CustomerOrder.objects.create(code=generate_order_code(), **data)
    _create_dozens(order, lines)
    return order


def _ensure_open(order):
    if order.closure:
        raise ValidationError({"detail": f"El pedido está {order.get_closure_display().lower()}. Reábrelo para modificarlo."})


@transaction.atomic
def add_dozens(order, lines):
    """Agrega más líneas a un pedido abierto."""
    _ensure_open(order)
    return _create_dozens(order, lines)


@transaction.atomic
def update_order(order, data):
    """Edita cabecera. Cliente y prioridad se propagan a todas sus docenas."""
    _ensure_open(order)
    for field, value in data.items():
        setattr(order, field, value)
    order.save()
    changes = {}
    if "customer" in data:
        changes["customer"] = order.customer
    if "priority" in data:
        changes["priority"] = order.priority
    if changes:
        order.dozens.update(**changes)
    return order


# --------------------------------------------------------------------------
# Cierres
# --------------------------------------------------------------------------

def _status_of(order):
    return get_order(order.pk).status


@transaction.atomic
def deliver_order(order):
    """Marca como entregado. Solo si todo está fabricado."""
    status = _status_of(order)
    if status != READY:
        raise ValidationError({"detail": "Solo se puede entregar un pedido con todas sus docenas completadas."})
    order.closure = DELIVERED
    order.closed_at = timezone.now()
    order.save(update_fields=["closure", "closed_at", "updated_at"])
    return order


@transaction.atomic
def cancel_order(order):
    """Cancela el pedido. Sus docenas se desactivan (no se borran: pueden tener pagos)."""
    if order.closure == DELIVERED:
        raise ValidationError({"detail": "Un pedido entregado no se puede cancelar."})
    order.closure = CANCELED
    order.closed_at = timezone.now()
    order.save(update_fields=["closure", "closed_at", "updated_at"])
    order.dozens.update(is_active=False)
    return order


@transaction.atomic
def reopen_order(order):
    """Quita el cierre (entregado o cancelado). Si estaba cancelado, reactiva sus docenas."""
    if not order.closure:
        raise ValidationError({"detail": "El pedido ya está abierto."})
    was_canceled = order.closure == CANCELED
    order.closure = None
    order.closed_at = None
    order.save(update_fields=["closure", "closed_at", "updated_at"])
    if was_canceled:
        order.dozens.update(is_active=True)
    return order


@transaction.atomic
def delete_order(order):
    """Borra el pedido y sus docenas, solo si ninguna tiene etapas asignadas."""
    if order.dozens.filter(assignments__isnull=False).exists():
        raise ValidationError(
            {"detail": "Alguna docena del pedido ya tiene etapas asignadas. Cancela el pedido en lugar de borrarlo."}
        )
    order.dozens.all().delete()
    order.delete()
