# Copyright The IETF Trust 2024-2026, All Rights Reserved
"""django-rest-framework serializers"""

from rest_framework import serializers

from .models import Group


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["acronym", "name", "type", "list_email"]


class AreaDirectorSerializer(serializers.Serializer):
    """Serialize an area director

    Works with Email or Role
    """

    email = serializers.EmailField(source="formatted_email")


class AreaSerializer(serializers.ModelSerializer):
    ads = AreaDirectorSerializer(many=True, read_only=True)

    class Meta:
        model = Group
        fields = ["acronym", "name", "type", "ads"]
