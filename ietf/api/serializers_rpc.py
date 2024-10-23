# Copyright The IETF Trust 2024, All Rights Reserved
#
import datetime
from typing import Literal, Optional

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from ietf.doc.models import DocumentAuthor, Document
from ietf.person.models import Person


class PersonBatchSerializer(serializers.Serializer):
    person_ids = serializers.ListField(child=serializers.IntegerField())


class PersonSerializer(serializers.ModelSerializer):
    """Serializer for a Person in a response"""

    plain_name = serializers.SerializerMethodField()

    class Meta:
        model = Person
        fields = ["id", "plain_name"]

    def get_plain_name(self, person) -> str:
        return person.plain_name()


class DocumentAuthorSerializer(serializers.ModelSerializer):
    """Serializer for a DocumentAuthor in a response"""

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


class DemoPersonCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)


class DemoPersonSerializer(serializers.ModelSerializer):
    person_pk = serializers.IntegerField(source="pk")

    class Meta:
        model = Person
        fields = ["user_id", "person_pk"]


class DemoDraftCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=True)
    stream_id = serializers.CharField(default="ietf")
    rev = serializers.CharField(default=None)
    states = serializers.DictField(child=serializers.CharField(), default=None)


class DemoDraftSerializer(serializers.ModelSerializer):
    doc_id = serializers.IntegerField(source="pk")

    class Meta:
        model = Document
        fields = ["doc_id", "name"]
