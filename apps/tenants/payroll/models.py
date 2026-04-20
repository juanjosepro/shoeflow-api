from django.db import models
from apps.tenants.staff.models import Worker
from apps.tenants.catalog.models import BrandVariant

class WorkerRateOverride(models.Model):
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='custom_prices')
    brand_variant = models.ForeignKey(BrandVariant, on_delete=models.CASCADE)
    # Este precio tiene PRIORIDAD sobre el standard_price de BrandVariant
    custom_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        # Evita que un mismo trabajador tenga dos precios para la misma variante
        unique_together = ('worker', 'brand_variant')

class PaymentSettlement(models.Model):
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='settlements')
    start_date = models.DateField() # Lunes
    end_date = models.DateField()   # Sábado
    
    total_earned = models.DecimalField(max_digits=10, decimal_places=2) # Lo que trabajó (ej: 500)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)  # Lo que le das (ej: 300)
    
    pending_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0) # Deuda (200)
    description = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Pago {self.worker.names} - Sem {self.start_date}"
