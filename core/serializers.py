from rest_framework import serializers
from .models import FeeCategory

class FeeCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeCategory
        fields = ['id', 'name', 'description', 'is_mandatory', 'applies_to_all', 'class_levels']