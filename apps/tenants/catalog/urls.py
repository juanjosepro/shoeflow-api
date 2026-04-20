from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, BrandViewSet, SizeViewSet, BrandVariantViewSet

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='catalog')
router.register(r'brands', BrandViewSet, basename='brands')
router.register(r'sizes', SizeViewSet, basename='sizes')
router.register(r'variants', BrandVariantViewSet, basename='variants')

urlpatterns = [
    path('', include(router.urls)),
]