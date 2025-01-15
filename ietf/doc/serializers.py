# Copyright The IETF Trust 2024, All Rights Reserved
"""django-rest-framework serializers"""
from dataclasses import dataclass
from typing import Literal, ClassVar

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers, fields

from ietf.group.serializers import GroupSerializer
from ietf.name.serializers import StreamNameSerializer
from .models import Document, DocumentAuthor


class RfcAuthorSerializer(serializers.ModelSerializer):
    """Serializer for a DocumentAuthor in a response"""

    name = fields.CharField(source="person.plain_name")
    email = fields.EmailField(source="email.address", required=False)

    class Meta:
        model = DocumentAuthor
        fields = ["person", "name", "email", "affiliation", "country"]


@dataclass
class DocIdentifier:
    type: Literal["doi", "issn"]
    value: str


class DocIdentifierSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["doi", "issn"])
    value = serializers.CharField()


# This should become "type RfcStatusSlugT ..." when we drop pre-py3.12 support
# It should be "RfcStatusSlugT: TypeAlias ..." when we drop py3.9 support
RfcStatusSlugT = Literal[
    "standard", "bcp", "informational", "experimental", "historic", "unknown"
]


@dataclass
class RfcStatus:
    """Helper to extract the 'Status' from an RFC document for serialization"""

    slug: RfcStatusSlugT

    # Names that aren't just the slug itself. ClassVar annotation prevents dataclass from treating this as a field.
    fancy_names: ClassVar[dict[RfcStatusSlugT, str]] = {
        "standard": "standards track",
        "bcp": "best current practice",
    }

    # ClassVar annotation prevents dataclass from treating this as a field
    stdlevelname_slug_map: ClassVar[dict[str, RfcStatusSlugT]] = {
        "bcp": "bcp",
        "ds": "standard",  # ds is obsolete
        "exp": "experimental",
        "hist": "historic",
        "inf": "informational",
        "std": "standard",
        "ps": "standard",
        "unkn": "unknown",
    }

    # ClassVar annotation prevents dataclass from treating this as a field
    status_slugs: ClassVar[list[RfcStatusSlugT]] = sorted(
        set(stdlevelname_slug_map.values())
    )

    @property
    def name(self):
        return RfcStatus.fancy_names.get(self.slug, self.slug)

    @classmethod
    def from_document(cls, doc: Document):
        """Decide the status that applies to a document"""
        return cls(
            slug=(cls.stdlevelname_slug_map.get(doc.std_level.slug, "unknown")),
        )

    @classmethod
    def filter(cls, queryset, name, value: list[RfcStatusSlugT]):
        """Filter a queryset by status

        This is basically the inverse of the from_document() method. Given a status name, filter
        the queryset to those in that status. The queryset should be a Document queryset.
        """
        interesting_slugs = [
            stdlevelname_slug
            for stdlevelname_slug, status_slug in cls.stdlevelname_slug_map.items()
            if status_slug in value
        ]
        if len(interesting_slugs) == 0:
            return queryset.none()
        return queryset.filter(std_level__slug__in=interesting_slugs)


class RfcStatusSerializer(serializers.Serializer):
    """Status serializer for a Document instance"""

    slug = serializers.ChoiceField(choices=RfcStatus.status_slugs)
    name = serializers.CharField()

    def to_representation(self, instance: Document):
        return super().to_representation(instance=RfcStatus.from_document(instance))


class RelatedRfcSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="source.id")
    number = serializers.IntegerField(source="source.rfc_number")
    title = serializers.CharField(source="source.title")


class RfcMetadataSerializer(serializers.ModelSerializer):
    """Serialize metadata of an RFC"""

    number = serializers.IntegerField(source="rfc_number")
    published = serializers.DateField()
    status = RfcStatusSerializer(source="*")
    authors = RfcAuthorSerializer(many=True, source="documentauthor_set")
    group = GroupSerializer()
    area = GroupSerializer(source="group.area", required=False)
    stream = StreamNameSerializer()
    identifiers = fields.SerializerMethodField()
    obsoleted_by = RelatedRfcSerializer(many=True, read_only=True)
    updated_by = RelatedRfcSerializer(many=True, read_only=True)

    class Meta:
        model = Document
        fields = [
            "number",
            "title",
            "published",
            "status",
            "pages",
            "authors",
            "group",
            "area",
            "stream",
            "identifiers",
            "obsoleted_by",
            "updated_by",
            "abstract",
        ]

    @extend_schema_field(DocIdentifierSerializer(many=True))
    def get_identifiers(self, doc: Document):
        identifiers = []
        if doc.rfc_number:
            identifiers.append(
                DocIdentifier(type="doi", value=f"10.17487/RFC{doc.rfc_number:04d}")
            )
        return DocIdentifierSerializer(instance=identifiers, many=True).data


class RfcSerializer(RfcMetadataSerializer):
    """Serialize an RFC, including its metadata and text content if available"""

    text = serializers.CharField(allow_null=True)

    class Meta:
        model = RfcMetadataSerializer.Meta.model
        fields = RfcMetadataSerializer.Meta.fields + ["text"]
