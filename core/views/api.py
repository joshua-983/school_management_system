from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import JsonResponse
import json
from decimal import Decimal
from django.core.serializers.json import DjangoJSONEncoder

from .base_views import *
from ..models import FeeCategory
from ..serializers import FeeCategorySerializer

@api_view(['GET'])
def fee_category_detail(request, pk):
    try:
        category = FeeCategory.objects.get(pk=pk)
        serializer = FeeCategorySerializer(category)
        return Response(serializer.data)
    except FeeCategory.DoesNotExist:
        return Response(status=404)

# Other API views if any