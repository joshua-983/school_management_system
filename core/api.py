from rest_framework import viewsets
from .models import FeeCategory
from .serializers import FeeCategorySerializer

class FeeCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows fee categories to be viewed
    """
    queryset = FeeCategory.objects.all()
    serializer_class = FeeCategorySerializer