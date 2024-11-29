# Copyright The IETF Trust 2024, All Rights Reserved
"""django-rest-framework serializers"""
from dataclasses import dataclass
from typing import Literal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers, fields

from .models import Document, DocumentAuthor


class RfcAuthorSerializer(serializers.ModelSerializer):
    """Serializer for a DocumentAuthor in a response"""
    name = fields.CharField(source="person.plain_name")
    email = fields.EmailField(source="email.address", required=False)

    class Meta:
        model = DocumentAuthor
        fields = ["person", "name", "email", "affiliation", "country"]

    # @extend_schema_field(fields.CharField)
    # def get_name(self, document_author: DocumentAuthor) -> str:
    #     """Name that should be shown for the RFC author list"""
    #     return document_author.person.plain_name()


@dataclass
class DocIdentifier:
    type: Literal["doi", "issn"]
    value: str


class DocIdentifierSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["doi", "issn"])
    value = serializers.CharField()


class RfcMetadataSerializer(serializers.ModelSerializer):
    # all fields are stand-ins
    # updates = serializers.CharField()
    # date = serializers.CharField()
    authors = RfcAuthorSerializer(many=True, source="documentauthor_set")
    # identifiers = fields.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "name",
            "title",
            # "date",
            "pages",
            "authors",
            "group",
            # "area",
            "stream",
            # "identifiers",
        ]

    @extend_schema_field(DocIdentifierSerializer)
    def get_identifiers(self, doc: Document):
        identifiers = []
        if doc.rfc_number:
            identifiers.append(DocIdentifier(type="doi", value=f"10.17487/RFC{doc.rfc_number:04d}"))
        return DocIdentifierSerializer(data=identifiers, many=True)
