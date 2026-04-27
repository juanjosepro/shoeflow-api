from django.db import models
from django_tenants.models import TenantMixin, DomainMixin

class Client(TenantMixin):
    schema_name = models.CharField(
        max_length=63, 
        unique=True, 
        verbose_name="Dominio"
    )
    names = models.CharField(max_length=100, verbose_name="Nombres")
    description = models.CharField(max_length=255, null=True, blank=True, verbose_name="Descripción")
    email = models.EmailField(unique=True, null=True, blank=True, verbose_name="Correo")
    phone = models.CharField(max_length=15, null=True, blank=True, verbose_name="Teléfono")
    paid_until = models.DateField(null=True, blank=True, verbose_name="Pagado hasta")
    comments = models.CharField(max_length=255, null=True, blank=True, verbose_name="Comentarios")
    is_active = models.BooleanField(default=True)
    on_trial = models.BooleanField(default=True)
    created_on = models.DateField(auto_now_add=True)
    updated_on = models.DateField(auto_now=True)

    # default true, schema will be automatically created and synced when tenant is created
    auto_create_schema = True

    def delete(self, *args, **kwargs):
        # El parámetro True fuerza la eliminación del esquema en la DB
        self.delete_tenant(True) 
        super().delete(*args, **kwargs)

class Domain(DomainMixin):
    pass
