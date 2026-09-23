# Copyright The IETF Trust 2024-2026, All Rights Reserved
"""django-rest-framework serializers"""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from ietf.name.models import GroupStateName
from ietf.person.models import Email
from .models import Group, Role




class GroupSerializer(serializers.ModelSerializer):
    state = serializers.SerializerMethodField()

    GROUP_STATE_CHOICES = ("active", "concluded", "other")  # simplified group states

    class Meta:
        model = Group
        fields = ["acronym", "name", "type", "state", "list_email"]

    @extend_schema_field(serializers.ChoiceField(choices=GROUP_STATE_CHOICES))
    def get_state(self, group: Group):
        if group.state_id is None:
            return "other"
        return {
            "active": "active",
            "bof-conc": "concluded",
            "conclude": "concluded",
        }.get(group.state_id, "other")


class AreaDirectorSerializer(serializers.Serializer):
    """Serialize an area director

    Works with Email or Role
    """

    name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField)
    def get_name(self, instance: Email | Role):
        person = getattr(instance, "person", None)
        return person.plain_name() if person else None

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
