# Copyright The IETF Trust 2025, All Rights Reserved
import datetime
from pathlib import Path
from typing import Literal, Optional

from django.db import transaction
from django.urls import reverse as urlreverse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from ietf.doc.expire import move_draft_files_to_archive
from ietf.doc.models import DocumentAuthor, Document, RelatedDocument, State, DocEvent
from ietf.doc.serializers import RfcAuthorSerializer
from ietf.doc.utils import default_consensus, prettify_std_name, update_action_holders
from ietf.group.models import Group
from ietf.name.models import StreamName, StdLevelName, FormalLanguageName
from ietf.person.models import Person
from ietf.utils import log


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
    consensus = serializers.SerializerMethodField()

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
            "consensus",
        ]

    def get_consensus(self, doc: Document) -> Optional[bool]:
        return default_consensus(doc)

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
    consensus = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "name",
            "stream",
            "submitted",
            "consensus",
        ]

    def get_submitted(self, doc) -> Optional[datetime.datetime]:
        event = doc.sent_to_rfc_editor_event()
        return None if event is None else event.time
    
    def get_consensus(self, doc) -> Optional[bool]:
        return default_consensus(doc)


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


class RfcPubSerializer(serializers.ModelSerializer):
    # publication-related fields
    published = serializers.DateTimeField(default_timezone=datetime.timezone.utc)
    draft_name = serializers.RegexField(
        required=False, regex=r"^draft-[a-zA-Z0-9-]+$"
    )
    draft_rev = serializers.RegexField(
        required=False, regex=r"^[0-9][0-9]$"
    )

    # fields on the RFC Document that need tweaking from ModelSerializer defaults
    rfc_number = serializers.IntegerField(min_value=1, required=True)
    group = serializers.SlugRelatedField(
        slug_field="acronym", queryset=Group.objects.all(), required=False
    )
    stream = serializers.PrimaryKeyRelatedField(
        queryset=StreamName.objects.filter(used=True)
    )
    formal_languages = serializers.PrimaryKeyRelatedField(
        many=True,
        required=False,
        queryset=FormalLanguageName.objects.filter(used=True),
        help_text=(
            "formal languages used in RFC (defaults to those from draft, send empty"
            "list to override)"
        )
    )
    std_level = serializers.PrimaryKeyRelatedField(
        queryset=StdLevelName.objects.filter(used=True),
    )
    ad = serializers.PrimaryKeyRelatedField(
        queryset=Person.objects.all(),
        allow_null=True,
        required=False,
    )
    obsoletes = serializers.SlugRelatedField(
        many=True,
        required=False,
        slug_field="rfc_number",
        queryset=Document.objects.filter(type_id="rfc"),
    )
    updates = serializers.SlugRelatedField(
        many=True,
        required=False,
        slug_field="rfc_number",
        queryset=Document.objects.filter(type_id="rfc"),
    )
    subseries = serializers.ListField(
        child=serializers.RegexField(
            required=False,
            # pattern: no leading 0, finite length (arbitrarily set to 5 digits)
            regex=r"^(bcp|std|fyi)[1-9][0-9]{0,4}$", 
        )
    )
    authors = RfcAuthorSerializer(many=True)

    class Meta:
        model = Document
        fields = [
            "published",
            "draft_name",
            "draft_rev",
            "rfc_number",
            "title",
            "authors",
            "group",
            "stream",
            "abstract",
            "pages",
            "words",
            "formal_languages",
            "std_level",
            "ad",
            "note",
            "obsoletes",
            "updates",
            "subseries",
        ]

    def validate(self, data):
        if "draft_name" in data or "draft_rev" in data:
            if "draft_name" not in data:
                raise serializers.ValidationError(
                    {"draft_name": "Missing draft_name"},
                    code="invalid-draft-spec",
                ) 
            if "draft_rev" not in data:
                raise serializers.ValidationError(
                    {"draft_rev": "Missing draft_rev"},
                    code="invalid-draft-spec",
                )
        return data

    def create(self, validated_data):
        """Publish an RFC"""
        published = validated_data.pop("published")
        draft_name = validated_data.pop("draft_name", None)
        draft_rev = validated_data.pop("draft_rev", None)
        obsoletes = validated_data.pop("obsoletes", [])
        updates = validated_data.pop("updates", [])
        subseries = validated_data.pop("subseries", [])

        system_person = Person.objects.get(name="(System)")

        # If specified, retrieve draft and extract RFC default values from it
        if draft_name is None:
            draft = None
            defaults_from_draft = {
                "group": Group.objects.get(acronym="none", type_id="individ"),
            }
        else:
            # validation enforces that draft_name and draft_rev are both present
            draft = Document.objects.filter(
                type_id="draft",
                name=draft_name,
                rev=draft_rev,
            ).first()
            if draft is None:
                raise serializers.ValidationError(
                    {
                        "draft_name": "No such draft",
                        "draft_rev": "No such draft",
                    },
                    code="invalid-draft"
                )
            elif draft.get_state_slug() == "rfc":
                raise serializers.ValidationError(
                    {
                        "draft_name": "Draft already published as RFC",
                    },
                    code="already-published-draft",
                )
            defaults_from_draft = {
                "ad": draft.ad,
                "formal_languages": draft.formal_languages.all(),
                "group": draft.group,
                "note": draft.note,
            }

        # Transaction to clean up if something fails
        with transaction.atomic():
            # create rfc, letting validated request data override draft defaults
            rfc = self._create_rfc(defaults_from_draft | validated_data)
            DocEvent.objects.create(
                doc=rfc,
                rev=rfc.rev,
                type="published_rfc",
                time=published,
                by=system_person,
                desc="RFC published",
            )
            rfc.set_state(State.objects.get(used=True, type_id="rfc", slug="published"))
    
            # create updates / obsoletes relations
            for obsoleted_rfc_pk in obsoletes:
                RelatedDocument.objects.get_or_create(
                    source=rfc, target=obsoleted_rfc_pk, relationship_id="obs"
                )
            for updated_rfc_pk in updates:
                RelatedDocument.objects.get_or_create(
                    source=rfc, target=updated_rfc_pk, relationship_id="updates"
                )
        
            # create subseries relations
            for subseries_doc_name in subseries:
                ss_slug = subseries_doc_name[:3]
                subseries_doc, ss_doc_created = Document.objects.get_or_create(
                    type_id=ss_slug, name=subseries_doc_name
                )
                if ss_doc_created:
                    subseries_doc.docevent_set.create(
                        type=f"{ss_slug}_doc_created",
                        by=system_person,
                        desc=f"Created {subseries_doc_name} via publication of {rfc.name}",
                    )
                _, ss_rel_created = subseries_doc.relateddocument_set.get_or_create(
                    relationship_id="contains", target=rfc
                )
                if ss_rel_created:
                    subseries_doc.docevent_set.create(
                        type="sync_from_rfc_editor",
                        by=system_person,
                        desc=f"Added {rfc.name} to {subseries_doc.name}",
                    )
                    rfc.docevent_set.create(
                        type="sync_from_rfc_editor",
                        by=system_person,
                        desc=f"Added {rfc.name} to {subseries_doc.name}",
                    )
    
    
            # create relation with draft and update draft state
            if draft is not None:
                draft_changes = []
                draft_events = []
                if draft.get_state_slug() != "rfc":
                    draft.set_state(
                        State.objects.get(used=True, type="draft", slug="rfc")
                    )
                    move_draft_files_to_archive(draft, draft.rev)
                    draft_changes.append(f"changed state to {draft.get_state()}")
    
                r, created_relateddoc = RelatedDocument.objects.get_or_create(
                    source=draft, target=rfc, relationship_id="became_rfc",
                )
                if created_relateddoc:
                    change = "created {rel_name} relationship between {pretty_draft_name} and {pretty_rfc_name}".format(
                        rel_name=r.relationship.name.lower(),
                        pretty_draft_name=prettify_std_name(draft_name),
                        pretty_rfc_name=prettify_std_name(rfc.name),
                    )
                    draft_changes.append(change)
    
                # Always set the "draft-iesg" state. This state should be set for all drafts, so
                # log a warning if it is not set. What should happen here is that ietf stream
                # RFCs come in as "rfcqueue" and are set to "pub" when they appear in the RFC index.
                # Other stream documents should normally be "idexists" and be left that way. The
                # code here *actually* leaves "draft-iesg" state alone if it is "idexists" or "pub",
                # and changes any other state to "pub". If unset, it changes it to "idexists".
                # This reflects historical behavior and should probably be updated, but a migration
                # of existing drafts (and validation of the change) is needed before we change the
                # handling.
                prev_iesg_state = draft.get_state("draft-iesg")
                if prev_iesg_state is None:
                    log.log(f'Warning while processing {rfc.name}: {draft.name} has no "draft-iesg" state')
                    new_iesg_state = State.objects.get(type_id="draft-iesg", slug="idexists")
                elif prev_iesg_state.slug not in ("pub", "idexists"):
                    if prev_iesg_state.slug != "rfcqueue":
                        log.log(
                            'Warning while processing {}: {} is in "draft-iesg" state {} (expected "rfcqueue")'.format(
                                rfc.name, draft.name, prev_iesg_state.slug
                            )
                        )
                    new_iesg_state = State.objects.get(type_id="draft-iesg", slug="pub")
                else:
                    new_iesg_state = prev_iesg_state
        
                if new_iesg_state != prev_iesg_state:
                    draft.set_state(new_iesg_state)
                    draft_changes.append(f"changed {new_iesg_state.type.label} to {new_iesg_state}")
                    e = update_action_holders(draft, prev_iesg_state, new_iesg_state)
                    if e:
                        draft_events.append(e)
    
                # If the draft and RFC streams agree, move draft to "pub" stream state. If not, complain.
                if draft.stream != rfc.stream:
                    log.log("Warning while processing {}: draft {} stream is {} but RFC stream is {}".format(
                        rfc.name, draft.name, draft.stream, rfc.stream
                    ))
                elif draft.stream.slug in ["iab", "irtf", "ise", "editorial"]:
                    stream_slug = f"draft-stream-{draft.stream.slug}"
                    prev_state = draft.get_state(stream_slug)
                    if prev_state is not None and prev_state.slug != "pub":
                        new_state = State.objects.select_related("type").get(used=True, type__slug=stream_slug, slug="pub")
                        draft.set_state(new_state)
                        draft_changes.append(
                            f"changed {new_state.type.label} to {new_state}"
                        )
                        e = update_action_holders(draft, prev_state, new_state)
                        if e:
                            draft_events.append(e)
                if draft_changes:
                    draft_events.append(
                        DocEvent.objects.create(
                            doc=draft,
                            rev=draft.rev,
                            by=system_person,
                            type="sync_from_rfc_editor",
                            desc=f"Updated while publishing {rfc.name} ({', '.join(draft_changes)})",
                        )
                    )
                    draft.save_with_history(draft_events)

        return rfc

    def _create_rfc(self, validated_data):
        authors_data = validated_data.pop("authors")
        formal_languages = validated_data.pop("formal_languages", [])
        # todo ad field
        rfc = Document.objects.create(
            type_id="rfc",
            name=f"rfc{validated_data['rfc_number']}",
            **validated_data,
        )
        rfc.formal_languages.set(formal_languages)  # list of PKs is ok
        for order, author_data in enumerate(authors_data):
            rfc.rfcauthor_set.create(
                order=order,
                **author_data,
            )
        return rfc


class RfcFileSerializer(serializers.Serializer):
    # The structure of this serializer is constrained by what openapi-generator-cli's
    # python generator can correctly serialize as multipart/form-data. It does not
    # handle nested serializers well (or perhaps at all). ListFields with child
    # ChoiceField or RegexField do not serialize correctly. DictFields don't seem
    # to work.
    #
    # It does seem to correctly send filenames along with FileFields, even as a child
    # in a ListField, so we use that to convey the file format of each item. There
    # are other options we could consider (e.g., a structured CharField) but this
    # works.
    allowed_extensions = (".xml", ".txt", ".html", ".txt.pdf")

    rfc = serializers.SlugRelatedField(
        slug_field="rfc_number",
        queryset=Document.objects.filter(type_id="rfc"),
        help_text="RFC number to which the contents belong",
    )
    contents = serializers.ListField(
        child=serializers.FileField(
            allow_empty_file=False,
            use_url=False,
        ),
        help_text=(
            "List of content files. Filename extensions are used to identify "
            "file types, but filenames are otherwise ignored."
        ),
    )
    replace = serializers.BooleanField(
        required=False,
        default=False,
        help_text=(
            "Replace existing files for this RFC. Defaults to false. When false, "
            "if _any_ files already exist for the specified RFC the upload will be "
            "rejected regardless of which files are being uploaded. When true,"
            "existing files will be removed and new ones will be put in place. BE"
            "VERY CAREFUL WITH THIS OPTION IN PRODUCTION."
        ),
    )

    def validate_contents(self, data):
        found_extensions = []
        for uploaded_file in data:
            if not hasattr(uploaded_file, "name"):
                raise serializers.ValidationError(
                    "filename not specified for uploaded file",
                    code="missing-filename",
                )
            ext = "".join(Path(uploaded_file.name).suffixes)
            if ext not in self.allowed_extensions:
                raise serializers.ValidationError(
                    f"File uploaded with invalid extension '{ext}'",
                    code="invalid-filename-ext",
                )
            if ext in found_extensions:
                raise serializers.ValidationError(
                    f"More than one file uploaded with extension '{ext}'",
                    code="duplicate-filename-ext",
                )
        return data


class NotificationAckSerializer(serializers.Serializer):
    message = serializers.CharField(default="ack")
