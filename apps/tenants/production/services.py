"""Lógica de negocio de producción: códigos, resolución de precios y asignación masiva.

Las reglas viven aquí y no en los modelos ni en las vistas, para que el diálogo
(vista previa) y el guardado usen EXACTAMENTE el mismo cálculo.
"""
import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models.functions import Length
from rest_framework.exceptions import ValidationError

from apps.tenants.payroll.models import SpecialtyRate, WorkerRateExtra
from apps.tenants.staff.models import Specialty, Worker

from .models import Dozen, DozenStageAssignment

TWELVE = Decimal(12)
CENT = Decimal("0.01")


# --------------------------------------------------------------------------
# Códigos
# --------------------------------------------------------------------------

def generate_dozen_code(model):
    """Siguiente código del modelo: AM-0001, AM-0002... (`model` = catalog.Model)."""
    prefix = model.code_prefix.upper()

    # Se ordena por longitud y luego por texto para que AM-10000 > AM-9999
    last = (
        Dozen.objects.filter(code__startswith=f"{prefix}-")
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

    return f"{prefix}-{sequence:04d}"


def generate_registration_group():
    return f"BATCH-{uuid.uuid4().hex[:8].upper()}"


# --------------------------------------------------------------------------
# Precios
# --------------------------------------------------------------------------

def load_rates(specialty_ids):
    """{specialty_id: [reglas]} con una sola consulta."""
    rates = {}
    for rate in SpecialtyRate.objects.filter(specialty_id__in=specialty_ids):
        rates.setdefault(rate.specialty_id, []).append(rate)
    return rates


def load_extras(specialty_ids, worker_ids=None):
    """{(worker_id, specialty_id): extra_price} con una sola consulta."""
    qs = WorkerRateExtra.objects.filter(specialty_id__in=specialty_ids)
    if worker_ids is not None:
        qs = qs.filter(worker_id__in=worker_ids)
    return {(e.worker_id, e.specialty_id): e.extra_price for e in qs}


def find_base_rate(rules, dozen):
    """Regla más específica que cumpla la docena, o None si no hay ninguna.

    Una regla aplica si cada condición definida coincide con la docena.
    Gana la que tiene más condiciones; en empate: material_type > plant_type > size > model.
    """
    best, best_key = None, None
    for rule in rules:
        if rule.model_id is not None and rule.model_id != dozen.model_id:
            continue
        if rule.size_id is not None and rule.size_id != dozen.size_id:
            continue
        if rule.material_type_id is not None and rule.material_type_id != dozen.material_type_id:
            continue
        if rule.plant_type_id is not None and rule.plant_type_id != dozen.plant_type_id:
            continue

        """ Para cambiar el orden solo reordenar esas cuatro líneas. Por ejemplo,
         si quisiera que la talla pese más que el material, solo cambio el orden"""
        key = (
            rule.specificity,
            rule.material_type_id is not None,
            rule.plant_type_id is not None,
            rule.size_id is not None,
            rule.model_id is not None,
        )
        if best_key is None or key > best_key:
            best, best_key = rule, key
    return best


def calculate_amount(unit_price, pairs):
    """Pago por la docena (o fracción): unit_price x pairs / 12."""
    return (unit_price * Decimal(pairs) / TWELVE).quantize(CENT, rounding=ROUND_HALF_UP)


# --------------------------------------------------------------------------
# Etapas excluyentes (ej. "Armado completo" vs "Armador" + "Pegador")
# --------------------------------------------------------------------------

def load_exclusions():
    """{specialty_id: {ids que no se usan junto con ella}} con una sola consulta."""
    mapping = {}
    for a, b in Specialty.excludes.through.objects.values_list("from_specialty_id", "to_specialty_id"):
        mapping.setdefault(a, set()).add(b)
        mapping.setdefault(b, set()).add(a)  # simétrico aunque falte una de las dos filas
    return mapping


def stage_progress(active_ids, exclusions, assigned_ids):
    """Avance de una docena con etapas excluyentes.

    - Una etapa queda "no aplica" si alguna etapa excluyente suya ya está asignada.
    - Un grupo de etapas excluyentes sin ninguna asignada cuenta como UNA sola etapa
      pendiente (hay que elegir una de las dos formas de hacerlo).
    Devuelve {total, assigned, not_applicable (ids), unresolved (bool)}.
    """
    active = set(active_ids)
    assigned = set(assigned_ids) & active

    # Grupos: etapas activas unidas por exclusiones
    parent = {i: i for i in active}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a in active:
        for b in exclusions.get(a, ()):
            if b in active:
                parent[find(a)] = find(b)

    groups = {}
    for i in active:
        groups.setdefault(find(i), set()).add(i)

    not_applicable = {i for i in active if exclusions.get(i, set()) & assigned}

    total = 0
    unresolved = False
    for members in groups.values():
        if len(members) == 1 or members & assigned:
            total += len(members - not_applicable)
        else:
            total += 1  # elegir cuál de las formas se usa
            unresolved = True
    return {
        "total": total,
        "assigned": len(assigned),
        "not_applicable": not_applicable,
        "unresolved": unresolved,
    }


def stage_groups(active_ids, exclusions):
    """{specialty_id: frozenset(ids del grupo)}: etapas unidas por exclusiones (solo activas)."""
    active = set(active_ids)
    parent = {i: i for i in active}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a in active:
        for b in exclusions.get(a, ()):
            if b in active:
                parent[find(a)] = find(b)
    members = {}
    for i in active:
        members.setdefault(find(i), set()).add(i)
    return {i: frozenset(members[find(i)]) for i in active}


def is_fully_assigned(progress):
    return progress["total"] > 0 and progress["assigned"] >= progress["total"]


# --------------------------------------------------------------------------
# Diálogo de asignación masiva
# --------------------------------------------------------------------------

def get_stage_options(dozen):
    """Datos para pintar el diálogo: una fila por etapa activa, en orden de proceso.

    Cada fila trae el precio base, los trabajadores que SÍ tienen esa especialidad
    (filtro estricto) con su extra y el precio final, o la asignación ya hecha.
    """
    specialties = list(Specialty.objects.filter(is_active=True))
    specialty_ids = [s.id for s in specialties]

    rates = load_rates(specialty_ids)
    extras = load_extras(specialty_ids)

    workers_by_specialty = {}
    through = Worker.specialties.through.objects.filter(
        specialty_id__in=specialty_ids, worker__is_active=True
    ).select_related("worker").order_by("worker__names")
    for link in through:
        workers_by_specialty.setdefault(link.specialty_id, []).append(link.worker)

    assigned = {
        a.specialty_id: a
        for a in dozen.assignments.select_related("worker")
    }

    exclusions = load_exclusions()
    progress = stage_progress(specialty_ids, exclusions, assigned.keys())

    rows = []
    for specialty in specialties:
        rule = find_base_rate(rates.get(specialty.id, []), dozen)
        base = rule.price if rule else None

        workers = []
        for worker in workers_by_specialty.get(specialty.id, []):
            extra = extras.get((worker.id, specialty.id), Decimal("0"))
            unit_price = amount = None
            if base is not None:
                unit_price = base + extra
                amount = calculate_amount(unit_price, dozen.pairs)
            workers.append({
                "id": worker.id,
                "names": worker.names,
                "extra_price": extra,
                "unit_price": unit_price,
                "amount": amount,
            })

        current = assigned.get(specialty.id)
        rows.append({
            "specialty": {"id": specialty.id, "name": specialty.name, "order": specialty.order},
            "base_price": base,
            "missing_rate": base is None,
            # Etapas que no se usan junto con esta, y si ya no aplica por lo asignado
            "excludes": sorted(i for i in exclusions.get(specialty.id, ()) if i in specialty_ids),
            "not_applicable": specialty.id in progress["not_applicable"] and specialty.id not in assigned,
            "workers": workers,
            "assignment": None if current is None else {
                "id": current.id,
                "worker": {"id": current.worker_id, "names": current.worker.names},
                "delivered_at": current.delivered_at,
                "completed_at": current.completed_at,
                "unit_price": current.unit_price,
                "amount": current.amount,
                "is_paid": current.settlement_id is not None,
            },
        })
    return rows


@transaction.atomic
def assign_stages(dozen, rows):
    """Asigna varias etapas de una docena de una sola vez (todo o nada).

    `rows`: lista de dicts con specialty, worker (instancias), delivered_at, completed_at.
    Fija unit_price y amount en cada asignación para que un cambio posterior de
    tarifas no altere lo ya registrado.
    """
    # Bloquea la docena para que dos personas no asignen la misma etapa a la vez
    dozen = Dozen.objects.select_for_update().get(pk=dozen.pk)

    errors = []
    if not dozen.is_active:
        raise ValidationError({"detail": "La docena está inactiva."})
    if dozen.status in (Dozen.Status.REJECTED, Dozen.Status.COMPLETED):
        raise ValidationError(
            {"detail": f"No se pueden asignar etapas a una docena {dozen.get_status_display().lower()}."}
        )

    specialty_ids = [r["specialty"].id for r in rows]
    worker_ids = [r["worker"].id for r in rows]

    already = set(dozen.assignments.values_list("specialty_id", flat=True))
    skills = set(
        Worker.specialties.through.objects
        .filter(worker_id__in=worker_ids, specialty_id__in=specialty_ids)
        .values_list("worker_id", "specialty_id")
    )
    rates = load_rates(specialty_ids)
    extras = load_extras(specialty_ids, worker_ids)

    exclusions = load_exclusions()
    names = {r["specialty"].id: r["specialty"].name for r in rows}
    taken = already | set(specialty_ids)  # lo que ya hay + lo que llega ahora

    seen = set()
    to_create = []
    for row in rows:
        specialty, worker = row["specialty"], row["worker"]
        label = specialty.name

        # No se puede usar junto con una etapa excluyente (ya asignada o en esta misma solicitud)
        clash = (exclusions.get(specialty.id, set()) & taken) - {specialty.id}
        if clash:
            clash_names = ", ".join(
                names.get(i) or Specialty.objects.filter(pk=i).values_list("name", flat=True).first() or str(i)
                for i in sorted(clash)
            )
            errors.append(f"{label}: no se usa junto con {clash_names}.")

        if specialty.id in seen:
            errors.append(f"{label}: está repetida en la solicitud.")
            continue
        seen.add(specialty.id)

        if not specialty.is_active:
            errors.append(f"{label}: no es una etapa activa.")
        if specialty.id in already:
            errors.append(f"{label}: ya tiene asignación en esta docena.")
        if not worker.is_active:
            errors.append(f"{label}: {worker.names} está inactivo.")
        if (worker.id, specialty.id) not in skills:
            errors.append(f"{label}: {worker.names} no tiene esta especialidad.")
        if row["delivered_at"] > row["completed_at"]:
            errors.append(f"{label}: la fecha de entrega no puede ser posterior a la de término.")

        rule = find_base_rate(rates.get(specialty.id, []), dozen)
        if rule is None:
            errors.append(f"{label}: no hay una tarifa configurada para esta docena.")
            continue

        unit_price = rule.price + extras.get((worker.id, specialty.id), Decimal("0"))
        if unit_price < 0:
            errors.append(f"{label}: el precio final de {worker.names} sería negativo.")
            continue

        to_create.append(DozenStageAssignment(
            dozen=dozen,
            specialty=specialty,
            worker=worker,
            status=DozenStageAssignment.Status.COMPLETED,
            delivered_at=row["delivered_at"],
            completed_at=row["completed_at"],
            unit_price=unit_price,
            amount=calculate_amount(unit_price, dozen.pairs),
            description=row.get("description") or None,
        ))

    if errors:
        raise ValidationError({"assignments": errors})

    DozenStageAssignment.objects.bulk_create(to_create)

    # Con todas las etapas activas asignadas, la docena queda completada;
    # si falta alguna (o falta elegir entre etapas excluyentes), queda en proceso.
    active_ids = list(Specialty.objects.filter(is_active=True).values_list("id", flat=True))
    assigned_ids = dozen.assignments.values_list("specialty_id", flat=True)
    progress = stage_progress(active_ids, exclusions, assigned_ids)
    _set_status(dozen, Dozen.Status.COMPLETED if is_fully_assigned(progress) else Dozen.Status.IN_PROGRESS)
    return dozen


@transaction.atomic
def remove_assignment(assignment):
    """Elimina una asignación que aún no se pagó."""
    if assignment.settlement_id:
        raise ValidationError({"detail": "La asignación ya fue pagada y no se puede eliminar."})

    dozen = assignment.dozen
    assignment.delete()

    # Al quitar una etapa, la docena deja de estar completa
    if dozen.status in (Dozen.Status.IN_PROGRESS, Dozen.Status.COMPLETED):
        _set_status(
            dozen,
            Dozen.Status.IN_PROGRESS if dozen.assignments.exists() else Dozen.Status.PENDING,
        )


# --------------------------------------------------------------------------
# Cambios de estado manuales: completar, rechazar y reabrir
# --------------------------------------------------------------------------

def _set_status(dozen, status):
    if dozen.status != status:
        dozen.status = status
        dozen.save(update_fields=["status", "updated_at"])


@transaction.atomic
def complete_dozen(dozen):
    """Marca la docena como completada aunque falten etapas (por ejemplo, si no
    todas aplican a este modelo). Necesita al menos una etapa asignada."""
    dozen = Dozen.objects.select_for_update().get(pk=dozen.pk)
    if dozen.status == Dozen.Status.REJECTED:
        raise ValidationError({"detail": "La docena está rechazada; reábrela primero."})
    if dozen.status == Dozen.Status.COMPLETED:
        raise ValidationError({"detail": "La docena ya está completada."})
    if not dozen.assignments.exists():
        raise ValidationError({"detail": "Asigna al menos una etapa antes de completar la docena."})
    _set_status(dozen, Dozen.Status.COMPLETED)
    return dozen


@transaction.atomic
def reject_dozen(dozen, reason=None):
    """Rechazo por falla grave: ya no admite asignaciones. Las etapas ya registradas
    se siguen pagando. El motivo, si se da, se agrega a la nota de la docena."""
    dozen = Dozen.objects.select_for_update().get(pk=dozen.pk)
    if dozen.status in (Dozen.Status.COMPLETED, Dozen.Status.REJECTED):
        raise ValidationError({"detail": "Solo se puede rechazar una docena pendiente o en proceso."})
    if reason:
        note = f"Rechazada: {reason}"
        dozen.description = f"{dozen.description}\n{note}" if dozen.description else note
        dozen.save(update_fields=["description"])
    _set_status(dozen, Dozen.Status.REJECTED)
    return dozen


@transaction.atomic
def reopen_dozen(dozen):
    """Devuelve una docena completada o rechazada a En proceso (o Pendiente si no tiene etapas)."""
    dozen = Dozen.objects.select_for_update().get(pk=dozen.pk)
    if dozen.status not in (Dozen.Status.COMPLETED, Dozen.Status.REJECTED):
        raise ValidationError({"detail": "La docena no está completada ni rechazada."})
    _set_status(
        dozen,
        Dozen.Status.IN_PROGRESS if dozen.assignments.exists() else Dozen.Status.PENDING,
    )
    return dozen