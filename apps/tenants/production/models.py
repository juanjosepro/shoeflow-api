from django.db import models
from apps.tenants.catalog.models import ModelVariant
from apps.tenants.staff.models import Worker
from apps.tenants.payroll.models import WorkerRateOverride, PaymentSettlement
from datetime import timedelta
from decimal import Decimal

def validate_dozen_quantity(value):
    """Solo permite 0.5 o un entero positivo (1, 2, 3...)."""
    if value == Decimal('0.5'):
        return
    if value > 0 and value == value.to_integral_value():
        return
    raise ValidationError("La cantidad debe ser 0.5 o un número entero mayor a 0.")

class Dozen(models.Model):
    class Status(models.TextChoices):
        # 0. Inicio: Puede que el administrador registre primero y luego de la orden de iniciar el proceso
        PENDING = 'PENDIENTE', 'Pendiente'
        # 1. Inicio: El cortador recibe el material
        CUTTING = 'CORTADO', 'Cortado'
        # 2. Unión: Se cosen las piezas (Aparado)
        STITCHING = 'APARADO', 'Aparado'
        # 3. Forma: Se le da la forma sobre la horma (Armado)
        ASSEMBLY = 'ARMADO', 'Armado'
        # 4. Estética: Limpieza y detalles finales (Rematado)
        FINISHING = 'REMATADO', 'Rematado'
        # 5. Filtro: Revisión antes de almacén
        QUALITY_CHECK = 'CONTROL_DE_CALIDAD', 'Control de Calidad'
        # 6. Final: Listo para que el cliente lo compre
        READY = 'LISTO_PARA_VENTA', 'Disponible para Venta'
        COMPLETED = 'COMPLETADO', 'Completado'
        # 7. Excepción: Por si hubo un problema grave
        REJECTED = 'RECHAZADO/FALLA', 'Rechazado/Falla'

    class Materials(models.TextChoices):
        LEATHER = 'CUERO', 'Cuero'
        GAMUSA = 'GAMUSA', 'Gamusa'
        SYNTHETIC = 'SINTETICO', 'Sintetico'
        OTHER = 'OTRO', 'Otro'

    class Colors(models.TextChoices):
        WHITE = 'BLANCO', 'Blanco'
        BLACK = 'NEGRO', 'Negro'
        DARK_GRAY = 'DARK_GRAY', 'darkgray'
        TAN = 'TAN', 'tan'
        SADDLE_BROWN = 'SADDLE_BROWN', 'saddlebrown'
        GOLD = 'GOLD', 'gold'
        STEEL_BLUE = 'STEEL_BLUE', 'steelblue'
        OTHER = 'OTHER', 'Otro'

    model_variant = models.ForeignKey(ModelVariant, on_delete=models.CASCADE)
    code = models.CharField(max_length=255)
    quantity = models.DecimalField(
        max_digits=4, 
        decimal_places=1, 
        default=Decimal('1.0'),
        validators=[validate_dozen_quantity],
        help_text="Cantidad de docenas en este lote (ej: 1.0 = 12 pares, 0.5 = 6 pares)"
    )
    material = models.CharField(max_length=50, choices=Materials.choices)
    color = models.CharField(max_length=50, choices=Colors.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    registered_at = models.DateTimeField()
    # registration_group = models.CharField(
    #     max_length=20,
    #     db_index=True,
    #     editable=False,
    # )
    registration_group = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_index=True,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Docena"
        verbose_name_plural = "Dozen"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.code} - {self.model_variant.model.name} {self.model_variant.size}"

class DozenStageAssignment(models.Model):
    class Stage(models.TextChoices):
        CUTTING = 'CORTADO', 'Corte'
        STITCHING = 'APARADO', 'Aparado'
        ASSEMBLY = 'ARMADO', 'Armado'
        FINISHING = 'REMATADO', 'Rematado'
        QUALITY_CHECK = 'CONTROL_DE_CALIDAD', 'Control de Calidad'

    class Status(models.TextChoices):
        PENDING = 'PENDIENTE', 'Pendiente'
        IN_PROGRESS = 'EN PROCESO', 'En Proceso'
        COMPLETED = 'COMPLETADO', 'Completado'
        CANCELED = 'CANCELADO', 'Cancelado'

    worker = models.ForeignKey(Worker, on_delete=models.PROTECT, related_name='dozen_assignments')
    dozen = models.ForeignKey(Dozen, on_delete=models.CASCADE, related_name="assignments")
    stage = models.CharField(max_length=20, choices=Stage.choices)
    settlement = models.ForeignKey(
        PaymentSettlement, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='items'
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    delivered_at = models.DateTimeField(null=True, blank=True)   # cuando se le entregó al worker
    completed_at = models.DateTimeField(null=True, blank=True)   # cuando terminó
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Asignación de etapa"
        verbose_name_plural = "Asignaciones de etapas"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.dozen.code} docenas - {self.worker.names}"

    @property
    def calculate_payment(self):
        # 1. Buscamos el precio por docena (estándar o personalizado)
        override = WorkerRateOverride.objects.filter(
            worker=self.worker, 
            model_variant=self.dozen.model_variant
        ).first()
        
        price_per_dozen = override.custom_price if override else self.dozen.model_variant.standard_price
        
        # 2. Multiplicamos por la cantidad real que trae el lote (Dozen)
        # S/ 60.00 * 0.5 = S/ 30.00
        return price_per_dozen * self.dozen.quantity

    @property
    def week_identifier(self):
        """
        Retorna un string único para agrupar: '2026-W16'
        """
        if self.created_at:
            # Obtenemos el año y el número de semana ISO
            year, week, weekday = self.created_at.isocalendar()
            return f"{year}-W{week:02d}"
        return None

    @property
    def week_label(self):
        """
        Retorna un rango de fechas amigable: 'Del 13 de abril al 19 de abril'
        """
        if not self.created_at:
            return "Sin fecha"
            
        # 1. Encontrar el lunes de esa semana
        # weekday() devuelve 0 para lunes, 6 para domingo
        monday = self.created_at.date() - timedelta(days=self.created_at.weekday())
        sunday = monday + timedelta(days=6)
        
        # 2. Diccionario para meses en español (opcional si no tienes locale configurado)
        meses = {
            1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
            5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
            9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
        }

        # 3. Formatear el string
        inicio = f"{monday.day} de {meses[monday.month]}"
        fin = f"{sunday.day} de {meses[sunday.month]}"
        
        return f"Del {inicio} al {fin}"