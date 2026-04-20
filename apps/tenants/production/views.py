from rest_framework import viewsets
from .models import Dozen, DozenAssignment
from .serializers import DozenSerializer, DozenAssignmentSerializer
from .pagination import ProductionPagination

class DozenViewSet(viewsets.ModelViewSet):
    queryset = Dozen.objects.all()
    serializer_class = DozenSerializer
    pagination_class = ProductionPagination

class DozenAssignmentViewSet(viewsets.ModelViewSet):
    queryset = DozenAssignment.objects.all()
    serializer_class = DozenAssignmentSerializer
    pagination_class = None # Desactiva la paginación global solo aquí
