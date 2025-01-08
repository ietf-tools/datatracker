# Copyright The IETF Trust 2025, All Rights Reserved
"""API views for django-rest-framework

This would normally be named api.py, but TastyPie creates an Api instance at
ietf.api that makes that awkward. For other apps, django-rest-framework API views
and viewsets should be put in api.py.
"""
from dataclasses import dataclass

from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import MonitoringResultSerializer


@dataclass
class MonitoringResult:
    """Data class for a single monitoring result"""

    result_type: str
    result_value: int


class MonitoringView(APIView):
    """Monitoring / status check DRF API view"""

    api_key_endpoint = "ietf.api.core_api.monitoring"

    @extend_schema(
        responses=MonitoringResultSerializer(many=True),
    )
    def get(self, request, flavor, format=None):
        """Report monitoring status"""
        if flavor != "nfs":
            raise Http404()

        # ersatz status to report
        result = [
            MonitoringResult(
                result_type="online",
                result_value=1,  # 0 = false, 1 = true
            ),
            MonitoringResult(
                result_type="latency",
                result_value=17,  # milliseconds? minutes? Use your imagination
            ),
        ]

        serializer = MonitoringResultSerializer(result, many=True)
        return Response(serializer.data)
