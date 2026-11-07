from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.serializers import ModelSerializer
from django.contrib.auth import get_user_model
from rest_framework import serializers
from django_tenants.utils import get_tenant_model

User = get_user_model()

class LogoutView(APIView):
    def post(self, request):
        # The token is identified because the user is already authenticated.
        request.user.auth_token.delete()
        return Response({"message": "Logged out successfully."}, 
                        status=status.HTTP_200_OK)

# A quick serializer for the user
class CurrentUserSerializer(ModelSerializer):
    tenant = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'tenant']

    def get_tenant(self, obj):
        request = self.context.get('request')
        tenant = getattr(request, 'tenant', None)

        if not tenant:
            return None

        return {
            'schema_name': tenant.schema_name,
            'business_name': tenant.business_name,
            'business_legal_name': tenant.business_legal_name,
            'business_ruc': tenant.business_ruc,
            'business_address': tenant.business_address,
            'business_phone': tenant.business_phone,
            'business_email': tenant.business_email,
            'owner_names': tenant.owner_names,
            'owner_last_names': tenant.owner_last_names,
            'owner_dni': tenant.owner_dni,
            'owner_email': tenant.owner_email,
            'owner_phone': tenant.owner_phone,
            'comments': tenant.comments,
            'created_on': tenant.created_on,
            'updated_on': tenant.updated_on,
        }
# The view
class CurrentUserView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CurrentUserSerializer

    def get_object(self):
        return self.request.user