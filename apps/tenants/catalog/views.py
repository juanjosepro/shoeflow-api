from rest_framework import viewsets
from .models import Category, Brand, Size, BrandVariant
from .serializers import CategorySerializer, BrandSerializer, SizeSerializer, BrandVariantSerializer

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    @property
    def pagination_class(self):
        if self.request.query_params.get('no_pagination') == 'true':
            return None
        
        return super().pagination_class

class SizeViewSet(viewsets.ModelViewSet):
    queryset = Size.objects.all()
    serializer_class = SizeSerializer

    @property
    def pagination_class(self):
        if self.request.query_params.get('no_pagination') == 'true':
            return None
        
        return super().pagination_class

class BrandViewSet(viewsets.ModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer

    @property
    def pagination_class(self):
        if self.request.query_params.get('no_pagination') == 'true':
            return None
        
        return super().pagination_class

class BrandVariantViewSet(viewsets.ModelViewSet):
    queryset = BrandVariant.objects.all()
    serializer_class = BrandVariantSerializer

    @property
    def pagination_class(self):
        if self.request.query_params.get('no_pagination') == 'true':
            return None
        
        return super().pagination_class
