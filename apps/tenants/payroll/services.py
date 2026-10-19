"""Lógica del pago semanal: qué entra en una liquidación y cómo se cierra."""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.tenants.production.models import DozenStageAssignment

from .models import PaymentSettlement, SettlementAdjustment, SpecialtyRate

ZERO = Decimal("0")


def pending_assignments(worker, start_date, end_date):
    """Etapas terminadas del trabajador, de esa semana, que aún no se pagaron."""
    return DozenStageAssignment.objects.filter(
        worker=worker,
        status=DozenStageAssignment.Status.COMPLETED,
        settlement__isnull=True,
        completed_at__range=(start_date, end_date),
    )


def pending_weeks(worker):
    """Semanas (lunes a domingo) en las que el trabajador tiene etapas terminadas sin pagar.
    La misma semana que usa DozenStageAssignment.week_identifier. Las más recientes primero."""
    weeks = {}
    rows = pending_assignments_all(worker).values_list("completed_at", "amount")
    for completed_at, amount in rows:
        monday = completed_at - timedelta(days=completed_at.weekday())
        week = weeks.setdefault(monday, {"count": 0, "amount": ZERO})
        week["count"] += 1
        week["amount"] += amount

    return [
        {
            "start_date": monday,
            "end_date": monday + timedelta(days=6),
            "count": data["count"],
            "amount": data["amount"],
        }
        for monday, data in sorted(weeks.items(), reverse=True)
    ]


def pending_assignments_all(worker):
    """Todas las etapas terminadas del trabajador que aún no se pagaron (sin límite de fechas)."""
    return DozenStageAssignment.objects.filter(
        worker=worker,
        status=DozenStageAssignment.Status.COMPLETED,
        settlement__isnull=True,
    )


def pending_adjustments(worker):
    """Bonos, descuentos, adelantos y saldos del trabajador que aún no se aplicaron.
    Entran todos los pendientes, sin importar la fecha en que se crearon."""
    return SettlementAdjustment.objects.filter(worker=worker, settlement__isnull=True)


def calculate_totals(items, adjustments):
    total_earned = sum((i.amount for i in items), ZERO)
    total_adjustments = sum((a.signed_amount for a in adjustments), ZERO)
    return {
        "total_earned": total_earned,
        "total_adjustments": total_adjustments,
        "total_to_pay": total_earned + total_adjustments,
    }


def preview_settlement(worker, start_date, end_date):
    """Qué se pagaría hoy (no guarda nada)."""
    items = list(
        pending_assignments(worker, start_date, end_date)
        .select_related("dozen", "specialty", "worker")
        .order_by("completed_at", "dozen__code", "specialty__order")
    )
    adjustments = list(pending_adjustments(worker).select_related("worker").order_by("created_at"))
    return items, adjustments, calculate_totals(items, adjustments)


@transaction.atomic
def create_settlement(worker, start_date, end_date, amount_paid=None, description=None, assignment_ids=None):
    """Cierra un pago: ata las etapas elegidas y los ajustes pendientes a la liquidación.

    assignment_ids: etapas a pagar. None = todas las pendientes del rango.
    Si se paga solo una parte de las etapas, se entrega exactamente el total (no se puede
    cambiar el monto); las etapas no elegidas siguen pendientes.
    amount_paid: None = el total a pagar.

    total_to_pay = total_earned + total_adjustments
    pending_balance = total_to_pay - amount_paid
    Si queda saldo pendiente, se crea un ajuste SALDO que se cobrará en el próximo pago.
    """
    # select_for_update: evita que dos pagos simultáneos tomen las mismas filas
    pending = list(pending_assignments(worker, start_date, end_date).select_for_update())

    if assignment_ids is None:
        items = pending
    else:
        chosen = set(assignment_ids)
        items = [i for i in pending if i.pk in chosen]
        if len(items) != len(chosen):
            raise ValidationError(
                {"detail": "Alguna etapa elegida ya fue pagada o no pertenece a este trabajador y periodo."}
            )
    is_partial = len(items) < len(pending)

    adjustments = list(pending_adjustments(worker).select_for_update())

    if not items and not adjustments:
        raise ValidationError({"detail": "No hay nada pendiente de pago para ese periodo."})

    totals = calculate_totals(items, adjustments)
    total_to_pay = totals["total_to_pay"]

    if total_to_pay < 0:
        raise ValidationError(
            {"detail": "Los descuentos superan lo ganado; revisa los ajustes pendientes del trabajador."}
        )
    if amount_paid is None:
        amount_paid = total_to_pay
    if is_partial and amount_paid != total_to_pay:
        raise ValidationError(
            {"amount_paid": "Al pagar solo algunas etapas se entrega el total exacto; no se puede cambiar el monto."}
        )
    if amount_paid > total_to_pay:
        raise ValidationError({"amount_paid": f"No puede ser mayor al total a pagar ({total_to_pay})."})

    pending_balance = total_to_pay - amount_paid

    settlement = PaymentSettlement.objects.create(
        worker=worker,
        start_date=start_date,
        end_date=end_date,
        amount_paid=amount_paid,
        pending_balance=pending_balance,
        description=description,
        **totals,
    )

    DozenStageAssignment.objects.filter(pk__in=[i.pk for i in items]).update(settlement=settlement)
    SettlementAdjustment.objects.filter(pk__in=[a.pk for a in adjustments]).update(settlement=settlement)

    if pending_balance > 0:
        # Queda en pendiente: se suma en la próxima liquidación del trabajador
        SettlementAdjustment.objects.create(
            worker=worker,
            type=SettlementAdjustment.Type.CARRYOVER,
            amount=pending_balance,
            reason=f"Saldo pendiente del pago {start_date:%d/%m/%Y} al {end_date:%d/%m/%Y}",
        )

    return settlement


# --------------------------------------------------------------------------
# Precios por talla de un modelo (formulario del modelo)
# --------------------------------------------------------------------------

def get_model_size_rates(model):
    """Reglas simples de un modelo: solo modelo + talla + especialidad.
    Las reglas con material o planta se administran aparte, en /rates/."""
    return SpecialtyRate.objects.filter(
        model=model,
        size__isnull=False,
        material_type__isnull=True,
        plant_type__isnull=True,
    )


@transaction.atomic
def sync_model_size_rates(model, rows):
    """Guarda los precios por especialidad y talla de un modelo.

    `rows`: lista de dicts {specialty, size, price} (instancias de Specialty y Size).
      - price con valor -> crea o actualiza la regla
      - price None      -> borra la regla si existía (esa talla vuelve a la tarifa general)
    Las combinaciones que no vienen en la lista no se tocan.
    """
    errors = []
    seen = set()
    wanted = {}      # (specialty_id, size_id) -> price
    to_delete = set()

    for row in rows:
        specialty, size, price = row["specialty"], row["size"], row["price"]
        key = (specialty.id, size.id)

        if key in seen:
            errors.append(f"{specialty.name} / {size.name}: está repetida.")
            continue
        seen.add(key)

        if price is None:
            to_delete.add(key)
        elif not specialty.is_active:
            errors.append(f"{specialty.name}: no es una etapa activa.")
        else:
            wanted[key] = price

    if errors:
        raise ValidationError({"size_rates": errors})

    existing = {(r.specialty_id, r.size_id): r for r in get_model_size_rates(model)}

    # 1. Borrar las que quedaron sin precio
    ids_to_delete = [existing[key].pk for key in to_delete if key in existing]
    SpecialtyRate.objects.filter(pk__in=ids_to_delete).delete()

    # 2. Actualizar las que cambiaron y crear las nuevas
    to_update, to_create = [], []
    for (specialty_id, size_id), price in wanted.items():
        rate = existing.get((specialty_id, size_id))
        if rate is None:
            to_create.append(
                SpecialtyRate(model=model, specialty_id=specialty_id, size_id=size_id, price=price)
            )
        elif rate.price != price:
            rate.price = price
            rate.updated_at = timezone.now()  # bulk_update no llena auto_now
            to_update.append(rate)

    SpecialtyRate.objects.bulk_update(to_update, ["price", "updated_at"])
    SpecialtyRate.objects.bulk_create(to_create)