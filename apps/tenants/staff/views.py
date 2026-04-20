from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import viewsets
from .models import Team, Worker
from .serializers import TeamSerializer, WorkerSerializer

class LogoutView(APIView):
    def post(self, request):
        # El token se identifica gracias a que el usuario ya viene autenticado
        request.user.auth_token.delete()
        return Response({"message": "Sesión cerrada correctamente."}, 
                        status=status.HTTP_200_OK)

class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer

    @property
    def pagination_class(self):
        if self.request.query_params.get('no_pagination') == 'true':
            return None
        
        return super().pagination_class

class WorkerViewSet(viewsets.ModelViewSet):
    queryset = Worker.objects.all()
    serializer_class = WorkerSerializer

    @property
    def pagination_class(self):
        if self.request.query_params.get('no_pagination') == 'true':
            return None

        return super().pagination_class
