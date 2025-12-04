# Copyright The IETF Trust 2024, All Rights Reserved
"""django-rest-framework serializers"""
from rest_framework import serializers

from .models import Group


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["acronym", "name", "type"]
