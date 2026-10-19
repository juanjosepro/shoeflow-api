from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.tenants.catalog.models import MaterialType, Model, PlantType, Size
from apps.tenants.staff.models import Specialty, Worker

ZERO = Decimal("0")

class SpecialtyRate(models.Model):
    """Regla de tarifa: cuánto se paga por DOCENA COMPLETA en una etapa.

    Las condiciones (model, size, material, plant_type) son opcionales:
    vacío = "cualquiera". Para una docena aplica la regla MÁS ESPECÍFICA que
    cumpla (más condiciones coincidentes); en empate de cantidad gana
    material > plant_type > size > model. Sin regla aplicable no se puede guardar.
    """

    specialty = models.ForeignKey(Specialty, on_delete=models.CASCADE, related_name="rates")
    model = models.ForeignKey(Model, on_delete=models.CASCADE, null=True, blank=True, related_name="rates")
    size = models.ForeignKey(Size, on_delete=models.CASCADE, null=True, blank=True, related_name="rates")
    material_type = models.ForeignKey(MaterialType, on_delete=models.PROTECT, null=True, blank=True, related_name="rates")
    plant_type = models.ForeignKey(PlantType, on_delete=models.PROTECT, null=True, blank=True, related_name="rates")
    # Precio por docena (12 pares)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(ZERO)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tarifa"
        verbose_name_plural = "Tarifas"
        ordering = ["specialty__order", "model", "size", "material_type", "plant_type"]
        constraints = [
            # Misma combinación de condiciones no se repite. nulls_distinct=False
            # trata NULL como un valor más (requiere PostgreSQL 15+).
            models.UniqueConstraint(
                fields=["specialty", "model", "size", "material_type", "plant_type"],
                name="unique_rate_specialty_conditions",
                nulls_distinct=False,
            )
        ]

    @property
    def specificity(self):
        """Cantidad de condiciones que define la regla."""
        return sum(v is not None for v in (self.model_id, self.size_id, self.material_type_id, self.plant_type_id))

    def __str__(self):
        conds = [str(c) for c in (self.model, self.size, self.material_type, self.plant_type) if c]
        return f"{self.specialty.name} | {' / '.join(conds) or 'Cualquiera'} | S/ {self.price}"


class WorkerRateExtra(models.Model):
    """Ajuste fijo a una persona en una etapa: unit_price = tarifa base + extra_price.
    Puede ser negativo (paga menos). Aplica a todas las docenas de esa etapa."""

    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name="rate_extras")
    specialty = models.ForeignKey(Specialty, on_delete=models.CASCADE, related_name="worker_extras")
    # Se suma (o resta) al precio por docena
    extra_price = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Extra por trabajador"
        verbose_name_plural = "Extras por trabajador"
        ordering = ["worker", "specialty__order"]
        constraints = [
            models.UniqueConstraint(fields=["worker", "specialty"], name="unique_extra_worker_specialty")
        ]

    def __str__(self):
        return f"{self.worker.names} | {self.specialty.name} | {self.extra_price:+}"


class PaymentSettlement(models.Model):
    """Pago semanal de un trabajador.
    total_to_pay = total_earned + total_adjustments
    pending_balance = total_to_pay - amount_paid"""

    worker = models.ForeignKey(Worker, on_delete=models.PROTECT, related_name="settlements")
    start_date = models.DateField()  # Lunes
    end_date = models.DateField()  # Domingo (o el día que cierre la semana)

    total_earned = models.DecimalField(max_digits=10, decimal_places=2)  # Suma de los amount de sus asignaciones
    total_adjustments = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)  # Suma con signo de los ajustes
    total_to_pay = models.DecimalField(max_digits=10, decimal_places=2)  # Lo que correspondía pagar
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)  # Lo que realmente se entregó
    pending_balance = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)  # Deuda que queda

    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Liquidación de pago"
        verbose_name_plural = "Liquidaciones de pago"
        ordering = ["-start_date", "worker"]
        constraints = [
            # Sin unicidad por semana: se puede pagar parte de las etapas y el resto después,
            # dentro del mismo rango. Una etapa nunca se paga dos veces (settlement ya asignado).
            # models.UniqueConstraint(
            #     fields=["worker", "start_date", "end_date"], name="unique_settlement_worker_week"
            # ),
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F("start_date")), name="settlement_end_not_before_start"
            ),
            models.CheckConstraint(
                check=models.Q(total_to_pay=models.F("total_earned") + models.F("total_adjustments")),
                name="settlement_total_to_pay_consistent",
            ),
            models.CheckConstraint(
                check=models.Q(pending_balance=models.F("total_to_pay") - models.F("amount_paid")),
                name="settlement_pending_consistent",
            ),
        ]

    def __str__(self):
        return f"Pago {self.worker.names} - Sem {self.start_date}"


class SettlementAdjustment(models.Model):
    """Bono, descuento, adelanto o saldo arrastrado de un trabajador.
    Nace PENDIENTE (settlement vacío) y se enlaza al pago cuando se liquida."""

    class Type(models.TextChoices):
        BONUS = "BONO", "Bono"  # suma
        DEDUCTION = "DESCUENTO", "Descuento"  # resta
        ADVANCE = "ADELANTO", "Adelanto"  # resta (ya se le dio dinero antes)
        CARRYOVER = "SALDO", "Saldo anterior"  # suma (deuda pendiente de una semana previa)

    NEGATIVE_TYPES = (Type.DEDUCTION, Type.ADVANCE)

    worker = models.ForeignKey(Worker, on_delete=models.PROTECT, related_name="adjustments")
    # Vacío = aún no pagado. Se llena al crear la liquidación.
    settlement = models.ForeignKey(
        PaymentSettlement, on_delete=models.SET_NULL, null=True, blank=True, related_name="adjustments"
    )
    type = models.CharField(max_length=20, choices=Type.choices)
    # Siempre positivo: el signo lo define el tipo (ver signed_amount)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    reason = models.CharField(max_length=255)  # Obligatorio: ej. "Mal acabado en D-002"
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ajuste de pago"
        verbose_name_plural = "Ajustes de pago"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name="adjustment_amount_positive"),
        ]

    @property
    def signed_amount(self):
        return -self.amount if self.type in self.NEGATIVE_TYPES else self.amount

    def clean(self):
        if self.settlement_id and self.settlement.worker_id != self.worker_id:
            raise ValidationError("El ajuste y la liquidación deben ser del mismo trabajador.")

    def __str__(self):
        return f"{self.worker.names} | {self.get_type_display()} | {self.signed_amount:+} | {self.reason}"