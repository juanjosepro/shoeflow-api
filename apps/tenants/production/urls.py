from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DozenViewSet, DozenStageAssignmentViewSet, DozenMetadataView

router = DefaultRouter()
router.register(r'dozens', DozenViewSet, basename='production')
router.register(r'assignments', DozenStageAssignmentViewSet, basename='assignments')

urlpatterns = [
    path('dozen-metadata/', DozenMetadataView.as_view(), name='dozen-metadata'),
    path('', include(router.urls)),
]