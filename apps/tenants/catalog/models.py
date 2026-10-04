from django.db import models
from django.core.validators import MinValueValidator

# ZAPATILLAS
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

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

#ADULTO
class Size(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Talla"
        verbose_name_plural = "Tallas"
        ordering = ["name"]

    def __str__(self):
        return self.name

# AIR
class Model(models.Model):
    # related_name = "apodo" que usa el PADRE para llamar a sus HIJOS
    #   category = Category.objects.get(name="Zapatillas")
    #   category.models.all()   ✅
    # El hijo NO lo usa, el hijo va con el nombre del campo:
    #   model = Model.objects.get(name="Air")
    #   model.category          ✅
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='models')
    name = models.CharField(max_length=100, unique=True)
    code_prefix = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Modelo"
        verbose_name_plural = "Modelos"
        ordering = ["name"]

    def __str__(self):
        status = "Activo" if self.is_active else "Inactivo"
        return f"{self.name} [{self.code_prefix}] | {status}"

# AIR ADULTO 50
class ModelVariant(models.Model):
    model = models.ForeignKey(Model, on_delete=models.PROTECT, related_name='variants')
    size = models.ForeignKey(Size, on_delete=models.PROTECT, related_name='variants')
    standard_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Variante del Modelo"
        verbose_name_plural = "Variantes de los Modelos"
        ordering = ["model", "size"]
        
        # ── LO QUE NO PUEDE REPETIRSE (IMPORTANTE) ──
        # En esta tabla NO puede existir dos veces la misma combinación de modelo + talla.
        # Si ya existe ("Air", "38"), no puedes crear otro igual.
        # Es una constraint a nivel de base de datos (como un índice único).
        constraints = [
            models.UniqueConstraint(
                fields=["model", "size"],
                name="unique_model_size",
            )
        ]

    def __str__(self):
        return f"{self.model.name} | {self.size.name} | S/ {self.standard_price}"
