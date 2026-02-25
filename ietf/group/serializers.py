# Copyright The IETF Trust 2024-2026, All Rights Reserved
"""django-rest-framework serializers"""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from ietf.person.models import Email
from .models import Group, Role


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["acronym", "name", "type", "list_email"]


class AreaDirectorSerializer(serializers.Serializer):
    """Serialize an area director

    Works with Email or Role
    """

    email = serializers.SerializerMethodField()

    @extend_schema_field(serializers.EmailField)
    def get_email(self, instance: Email | Role):
        if isinstance(instance, Role):
            return instance.email.email_address()
        return instance.email_address()


class AreaSerializer(serializers.ModelSerializer):
    ads = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ["acronym", "name", "ads"]

    @extend_schema_field(AreaDirectorSerializer(many=True))
    def get_ads(self, area: Group):
        return AreaDirectorSerializer(
            area.ads if area.is_active else Role.objects.none(),
            many=True,
        ).data
