from django.db import models
from django.utils import timezone
from apps.tenants.catalog.models import BrandVariant
from apps.tenants.staff.models import Worker
from apps.tenants.payroll.models import WorkerRateOverride, PaymentSettlement
from datetime import timedelta

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
        QUALITY_CHECK = 'CONTROL DE CALIDAD', 'Control de Calidad'
        # 6. Final: Listo para que el cliente lo compre
        READY = 'LISTO PARA VENTA', 'Disponible para Venta'
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

    brand_variant = models.ForeignKey(BrandVariant, on_delete=models.CASCADE)
    code = models.CharField(max_length=255)
    quantity = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=1.0,
        help_text="Cantidad de docenas en este lote (ej: 1.0 = 12 pares, 0.5 = 6 pares)"
    )
    material = models.CharField(max_length=50, choices=Materials.choices, default=Materials.LEATHER)
    color = models.CharField(max_length=50, choices=Colors.choices, default=Colors.WHITE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CUTTING)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.code} - {self.brand_variant.brand.name} {self.brand_variant.size}"

class DozenAssignment(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDIENTE', 'Pendiente'
        IN_PROGRESS = 'EN PROCESO', 'En Proceso'
        COMPLETED = 'COMPLETADO', 'Completado'
        CANCELED = 'CANCELADO', 'Cancelado'

    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='dozen_assignments')
    dozen = models.ForeignKey(Dozen, on_delete=models.CASCADE)
    settlement = models.ForeignKey(
        PaymentSettlement, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='items'
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.dozen.code} docenas - {self.worker.names}"

    @property
    def calculate_payment(self):
        # 1. Buscamos el precio por docena (estándar o personalizado)
        override = WorkerRateOverride.objects.filter(
            worker=self.worker, 
            brand_variant=self.dozen.brand_variant
        ).first()
        
        price_per_dozen = override.custom_price if override else self.dozen.brand_variant.standard_price
        
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