from django.utils import timezone
from django.db import transaction
from .models import Dozen, DozenStageAssignment


# Define el orden de las etapas en un solo lugar (fuente de verdad del flujo)
STAGE_ORDER = [
    DozenStageAssignment.Stage.CUTTING,
    DozenStageAssignment.Stage.STITCHING,
    DozenStageAssignment.Stage.ASSEMBLY,
    DozenStageAssignment.Stage.FINISHING,
    DozenStageAssignment.Stage.QUALITY_CHECK,
]


def get_next_stage(current_stage: str) -> str | None:
    """Devuelve la siguiente etapa en el flujo, o None si ya es la última."""
    try:
        idx = STAGE_ORDER.index(current_stage)
    except ValueError:
        return None
    if idx + 1 < len(STAGE_ORDER):
        return STAGE_ORDER[idx + 1]
    return None


@transaction.atomic
def complete_assignment(assignment: DozenStageAssignment) -> DozenStageAssignment:
    """
    Marca una asignación como completada y sincroniza el estado
    resumen del Dozen. Devuelve la asignación actualizada.
    """
    assignment.status = DozenStageAssignment.Status.COMPLETED
    assignment.completed_at = timezone.now()
    assignment.save(update_fields=["status", "completed_at", "updated_at"])

    next_stage = get_next_stage(assignment.stage)
    assignment.dozen.status = next_stage if next_stage else Dozen.Status.READY
    assignment.dozen.save(update_fields=["status", "updated_at"])
    return assignment


@transaction.atomic
def deliver_assignment(dozen: Dozen, stage: str, worker) -> DozenStageAssignment:
    """
    Crea (o reutiliza) una asignación pendiente y la marca como entregada
    a un worker específico.
    """
    assignment = DozenStageAssignment.objects.create(
        dozen=dozen,
        stage=stage,
        worker=worker,
        status=DozenStageAssignment.Status.IN_PROGRESS,
        delivered_at=timezone.now(),
    )
    dozen.status = stage
    dozen.save(update_fields=["status", "updated_at"])
    return assignment