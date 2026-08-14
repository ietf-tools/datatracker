# Copyright The IETF Trust 2024, All Rights Reserved
"""django-rest-framework serializers"""
from rest_framework import serializers

from .models import StreamName


class StreamNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = StreamName
        fields = ["slug", "name", "desc"]
