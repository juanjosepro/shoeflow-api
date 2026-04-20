from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DozenViewSet, DozenAssignmentViewSet

router = DefaultRouter()
router.register(r'dozens', DozenViewSet, basename='production')
router.register(r'assignments', DozenAssignmentViewSet, basename='assignments')

urlpatterns = [
    path('', include(router.urls)),
]