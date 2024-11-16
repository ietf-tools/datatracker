# Copyright The IETF Trust 2024, All Rights Reserved
"""DRF Serializers"""

from rest_framework import serializers

from .models import Email, Person


class EmailSerializer(serializers.ModelSerializer):
    """Email serializer for read/update"""

    address = serializers.EmailField(read_only=True)

    class Meta:
        model = Email
        fields = [
            "person",
            "address",
            "primary",
            "active",
            "origin",
        ]
        read_only_fields = ["person", "address", "origin"]


class EmailCreationSerializer(serializers.ModelSerializer):
    """Email serializer for creation only"""
    address = serializers.EmailField()

    class Meta:
        model = Email
        fields = [
            "address",
            "primary",
            "active",
        ]
        # Because address is the primary key, it's read-only by default.
        # Use extra_kwargs to force it into the writeable parameter list.
        # This can go away if we move to a surrogate primary key for Email.
        extra_kwargs = {"address": {}}


class PersonSerializer(serializers.ModelSerializer):
    """Person serializer"""
    emails = EmailSerializer(many=True, source="email_set")

    class Meta:
        model = Person
        fields = ["id", "name", "emails"]
