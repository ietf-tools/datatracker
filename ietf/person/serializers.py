# Copyright The IETF Trust 2024, All Rights Reserved
"""DRF Serializers"""

from rest_framework import serializers

from ietf.ietfauth.validators import is_allowed_address

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


class NewEmailSerializer(serializers.Serializer):
    """Serialize a new email address request"""
    address = serializers.EmailField(validators=[is_allowed_address])


class PersonSerializer(serializers.ModelSerializer):
    """Person serializer"""
    emails = EmailSerializer(many=True, source="email_set")

    class Meta:
        model = Person
        fields = ["id", "name", "emails"]
