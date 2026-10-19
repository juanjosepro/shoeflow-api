from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet,
    ColorViewSet,
    MaterialTypeViewSet,
    ModelViewSet,
    PlantTypeViewSet,
    SizeViewSet,
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='categories')
router.register(r'sizes', SizeViewSet, basename='sizes')
router.register(r'models', ModelViewSet, basename='models')
router.register(r'material-types', MaterialTypeViewSet, basename='material-types')
router.register(r'colors', ColorViewSet, basename='colors')
router.register(r'plant-types', PlantTypeViewSet, basename='plant-types')

urlpatterns = [
    path('', include(router.urls)),
]