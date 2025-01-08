# Copyright The IETF Trust 2025, All Rights Reserved
"""Serializers for django-rest-framework"""
from rest_framework import serializers


class MonitoringResultSerializer(serializers.Serializer):
    """Serialize a MonitoringResult"""

    result_type = serializers.CharField()
    result_value = serializers.IntegerField()
