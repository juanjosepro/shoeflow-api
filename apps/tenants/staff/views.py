from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets
from .models import Team, Worker
from .serializers import TeamSerializer, WorkerSerializer

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from apps.common.mixins import OptionalPaginationMixin

class TeamViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer

class WorkerViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    queryset = Worker.objects.all()
    serializer_class = WorkerSerializer