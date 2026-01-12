# Copyright The IETF Trust 2024-2026, All Rights Reserved
"""django-rest-framework serializers"""

from dataclasses import dataclass
from typing import Literal, ClassVar

from django.db.models.manager import BaseManager
from django.db.models.query import QuerySet
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from ietf.group.serializers import GroupSerializer
from ietf.name.serializers import StreamNameSerializer
from .models import Document, DocumentAuthor, RfcAuthor


class RfcAuthorSerializer(serializers.ModelSerializer):
    """Serializer for a DocumentAuthor in a response"""
    datatracker_person_path = serializers.URLField(
        source="person.get_absolute_url",
        required=False,
        help_text="URL for person link (relative to datatracker base URL)",
    )

    class Meta:
        model = RfcAuthor
        fields = [
            "titlepage_name",
            "is_editor",
            "person",
            "email",  # relies on email.pk being email.address
            "affiliation",
            "country",
            "datatracker_person_path",
        ]

    def to_representation(self, instance):
        """instance -> primitive data types
        
        Translates a DocumentAuthor into an equivalent RfcAuthor we can use the same
        serializer for either type.
        """
        if isinstance(instance, DocumentAuthor):
            # create a non-persisted RfcAuthor as a shim - do not save it!
            document_author = instance
            instance = RfcAuthor(
                titlepage_name=document_author.person.plain_name(),
                is_editor=False,
                person=document_author.person,
                email=document_author.email,
                affiliation=document_author.affiliation,
                country=document_author.country,
                order=document_author.order,
            )
        return super().to_representation(instance)

    def validate(self, data):
        email = data.get("email")
        if email is not None:
            person = data.get("person")
            if person is None:
                raise serializers.ValidationError(
                    {
                        "email": "cannot have an email without a person",
                    },
                    code="email-without-person",
                )
            if email.person_id != person.pk:
                raise serializers.ValidationError(
                    {
                        "email": "email must belong to person",
                    },
                    code="email-person-mismatch",
                )
        return data


@dataclass
class DocIdentifier:
    type: Literal["doi", "issn"]
    value: str


class DocIdentifierSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["doi", "issn"])
    value = serializers.CharField()


type RfcStatusSlugT = Literal[
    "std", "ps", "ds", "bcp", "inf", "exp", "hist", "unkn", "not-issued",
]


@dataclass
class RfcStatus:
    """Helper to extract the 'Status' from an RFC document for serialization"""

    slug: RfcStatusSlugT

    # Names that aren't just the slug itself. ClassVar annotation prevents dataclass from treating this as a field.
    fancy_names: ClassVar[dict[RfcStatusSlugT, str]] = {
        "std": "internet standard",
        "ps": "proposed standard",
        "ds": "draft standard",
        "bcp": "best current practice",
        "inf": "informational",
        "exp": "experimental",
        "hist": "historic",
        "unkn": "unknown",
    }

    # ClassVar annotation prevents dataclass from treating this as a field
    stdlevelname_slug_map: ClassVar[dict[str, RfcStatusSlugT]] = {
        "bcp": "bcp",
        "ds": "ds",
        "exp": "exp",
        "hist": "hist",
        "inf": "inf",
        "std": "std",
        "ps": "ps",
        "unkn": "unkn",
    }

    # ClassVar annotation prevents dataclass from treating this as a field
    status_slugs: ClassVar[list[RfcStatusSlugT]] = sorted(
        # TODO implement "not-issued" RFCs
        set(stdlevelname_slug_map.values()) | {"not-issued"}
    )

    @property
    def name(self):
        return RfcStatus.fancy_names.get(self.slug, self.slug)

    @classmethod
    def from_document(cls, doc: Document):
        """Decide the status that applies to a document"""
        return cls(
            slug=(cls.stdlevelname_slug_map.get(doc.std_level.slug, "unkn")),
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


class RelatedDraftSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="source.id")
    name = serializers.CharField(source="source.name")
    title = serializers.CharField(source="source.title")


class RelatedRfcSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="target.id")
    number = serializers.IntegerField(source="target.rfc_number")
    title = serializers.CharField(source="target.title")


class ReverseRelatedRfcSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="source.id")
    number = serializers.IntegerField(source="source.rfc_number")
    title = serializers.CharField(source="source.title")


class ContainingSubseriesSerializer(serializers.Serializer):
    name = serializers.CharField(source="source.name")
    type = serializers.CharField(source="source.type_id")


class RfcMetadataSerializer(serializers.ModelSerializer):
    """Serialize metadata of an RFC"""

    RFC_FORMATS = ("xml", "txt", "html", "htmlized", "pdf", "ps")

    number = serializers.IntegerField(source="rfc_number")
    published = serializers.DateField()
    status = RfcStatusSerializer(source="*")
    authors = serializers.SerializerMethodField()
    group = GroupSerializer()
    area = GroupSerializer(source="group.area", required=False)
    stream = StreamNameSerializer()
    identifiers = serializers.SerializerMethodField()
    draft = serializers.SerializerMethodField()
    obsoletes = RelatedRfcSerializer(many=True, read_only=True)
    obsoleted_by = ReverseRelatedRfcSerializer(many=True, read_only=True)
    updates = RelatedRfcSerializer(many=True, read_only=True)
    updated_by = ReverseRelatedRfcSerializer(many=True, read_only=True)
    subseries = ContainingSubseriesSerializer(many=True, read_only=True)
    see_also = serializers.ListField(child=serializers.CharField(), read_only=True)
    formats = serializers.MultipleChoiceField(choices=RFC_FORMATS)
    keywords = serializers.ListField(child=serializers.CharField(), read_only=True)
    errata = serializers.ListField(child=serializers.CharField(), read_only=True)

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
            "obsoletes",
            "obsoleted_by",
            "updates",
            "updated_by",
            "subseries",
            "see_also",
            "draft",
            "abstract",
            "formats",
            "keywords",
            "errata",
        ]


    @extend_schema_field(RfcAuthorSerializer(many=True))
    def get_authors(self, doc: Document):
        # If doc has any RfcAuthors, use those, otherwise fall back to DocumentAuthors
        author_queryset: QuerySet[RfcAuthor] | QuerySet[DocumentAuthor] = (
            doc.rfcauthor_set.all()
            if doc.rfcauthor_set.exists()
            else doc.documentauthor_set.all()
        )
        # RfcAuthorSerializer can deal with DocumentAuthor instances
        return RfcAuthorSerializer(
            instance=author_queryset,
            many=True,
        ).data

    @extend_schema_field(DocIdentifierSerializer(many=True))
    def get_identifiers(self, doc: Document):
        identifiers = []
        if doc.rfc_number:
            identifiers.append(
                DocIdentifier(type="doi", value=f"10.17487/RFC{doc.rfc_number:04d}")
            )
        return DocIdentifierSerializer(instance=identifiers, many=True).data

    @extend_schema_field(RelatedDraftSerializer)
    def get_draft(self, object):
        try:
            related_doc = object.drafts[0]
        except IndexError:
            return None
        return RelatedDraftSerializer(related_doc).data


class RfcSerializer(RfcMetadataSerializer):
    """Serialize an RFC, including its metadata and text content if available"""

    text = serializers.CharField(allow_null=True)

    class Meta:
        model = RfcMetadataSerializer.Meta.model
        fields = RfcMetadataSerializer.Meta.fields + ["text"]


class SubseriesContentListSerializer(serializers.ListSerializer):
    """ListSerializer that gets its object from item.target"""

    def to_representation(self, data):
        """
        List of object instances -> List of dicts of primitive datatypes.
        """
        # Dealing with nested relationships, data can be a Manager,
        # so, first get a queryset from the Manager if needed
        iterable = data.all() if isinstance(data, BaseManager) else data
        # Serialize item.target instead of item itself
        return [self.child.to_representation(item.target) for item in iterable]


class SubseriesContentSerializer(RfcMetadataSerializer):
    """Serialize RFC contained in a subseries doc"""

    class Meta(RfcMetadataSerializer.Meta):
        list_serializer_class = SubseriesContentListSerializer


class SubseriesDocSerializer(serializers.ModelSerializer):
    """Serialize a subseries document (e.g., a BCP or STD)"""

    contents = SubseriesContentSerializer(many=True)

    class Meta:
        model = Document
        fields = [
            "name",
            "type",
            "contents",
        ]
