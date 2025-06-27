# Copyright The IETF Trust 2025, All Rights Reserved
from rest_framework import serializers

from ietf.person.models import Person


class PersonSerializer(serializers.ModelSerializer):
    picture = serializers.URLField(source="cdn_photo_url", read_only=True)

    class Meta:
        model = Person
        fields = ["id", "plain_name", "picture"]
        read_only_fields = ["id", "plain_name", "picture"]
