from django.core.validators import RegexValidator
from django.db import models


# Ej: Zapatillas
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        # ── CÓMO SE LLAMA EL MODELO EN EL ADMIN ──
        verbose_name = "Categoría"
        # ── CÓMO SE LLAMA EN PLURAL EN EL ADMIN ──
        verbose_name_plural = "Categorías"
        # ── ORDEN POR DEFECTO DE LAS CONSULTAS ──
        ordering = ["name"]

    def __str__(self):
        # ── REPRESENTACIÓN EN TEXTO DEL OBJETO ──
        # Define QUÉ SE MUESTRA cuando imprimes o referencias el objeto.
        # Sin esto verías: <Category: Category object (1)>
        # Con esto verás:   Zapatillas

        # Django lo usa en:
        #   - El admin (lista de categorías)
        #   - Los <select> cuando es ForeignKey de otro modelo
        #   - El shell al hacer print(categoria)
        #   - Templates con {{ categoria }}
        return self.name


# Ej: Adulto (38-42).
class Size(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)  # Ej: "38-42"
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Talla"
        verbose_name_plural = "Tallas"
        ordering = ["name"]

    def __str__(self):
        return self.name


# Ej: Air Max
class Model(models.Model):
    # related_name = "apodo" que usa el PADRE para llamar a sus HIJOS
    #   category = Category.objects.get(name="Zapatillas")
    #   category.models.all()   ✅
    # El hijo NO lo usa, el hijo va con el nombre del campo:
    #   model = Model.objects.get(name="Air")
    #   model.category          ✅
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="models")
    name = models.CharField(max_length=100, unique=True)
    code_prefix = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Modelo"
        verbose_name_plural = "Modelos"
        ordering = ["-created_at"]

    def __str__(self):
        status = "Activo" if self.is_active else "Inactivo"
        return f"{self.name} [{self.code_prefix}] | {status}"
 
# Ej: Cuero, Gamusa, Sintético
class MaterialType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        verbose_name = "Material"
        verbose_name_plural = "Materiales"
        ordering = ["-created_at"]
 
    def __str__(self):
        return self.name
 
 
# Ej: Blanco (#FFFFFF)
class Color(models.Model):
    name = models.CharField(max_length=100, unique=True)  # Como lo llama el taller: "Rojo", "Azul acero"
    # Para pintar la muestra en pantalla. Formato #RRGGBB (el serializer lo guarda en mayúsculas)
    hex_code = models.CharField(
        max_length=7,
        unique=True,
        validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Usa el formato #RRGGBB, por ejemplo #FF0000.")],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        verbose_name = "Color"
        verbose_name_plural = "Colores"
        ordering = ["-created_at"]
 
    def __str__(self):
        return f"{self.name} ({self.hex_code})"
 
 
# Ej: Goma, PVC, EVA (la planta es la suela)
class PlantType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        verbose_name = "Tipo de planta"
        verbose_name_plural = "Tipos de planta"
        ordering = ["-created_at"]
 
    def __str__(self):
        return self.name