# Copyright The IETF Trust 2025, All Rights Reserved
import datetime
from typing import Literal, Optional

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from ietf.doc.models import DocumentAuthor, Document, RelatedDocument
from ietf.person.models import Person


class PersonSerializer(serializers.ModelSerializer):
    picture = serializers.URLField(source="cdn_photo_url", read_only=True)

    class Meta:
        model = Person
        fields = ["id", "plain_name", "picture"]
        read_only_fields = ["id", "plain_name", "picture"]


class EmailPersonSerializer(serializers.Serializer):
    email = serializers.EmailField(source="address")
    person_pk = serializers.IntegerField(source="person.pk")
    name = serializers.CharField(source="person.name")
    last_name = serializers.CharField(source="person.last_name")
    initials = serializers.CharField(source="person.initials")


class LowerCaseEmailField(serializers.EmailField):

    def to_representation(self, value):
        return super().to_representation(value).lower()


class AuthorPersonSerializer(serializers.ModelSerializer):
    person_pk = serializers.IntegerField(source="pk", read_only=True)
    last_name = serializers.CharField()
    initials = serializers.CharField()
    email_addresses = serializers.ListField(
        source="email_set.all", child=LowerCaseEmailField()
    )

    class Meta:
        model = Person
        fields = ["person_pk", "name", "last_name", "initials", "email_addresses"]


class RfcWithAuthorsSerializer(serializers.ModelSerializer):
    authors = AuthorPersonSerializer(many=True)

    class Meta:
        model = Document
        fields = ["rfc_number", "authors"]


class DraftWithAuthorsSerializer(serializers.ModelSerializer):
    draft_name = serializers.CharField(source="name")
    authors = AuthorPersonSerializer(many=True)

    class Meta:
        model = Document
        fields = ["draft_name", "authors"]


class DocumentAuthorSerializer(serializers.ModelSerializer):
    """Serializer for a Person in a response"""

    plain_name = serializers.SerializerMethodField()

    class Meta:
        model = DocumentAuthor
        fields = ["person", "plain_name"]

    def get_plain_name(self, document_author: DocumentAuthor) -> str:
        return document_author.person.plain_name()


class FullDraftSerializer(serializers.ModelSerializer):
    source_format = serializers.SerializerMethodField()
    authors = DocumentAuthorSerializer(many=True, source="documentauthor_set")
    shepherd = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "name",
            "rev",
            "stream",
            "title",
            "pages",
            "source_format",
            "authors",
            "shepherd",
            "intended_std_level",
        ]

    def get_source_format(
        self, doc: Document
    ) -> Literal["unknown", "xml-v2", "xml-v3", "txt"]:
        submission = doc.submission()
        if submission is None:
            return "unknown"
        if ".xml" in submission.file_types:
            if submission.xml_version == "3":
                return "xml-v3"
            else:
                return "xml-v2"
        elif ".txt" in submission.file_types:
            return "txt"
        return "unknown"

    @extend_schema_field(OpenApiTypes.EMAIL)
    def get_shepherd(self, doc: Document) -> str:
        if doc.shepherd:
            return doc.shepherd.formatted_ascii_email()
        return ""


class DraftSerializer(FullDraftSerializer):
    class Meta:
        model = Document
        fields = [
            "id",
            "name",
            "rev",
            "stream",
            "title",
            "pages",
            "source_format",
            "authors",
        ]


class SubmittedToQueueSerializer(FullDraftSerializer):
    submitted = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "name",
            "stream",
            "submitted",
        ]

    def get_submitted(self, doc) -> Optional[datetime.datetime]:
        event = doc.sent_to_rfc_editor_event()
        return None if event is None else event.time


class OriginalStreamSerializer(serializers.ModelSerializer):
    stream = serializers.CharField(read_only=True, source="orig_stream_id")

    class Meta:
        model = Document
        fields = ["rfc_number", "stream"]


class ReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["id", "name"]
        read_only_fields = ["id", "name"]
