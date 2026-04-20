from django.db import models

# ZAPATILLAS
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name
#ADULTO
class Size(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

# AIR
class Brand(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='brands')
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

# AIR ADULTO 50
class BrandVariant(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='brand_variants')
    size = models.ForeignKey(Size, on_delete=models.CASCADE, related_name='brand_variants')
    standard_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.brand.name} - {self.size.name} - S/ {self.standard_price}"
