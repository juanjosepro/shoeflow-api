from datetime import timedelta
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.tenants.catalog.models import Color, MaterialType, Model, PlantType, Size
from apps.tenants.payroll.models import PaymentSettlement
from apps.tenants.staff.models import Specialty, Worker


class Dozen(models.Model):
    """Un lote físico con su propio código. Normalmente 12 pares; puede tener menos."""

    class Status(models.TextChoices):
        # La etapa en que va no se guarda aquí: se deduce de las asignaciones.
        PENDING = "PENDIENTE", "Pendiente"  # registrada, sin etapas asignadas
        IN_PROGRESS = "EN_PROCESO", "En proceso"  # automático con la primera asignación
        COMPLETED = "COMPLETADO", "Completado"  # lo marca el administrador
        REJECTED = "RECHAZADO", "Rechazado"  # falla grave: no admite asignaciones

    class Priority(models.TextChoices):
        LOW = "BAJA", "Baja"
        NORMAL = "NORMAL", "Normal"
        HIGH = "ALTA", "Alta"
        URGENT = "URGENTE", "Urgente"

    model = models.ForeignKey(Model, on_delete=models.PROTECT, related_name="dozens")
    size = models.ForeignKey(Size, on_delete=models.PROTECT, related_name="dozens")
    code = models.CharField(max_length=255, unique=True)  # Ej: AM-001
    # Pares del lote (1 a 12). Fracción de docena = pairs / 12 (6 pares = 0.5)
    pairs = models.PositiveSmallIntegerField(
        default=12, validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    # Serie de tallas opcional: {"38": 2, "39": 3, ...} (talla -> pares). Si existe, suma `pairs`.
    # Es informativa (ficha y detalle): el precio sigue dependiendo de `size` y `pairs`.
    size_run = models.JSONField(null=True, blank=True)
    material_type = models.ForeignKey(MaterialType, on_delete=models.PROTECT, related_name="dozens")
    color = models.ForeignKey(Color, on_delete=models.PROTECT, related_name="dozens")
    plant_type = models.ForeignKey(PlantType, on_delete=models.PROTECT, related_name="dozens")
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    registered_at = models.DateTimeField()
    # Agrupa las docenas creadas en un mismo registro
    registration_group = models.CharField(
        max_length=20, null=True, blank=True, db_index=True, editable=False
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Docena"
        verbose_name_plural = "Docenas"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(pairs__gte=1, pairs__lte=12), name="dozen_pairs_between_1_and_12"
            )
        ]

    @property
    def fraction(self):
        """Parte de docena que representa (pairs / 12). Se usa para calcular el pago."""
        return Decimal(self.pairs) / Decimal(12)

    def __str__(self):
        return f"{self.code} - {self.model.name} {self.size} ({self.pairs} pares)"


class DozenStageAssignment(models.Model):
    """Quién hizo una etapa de una docena, cuándo y por cuánto."""

    class Status(models.TextChoices):
        PENDING = "PENDIENTE", "Pendiente"
        IN_PROGRESS = "EN PROCESO", "En Proceso"
        COMPLETED = "COMPLETADO", "Completado"
        CANCELED = "CANCELADO", "Cancelado"

    dozen = models.ForeignKey(Dozen, on_delete=models.CASCADE, related_name="assignments")
    # La etapa es una especialidad (las activas, en el orden de Specialty.order)
    specialty = models.ForeignKey(Specialty, on_delete=models.PROTECT, related_name="dozen_assignments")
    # Debe tener esa especialidad: lo valida el servicio, no la base de datos
    worker = models.ForeignKey(Worker, on_delete=models.PROTECT, related_name="dozen_assignments")
    # Vacío = pendiente de pago. Se llena al liquidar la semana.
    settlement = models.ForeignKey(
        PaymentSettlement, on_delete=models.SET_NULL, null=True, blank=True, related_name="items"
    )
    # En el flujo masivo siempre queda Completado
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPLETED)
    # Siempre se llenan. delivered_at nunca es posterior a completed_at
    # (lo garantiza el CheckConstraint; el servicio lo valida antes para dar un mensaje claro).
    delivered_at = models.DateField()
    completed_at = models.DateField()  # Define a qué semana de pago pertenece
    # Se fijan al guardar: un cambio de tarifas NO altera lo ya registrado.
    # unit_price = tarifa base resuelta + WorkerRateExtra.extra_price (por docena completa)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    # amount = unit_price x pairs / 12 (lo que se le paga por esta etapa)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Asignación de etapa"
        verbose_name_plural = "Asignaciones de etapas"
        ordering = ["dozen", "specialty__order"]
        constraints = [
            models.UniqueConstraint(fields=["dozen", "specialty"], name="unique_assignment_dozen_specialty"),
            # Django 5.0: el argumento es check=. En 5.1+ pasa a condition=.
            models.CheckConstraint(
                check=models.Q(delivered_at__lte=models.F("completed_at")),
                name="assignment_delivered_not_after_completed",
            ),
            models.CheckConstraint(check=models.Q(amount__gte=0), name="assignment_amount_not_negative"),
        ]

    def __str__(self):
        return f"{self.dozen.code} - {self.specialty.name} - {self.worker.names}"

    @property
    def week_identifier(self):
        """Semana ISO del trabajo realizado, ej. '2026-W41'."""
        year, week, _ = self.completed_at.isocalendar()
        return f"{year}-W{week:02d}"

    @property
    def week_label(self):
        """Rango legible de la semana, ej. 'Del 5 de octubre al 11 de octubre'."""
        monday = self.completed_at - timedelta(days=self.completed_at.weekday())
        sunday = monday + timedelta(days=6)
        meses = {
            1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
            7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
        }
        return f"Del {monday.day} de {meses[monday.month]} al {sunday.day} de {meses[sunday.month]}"