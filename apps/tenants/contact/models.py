from django.db import models

class Customer(models.Model):
    """[PED] Cliente al que se le fabrica y entrega calzado. No se borra si tiene pedidos: se desactiva."""

    name = models.CharField(max_length=150)
    # RUC / DNI. Opcional, pero si se llena no puede repetirse
    document = models.CharField(max_length=20, unique=True, null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["name"]

    def __str__(self):
        return self.name


class CustomerOrder(models.Model):
    """[PED] Pedido de un cliente. Agrupa docenas (Dozen.customer_order).

    El estado (pendiente / en producción / listo) NO se guarda: se calcula con el avance de
    sus docenas (ver order_services.annotate_orders). Solo se guarda el cierre manual.
    """

    class Closure(models.TextChoices):
        DELIVERED = "ENTREGADO", "Entregado"
        CANCELED = "CANCELADO", "Cancelado"

    class Priority(models.TextChoices):
        LOW = "BAJA", "Baja"
        NORMAL = "NORMAL", "Normal"
        HIGH = "ALTA", "Alta"
        URGENT = "URGENTE", "Urgente"

    code = models.CharField(max_length=20, unique=True)  # PED-0001 (también es el registration_group de sus docenas)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="orders")
    ordered_at = models.DateField()  # fecha en que el cliente hizo el pedido
    due_date = models.DateField(null=True, blank=True)  # fecha de entrega prometida
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)  # se copia a sus docenas
    notes = models.TextField(blank=True, default="")
    closure = models.CharField(max_length=20, choices=Closure.choices, null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.code} - {self.customer.name}"

