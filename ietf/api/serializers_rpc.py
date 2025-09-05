# Copyright The IETF Trust 2025, All Rights Reserved
import datetime
from typing import Literal, Optional

from django.urls import reverse as urlreverse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from ietf.doc.models import DocumentAuthor, Document
from ietf.person.models import Person


class PersonSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(read_only=True)
    picture = serializers.URLField(source="cdn_photo_url", read_only=True)
    url = serializers.SerializerMethodField(
        help_text="relative URL for datatracker person page"
    )

    class Meta:
        model = Person
        fields = ["id", "plain_name", "email", "picture", "url"]
        read_only_fields = ["id", "plain_name", "email", "picture", "url"]

    @extend_schema_field(OpenApiTypes.URI)
    def get_url(self, object: Person):
        return urlreverse(
            "ietf.person.views.profile",
            kwargs={"email_or_name": object.email_address() or object.name},
        )


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
    # Redefine these fields so they don't pick up the regex validator patterns.
    # There seem to be some non-compliant drafts in the system! If this serializer
    # is used for a writeable view, the validation will need to be added back.
    name = serializers.CharField(max_length=255)
    title = serializers.CharField(max_length=255)

    # Other fields we need to add / adjust
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


class CreateDocumentAuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentAuthor
        fields = ["person", "email", "affiliation", "country"]


class CreateRfcSerializer(serializers.ModelSerializer):
    # fields based on ietf.sync.rfceditor.update_docs_from_rfc_index()
    authors = CreateDocumentAuthorSerializer(many=True)  # todo what about non-Person authors?

    class Meta:
        model = Document
        fields = [
            "rfc_number",
            "title",
            "authors",
            "stream",
            "group",
            "abstract",
            "pages",
            "words",
            "formal_languages",
            "std_level",
            "ad",
            "external_url",
            "uploaded_filename",
            "note",
        ]

    def create(self, validated_data):
        authors_data = validated_data.pop("authors")
        rfc = Document.objects.create(
            type_id="rfc",
            name=f"rfc{validated_data['rfc_number']}",
            **validated_data,
        )
        for order, author_data in enumerate(authors_data):
            rfc.documentauthor_set.create(
                order=order,
                **author_data,
            )


class RfcPubNotificationSerializer(serializers.Serializer):
    published = serializers.DateTimeField(default_timezone=datetime.timezone.utc)
    draft_name = serializers.CharField(allow_blank=True)
    draft_rev = serializers.CharField(allow_blank=True)
    rfc = CreateRfcSerializer()


class NotificationAckSerializer(serializers.Serializer):
    message = serializers.CharField(default="ack")
