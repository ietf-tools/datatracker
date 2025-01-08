# Copyright The IETF Trust 2025, All Rights Reserved
"""API views for django-rest-framework

This would normally be named api.py, but TastyPie creates an Api instance at
ietf.api that makes that awkward. For other apps, django-rest-framework API views
and viewsets should be put in api.py.
"""
from dataclasses import dataclass

from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.response import Response

from .serializers import MonitoringResultSerializer

import debug


@dataclass
class MonitoringResult:
    """Data class for a single monitoring result"""

    result_type: str
    result_value: int


class MonitoringViewSet(viewsets.ViewSet):
    """Monitoring / status check DRF API views"""

    permission_classes = []  # allow any for testing
    # api_key_endpoint = "ietf.api.core_api.monitoring"

    @extend_schema(
        responses=MonitoringResultSerializer(many=True),
    )
    def retrieve(self, request, pk):
        """Report status for service monitoring"""
        
        debug.show("pk")

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
        return Response(
            MonitoringResultSerializer(result, many=True).data,
        )
