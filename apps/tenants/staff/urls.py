from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TeamViewSet, WorkerViewSet

router = DefaultRouter()
router.register(r'teams', TeamViewSet, basename='staff')
router.register(r'workers', WorkerViewSet, basename='workers')

urlpatterns = [
    path('', include(router.urls)),
]