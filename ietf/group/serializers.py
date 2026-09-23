# Copyright The IETF Trust 2024-2026, All Rights Reserved
"""django-rest-framework serializers"""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from ietf.name.models import GroupStateName
from ietf.person.models import Email
from .models import Group, Role


class GroupStateField(serializers.ChoiceField):
    """API representation of group state

    Only represents "active" and "conclude". The "bof-conc" state is treated as
    "conclude". Any other state is represented as "other".
    """

    def __init__(self, **kwargs):
        if not kwargs.pop("read_only", True):
            raise RuntimeError("GroupStateField is read-only")
        choices = ("active", "conclude", "other")
        super().__init__(choices, read_only=True, **kwargs)

    def to_representation(self, value):
        if not isinstance(value, GroupStateName):
            raise ValueError(f"value is a {type(value)}, not a GroupStateName")
        return {
            "active": "active",
            "bof-conc": "conclude",
            "conclude": "conclude",
        }.get(value.slug, "other")


class GroupSerializer(serializers.ModelSerializer):
    state = GroupStateField(allow_null=True)

    class Meta:
        model = Group
        fields = ["acronym", "name", "type", "state", "list_email"]


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
