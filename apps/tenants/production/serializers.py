from rest_framework import serializers
from .models import Dozen, DozenAssignment
from apps.tenants.staff.serializers import WorkerSerializer
from apps.tenants.catalog.serializers import BrandVariantSerializer

class DozenSerializer(serializers.ModelSerializer):
    brand_variant = BrandVariantSerializer(read_only=True)
    class Meta:
        model = Dozen
        fields = '__all__'

class DozenAssignmentSerializer(serializers.ModelSerializer):
    worker = WorkerSerializer(read_only=True)
    dozen = DozenSerializer(read_only=True)
    week_identifier = serializers.ReadOnlyField()
    week_label = serializers.ReadOnlyField()

    total_payment = serializers.ReadOnlyField(source='calculate_payment')
    class Meta:
        model = DozenAssignment
        fields = [
            'id', 'worker', 'dozen', 'status', 
            'week_identifier', 'week_label', 'total_payment',
            'created_at', 'settlement'
        ]