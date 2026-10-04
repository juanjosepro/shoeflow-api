from rest_framework import viewsets
from .models import Category, Model, Size, ModelVariant
from .serializers import CategorySerializer, ModelSerializer, SizeSerializer, ModelVariantSerializer
from apps.common.mixins import OptionalPaginationMixin

class CategoryViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

class SizeViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    queryset = Size.objects.all()
    serializer_class = SizeSerializer

class ModelViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    # OBLIGATORIO: Este nombre de variable DEBE ser 'queryset'. 
    # DRF lo busca automáticamente para saber de qué tabla traer los registros.
    queryset = (
        Model.objects
        .select_related('category')
        .prefetch_related('variants__size')
        .order_by('-id')
    )
    
    # OBLIGATORIO: Este nombre de variable DEBE ser 'serializer_class'. 
    # DRF lo usa por debajo para transformar los datos entre JSON y objetos de Base de Datos.
    serializer_class = ModelSerializer

class ModelVariantViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    serializer_class = ModelVariantSerializer

    def get_queryset(self):
        queryset = ModelVariant.objects.select_related('model__category', 'size')
        # Capturamos el parámetro model_id de la URL (?model_id=1)
        model_id = self.request.query_params.get('model_id')
        
        if model_id:
            queryset = queryset.filter(model_id=model_id)
            
        return queryset
