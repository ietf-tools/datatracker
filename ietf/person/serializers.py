# Copyright The IETF Trust 2024, All Rights Reserved
"""DRF Serializers"""

from rest_framework import serializers

from .models import Email, Person


class EmailSerializer(serializers.ModelSerializer):
    """Email serializer"""
    address = serializers.EmailField()

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


class PersonSerializer(serializers.ModelSerializer):
    """Person serializer"""
    emails = EmailSerializer(many=True, source="email_set")

    class Meta:
        model = Person
        fields = ["id", "name", "emails"]
