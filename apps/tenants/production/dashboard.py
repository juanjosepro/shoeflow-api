"""Datos del dashboard. Todo se cuenta en DOCENAS (pares / 12); una docena de 6 pares cuenta 0.5.

`compute_dashboard` es una función pura (recibe listas simples) para poder probarla sin base de datos;
`build_dashboard` es la que consulta la base y la llama.
"""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Max
from django.utils import timezone

from apps.tenants.payroll.models import PaymentSettlement, SettlementAdjustment
from apps.tenants.staff.models import Specialty, Worker

from . import services
from .models import Dozen, DozenStageAssignment

STALE_DAYS = 7  # sin movimiento hace tantos días = docena detenida
ALLOWED_WEEKS = (4, 8, 12, 26)
OPEN_STATUSES = (Dozen.Status.PENDING, Dozen.Status.IN_PROGRESS)


def _doz(pairs):
    """Pares -> docenas (decimal)."""
    return pairs / 12


def _r(value, digits=2):
    return round(float(value), digits)


def _dz(value):
    """Texto de docenas: 1 docena, 2.5 docenas."""
    number = f"{round(float(value), 1):g}"
    return f"{number} {'docena' if number == '1' else 'docenas'}"


def _monday(day):
    return day - timedelta(days=day.weekday())


def compute_dashboard(
    *,
    today,
    weeks,
    open_dozens,        # [{id, pairs, status, priority, model, registered, last_move}] activas pendientes/en proceso
    finished_dozens,    # [{pairs, last_move}] completadas con último movimiento en el periodo
    registered,         # [{pairs, registered}] registradas en el periodo (cualquier estado)
    rejected,           # [{pairs}] rechazadas en el periodo
    assignments,        # [{specialty_id, worker_id, worker, pairs, amount, completed}] del periodo
    open_assigned,      # {dozen_id: {specialty_id}} etapas ya asignadas de las docenas abiertas
    stages,             # [{id, name, order}] etapas activas
    exclusions,         # {specialty_id: {ids excluyentes}}
    unpaid_by_worker,   # [{worker_id, worker, amount, dozens}] pendiente de pago por trabajador
    paid,               # [{date, amount}] pagos del periodo
    pending_adjustments_total,
    missing_base,       # [{id, name}]
    stages_without_workers,  # [nombres]
):
    start = _monday(today) - timedelta(weeks=weeks - 1)
    week_starts = [start + timedelta(weeks=i) for i in range(weeks)]
    index = {w: i for i, w in enumerate(week_starts)}

    def bucket(day):
        return index.get(_monday(day))

    # ── Semana a semana ──
    series = [
        {"week_start": w.isoformat(), "registered": 0.0, "completed": 0.0, "paid": 0.0}
        for w in week_starts
    ]
    for row in registered:
        i = bucket(row["registered"])
        if i is not None:
            series[i]["registered"] += _doz(row["pairs"])
    for row in finished_dozens:
        i = bucket(row["last_move"])
        if i is not None:
            series[i]["completed"] += _doz(row["pairs"])
    for row in paid:
        i = bucket(row["date"])
        if i is not None:
            series[i]["paid"] += float(row["amount"])
    for item in series:
        item["registered"] = _r(item["registered"])
        item["completed"] = _r(item["completed"])
        item["paid"] = _r(item["paid"])

    # ── Tarjetas ──
    in_process = sum(_doz(d["pairs"]) for d in open_dozens if d["status"] == Dozen.Status.IN_PROGRESS)
    pending = sum(_doz(d["pairs"]) for d in open_dozens if d["status"] == Dozen.Status.PENDING)
    stale = [
        d for d in open_dozens
        if (today - (d["last_move"] or d["registered"])).days >= STALE_DAYS
    ]
    this_week = series[-1]
    last_week = series[-2] if len(series) > 1 else None

    cards = {
        "in_process": _r(in_process),
        "pending": _r(pending),
        "completed_period": _r(sum(_doz(d["pairs"]) for d in finished_dozens)),
        "registered_period": _r(sum(_doz(d["pairs"]) for d in registered)),
        "completed_this_week": this_week["completed"],
        "completed_last_week": last_week["completed"] if last_week else None,
        "stale": _r(sum(_doz(d["pairs"]) for d in stale)),
        "stale_count": len(stale),
        "rejected_period": _r(sum(_doz(d["pairs"]) for d in rejected)),
        "to_pay": _r(sum(float(w["amount"]) for w in unpaid_by_worker) + float(pending_adjustments_total)),
        "paid_period": _r(sum(float(p["amount"]) for p in paid)),
        "labor_cost_period": _r(sum(float(a["amount"]) for a in assignments)),
    }

    # ── Embudo por etapa: cuántas docenas esperan cada etapa y cuántas se hicieron en el periodo ──
    all_ids = [s["id"] for s in stages]
    groups = services.stage_groups(all_ids, exclusions)
    ordered = sorted(stages, key=lambda s: s["order"])
    waiting = defaultdict(float)
    for dozen in open_dozens:
        assigned = open_assigned.get(dozen["id"], set())
        progress = services.stage_progress(all_ids, exclusions, assigned)
        counted_groups = set()
        for stage in ordered:
            sid = stage["id"]
            if sid in assigned or sid in progress["not_applicable"]:
                continue
            group = groups[sid]
            # Un grupo excluyente sin elegir cuenta una sola vez (en su primera etapa)
            if len(group) > 1 and not group & assigned:
                if group in counted_groups:
                    continue
                counted_groups.add(group)
            waiting[sid] += _doz(dozen["pairs"])

    funnel = []
    done = defaultdict(float)
    for a in assignments:
        done[a["specialty_id"]] += _doz(a["pairs"])
    for stage in sorted(stages, key=lambda s: s["order"]):
        funnel.append({
            "id": stage["id"],
            "name": stage["name"],
            "waiting": _r(waiting[stage["id"]]),
            "done": _r(done[stage["id"]]),
        })

    # ── Distribuciones de lo que está abierto ──
    by_priority = defaultdict(float)
    by_model = defaultdict(float)
    for d in open_dozens:
        by_priority[d["priority"]] += _doz(d["pairs"])
        by_model[d["model"]] += _doz(d["pairs"])
    models_top = sorted(by_model.items(), key=lambda kv: -kv[1])[:6]

    # ── Trabajadores ──
    produced = defaultdict(lambda: {"dozens": 0.0, "amount": 0.0, "name": ""})
    for a in assignments:
        item = produced[a["worker_id"]]
        item["name"] = a["worker"]
        item["dozens"] += _doz(a["pairs"])
        item["amount"] += float(a["amount"])
    top_workers = sorted(produced.values(), key=lambda w: -w["dozens"])[:8]
    pending_workers = sorted(unpaid_by_worker, key=lambda w: -float(w["amount"]))[:8]

    # ── Alertas ──
    alerts = []
    if missing_base:
        alerts.append({
            "level": "warn", "code": "missing_base",
            "text": "Etapas sin tarifa base: " + ", ".join(s["name"] for s in missing_base),
        })
    if stages_without_workers:
        alerts.append({
            "level": "warn", "code": "no_workers",
            "text": "Etapas sin trabajadores: " + ", ".join(stages_without_workers),
        })
    if stale:
        alerts.append({
            "level": "info", "code": "stale",
            "text": f"Sin movimiento hace {STALE_DAYS} días o más: {_dz(cards['stale'])}",
        })
    if rejected:
        alerts.append({
            "level": "danger", "code": "rejected",
            "text": f"Rechazadas en el periodo: {_dz(cards['rejected_period'])}",
        })

    return {
        "weeks": weeks,
        "from": start.isoformat(),
        "to": today.isoformat(),
        "cards": cards,
        "weekly": series,
        "funnel": funnel,
        "by_priority": [{"key": k, "dozens": _r(v)} for k, v in by_priority.items()],
        "by_model": [{"name": k, "dozens": _r(v)} for k, v in models_top],
        "top_workers": [
            {"name": w["name"], "dozens": _r(w["dozens"]), "amount": _r(w["amount"])} for w in top_workers
        ],
        "pending_workers": [
            {"name": w["worker"], "amount": _r(w["amount"]), "dozens": _r(w["dozens"])}
            for w in pending_workers
        ],
        "alerts": alerts,
    }


def build_dashboard(weeks=8):
    weeks = weeks if weeks in ALLOWED_WEEKS else 8
    today = timezone.localdate()
    start = _monday(today) - timedelta(weeks=weeks - 1)

    def to_date(value):
        return timezone.localtime(value).date() if hasattr(value, "hour") else value

    # Docenas abiertas (pendientes y en proceso)
    open_qs = (
        Dozen.objects.filter(is_active=True, status__in=OPEN_STATUSES)
        .annotate(last_move=Max("assignments__completed_at"))
        .values("id", "pairs", "status", "priority", "model__name", "registered_at", "last_move")
    )
    open_dozens = [
        {
            "id": d["id"], "pairs": d["pairs"], "status": d["status"], "priority": d["priority"],
            "model": d["model__name"], "registered": to_date(d["registered_at"]), "last_move": d["last_move"],
        }
        for d in open_qs
    ]
    open_ids = [d["id"] for d in open_dozens]

    open_assigned = defaultdict(set)
    for dozen_id, specialty_id in DozenStageAssignment.objects.filter(dozen_id__in=open_ids).values_list(
        "dozen_id", "specialty_id"
    ):
        open_assigned[dozen_id].add(specialty_id)

    # Completadas en el periodo (fecha = último movimiento)
    finished_dozens = [
        {"pairs": d["pairs"], "last_move": d["last_move"]}
        for d in Dozen.objects.filter(is_active=True, status=Dozen.Status.COMPLETED)
        .annotate(last_move=Max("assignments__completed_at"))
        .filter(last_move__gte=start)
        .values("pairs", "last_move")
    ]

    registered = [
        {"pairs": d["pairs"], "registered": to_date(d["registered_at"])}
        for d in Dozen.objects.filter(is_active=True, registered_at__date__gte=start)
        .values("pairs", "registered_at")
    ]
    rejected = list(
        Dozen.objects.filter(is_active=True, status=Dozen.Status.REJECTED, updated_at__date__gte=start)
        .values("pairs")
    )

    # Etapas hechas en el periodo (producción y mano de obra)
    assignments = [
        {
            "specialty_id": a["specialty_id"], "worker_id": a["worker_id"], "worker": a["worker__names"],
            "pairs": a["dozen__pairs"], "amount": a["amount"], "completed": a["completed_at"],
        }
        for a in DozenStageAssignment.objects.filter(completed_at__gte=start)
        .values("specialty_id", "worker_id", "worker__names", "dozen__pairs", "amount", "completed_at")
    ]

    stages = [
        {"id": s.id, "name": s.name, "order": s.order}
        for s in Specialty.objects.filter(is_active=True)
    ]

    # Pendiente de pago por trabajador (etapas terminadas sin liquidar + ajustes pendientes)
    unpaid = defaultdict(lambda: {"worker": "", "amount": Decimal("0"), "dozens": 0.0})
    for a in (
        DozenStageAssignment.objects.filter(status=DozenStageAssignment.Status.COMPLETED, settlement__isnull=True)
        .values("worker_id", "worker__names", "amount", "dozen__pairs")
    ):
        item = unpaid[a["worker_id"]]
        item["worker"] = a["worker__names"]
        item["amount"] += a["amount"]
        item["dozens"] += _doz(a["dozen__pairs"])
    unpaid_by_worker = [{"worker_id": k, **v} for k, v in unpaid.items()]
    adjustments_total = sum(
        (a.signed_amount for a in SettlementAdjustment.objects.filter(settlement__isnull=True)), Decimal("0")
    )

    paid = [
        {"date": to_date(p["created_at"]), "amount": p["amount_paid"]}
        for p in PaymentSettlement.objects.filter(created_at__date__gte=start).values("created_at", "amount_paid")
    ]

    # Etapas activas que ningún trabajador activo sabe hacer
    with_workers = set(
        Worker.specialties.through.objects.filter(worker__is_active=True).values_list("specialty_id", flat=True)
    )
    stages_without_workers = [s["name"] for s in stages if s["id"] not in with_workers]

    from apps.tenants.payroll import services as payroll_services  # evita import circular

    return compute_dashboard(
        today=today,
        weeks=weeks,
        open_dozens=open_dozens,
        finished_dozens=finished_dozens,
        registered=registered,
        rejected=rejected,
        assignments=assignments,
        open_assigned=open_assigned,
        stages=stages,
        exclusions=services.load_exclusions(),
        unpaid_by_worker=unpaid_by_worker,
        paid=paid,
        pending_adjustments_total=adjustments_total,
        missing_base=payroll_services.specialties_without_base(),
        stages_without_workers=stages_without_workers,
    )
