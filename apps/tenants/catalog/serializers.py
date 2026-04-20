from rest_framework import serializers
from .models import Category, Brand, Size, BrandVariant

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'

class SizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Size
        fields = '__all__'

class BrandSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Brand
        fields = '__all__'

class BrandVariantSerializer(serializers.ModelSerializer):
    brand = BrandSerializer(read_only=True)
    size = SizeSerializer(read_only=True)

    class Meta:
        model = BrandVariant
        fields = '__all__'