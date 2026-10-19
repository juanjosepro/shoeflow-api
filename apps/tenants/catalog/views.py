from django.db.models import ProtectedError
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from apps.common.mixins import OptionalPaginationMixin, ActiveFilterMixin

from .models import Category, Color, MaterialType, Model, PlantType, Size
from .serializers import (
    CategorySerializer,
    ColorSerializer,
    MaterialTypeSerializer,
    ModelSerializer,
    PlantTypeSerializer,
    SizeSerializer,
)

class CatalogViewSet(OptionalPaginationMixin, ActiveFilterMixin, viewsets.ModelViewSet):
    """Base del catálogo: si el registro está en uso responde 400 en vez de error 500."""
 
    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError(
                {"detail": "No se puede eliminar porque está en uso. Puedes desactivarlo en su lugar."}
            )

class CategoryViewSet(OptionalPaginationMixin, ActiveFilterMixin, viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class SizeViewSet(OptionalPaginationMixin, ActiveFilterMixin, viewsets.ModelViewSet):
    queryset = Size.objects.all()
    serializer_class = SizeSerializer


class ModelViewSet(OptionalPaginationMixin, ActiveFilterMixin, viewsets.ModelViewSet):
    # OBLIGATORIO: DRF busca 'queryset' y 'serializer_class' por esos nombres.
    queryset = Model.objects.select_related('category').order_by('-created_at')
    serializer_class = ModelSerializer

class MaterialTypeViewSet(CatalogViewSet):
    queryset = MaterialType.objects.all()
    serializer_class = MaterialTypeSerializer
 
 
class ColorViewSet(CatalogViewSet):
    queryset = Color.objects.all()
    serializer_class = ColorSerializer
 
 
class PlantTypeViewSet(CatalogViewSet):
    queryset = PlantType.objects.all()
    serializer_class = PlantTypeSerializer