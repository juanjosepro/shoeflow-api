from django.db import models
from django_tenants.models import TenantMixin, DomainMixin


class Client(TenantMixin):

    # Información del tenant
    schema_name = models.CharField(
        max_length=63,
        unique=True,
        verbose_name="Dominio"
    )

    # Información del negocio
    business_name = models.CharField(
        max_length=150,
        verbose_name="Nombre comercial"
    )
    business_legal_name = models.CharField(
        max_length=150,
        null=True,
        blank=True,
        verbose_name="Razón social"
    )
    business_ruc = models.CharField(
        max_length=11,
        null=True,
        blank=True,
        verbose_name="RUC"
    )

    business_address = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Dirección del negocio"
    )
    business_phone = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        verbose_name="Teléfono del negocio"
    )

    business_email = models.EmailField(
        unique=True,
        null=True,
        blank=True,
        verbose_name="Correo del negocio"
    )

    # Información del responsable
    owner_names = models.CharField(
        max_length=100,
        verbose_name="Nombres del responsable"
    )
    owner_last_names = models.CharField(
        max_length=100,
        verbose_name="Apellidos del responsable"
    )
    owner_dni = models.CharField(
        max_length=8,
        null=True,
        blank=True,
        verbose_name="DNI del responsable"
    )

    # Información de contacto
    owner_email = models.EmailField(
        unique=True,
        null=True,
        blank=True,
        verbose_name="Correo del responsable"
    )
    owner_phone = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        verbose_name="Teléfono del responsable"
    )

    # Suscripción
    paid_until = models.DateField(null=True, blank=True, verbose_name="Pagado hasta (Fin de suscripción)")
    on_trial = models.BooleanField(default=True, verbose_name="En trial")
    is_active = models.BooleanField(default=True, verbose_name="Activo")

    # Información adicional
    comments = models.CharField(max_length=255, null=True, blank=True, verbose_name="Comentarios")

    created_on = models.DateField(auto_now_add=True, verbose_name="Fecha de creación")
    updated_on = models.DateField(auto_now=True, verbose_name="Fecha de actualización")

    auto_create_schema = True

    def delete(self, *args, **kwargs):
        self.delete_tenant(True)
        super().delete(*args, **kwargs)


class Domain(DomainMixin):
    pass