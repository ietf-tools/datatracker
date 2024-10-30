# Copyright The IETF Trust 2024, All Rights Reserved
"""DRF Serializers"""

from rest_framework import serializers

from .models import Person


class PersonSerializer(serializers.ModelSerializer):
    """Person serializer"""

    class Meta:
        model = Person
        fields = ["id", "name"]
