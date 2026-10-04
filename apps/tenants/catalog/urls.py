from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ModelViewSet, SizeViewSet, ModelVariantViewSet

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='categories')
router.register(r'sizes', SizeViewSet, basename='sizes')
router.register(r'models', ModelViewSet, basename='models')
router.register(r'variants', ModelVariantViewSet, basename='variants')

urlpatterns = [
    path('', include(router.urls)),
]