from django.db import models

class Specialty(models.Model):
    """Una etapa del proceso. Las especialidades ACTIVAS son las etapas de la fábrica."""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    # Posición en el proceso: define el orden de las filas en el diálogo de
    order = models.PositiveSmallIntegerField(default=0)
    # False = la fábrica no usa esta etapa (no aparece en el diálogo masivo)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Especialidad"
        verbose_name_plural = "Especialidades"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Worker(models.Model):
    # Etapas que sabe hacer. El filtro es estricto: solo se le asignan estas.
    specialties = models.ManyToManyField(Specialty, related_name="workers", blank=True)
    names = models.CharField(max_length=100)
    dni = models.CharField(max_length=15, unique=True)
    phone = models.CharField(max_length=15, blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")
    # OJO: unique + default "" => dos trabajadores sin email chocan (pendiente de revisar)
    email = models.EmailField(unique=True, blank=True, default="")
    password = models.CharField(max_length=128, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Trabajador"
        verbose_name_plural = "Trabajadores"
        ordering = ["-created_at"]

    def __str__(self):
        specialties = ", ".join(self.specialties.values_list("name", flat=True))
        return f"{self.names} ({specialties or 'Sin especialidad'})"