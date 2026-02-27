# Copyright The IETF Trust 2023-2026, All Rights Reserved
import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.db import IntegrityError
from drf_spectacular.utils import OpenApiParameter
from rest_framework import mixins, parsers, serializers, viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.views import APIView
from rest_framework.response import Response

from django.db.models import CharField as ModelCharField, OuterRef, Subquery, Q
from django.db.models.functions import Coalesce
from django.http import Http404
from drf_spectacular.utils import extend_schema_view, extend_schema
from rest_framework import generics
from rest_framework.fields import CharField as DrfCharField
from rest_framework.filters import SearchFilter
from rest_framework.pagination import LimitOffsetPagination

from ietf.api.serializers_rpc import (
    PersonSerializer,
    FullDraftSerializer,
    DraftSerializer,
    SubmittedToQueueSerializer,
    OriginalStreamSerializer,
    ReferenceSerializer,
    EmailPersonSerializer,
    RfcWithAuthorsSerializer,
    DraftWithAuthorsSerializer,
    NotificationAckSerializer, RfcPubSerializer, RfcFileSerializer,
    EditableRfcSerializer,
)
from ietf.doc.api import PrefetchRelatedDocument
from ietf.doc.models import Document, DocHistory, RfcAuthor, SUBSERIES_DOC_TYPE_IDS, \
    DocEvent
from ietf.doc.serializers import RfcAuthorSerializer
from ietf.doc.storage_utils import remove_from_storage, store_file, exists_in_storage
from ietf.person.models import Email, Person


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict."
    default_code = "conflict"


@extend_schema_view(
    retrieve=extend_schema(
        operation_id="get_person_by_id",
        summary="Find person by ID",
        description="Returns a single person",
        parameters=[
            OpenApiParameter(
                name="person_id",
                type=int,
                location="path",
                description="Person ID identifying this person.",
            ),
        ],
    ),
)
class PersonViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Person.objects.all()
    serializer_class = PersonSerializer
    api_key_endpoint = "ietf.api.views_rpc"
    lookup_url_kwarg = "person_id"

    @extend_schema(
        operation_id="get_persons",
        summary="Get a batch of persons",
        description="Returns a list of persons matching requested ids. Omits any that are missing.",
        request=list[int],
        responses=PersonSerializer(many=True),
    )
    @action(detail=False, methods=["post"])
    def batch(self, request):
        """Get a batch of rpc person names"""
        pks = request.data
        return Response(
            self.get_serializer(Person.objects.filter(pk__in=pks), many=True).data
        )

    @extend_schema(
        operation_id="persons_by_email",
        summary="Get a batch of persons by email addresses",
        description=(
            "Returns a list of persons matching requested ids. "
            "Omits any that are missing."
        ),
        request=list[str],
        responses=EmailPersonSerializer(many=True),
    )
    @action(detail=False, methods=["post"], serializer_class=EmailPersonSerializer)
    def batch_by_email(self, request):
        emails = Email.objects.filter(address__in=request.data, person__isnull=False)
        serializer = self.get_serializer(emails, many=True)
        return Response(serializer.data)


class SubjectPersonView(APIView):
    api_key_endpoint = "ietf.api.views_rpc"

    @extend_schema(
        operation_id="get_subject_person_by_id",
        summary="Find person for OIDC subject by ID",
        description="Returns a single person",
        responses=PersonSerializer,
        parameters=[
            OpenApiParameter(
                name="subject_id",
                type=str,
                description="subject ID of person to return",
                location="path",
            ),
        ],
    )
    def get(self, request, subject_id: str):
        try:
            user_id = int(subject_id)
        except ValueError:
            raise serializers.ValidationError(
                {"subject_id": "This field must be an integer value."}
            )
        person = Person.objects.filter(user__pk=user_id).first()
        if person:
            return Response(PersonSerializer(person).data)
        raise Http404


class RpcLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 10
    max_limit = 100


class SingleTermSearchFilter(SearchFilter):
    """SearchFilter backend that does not split terms

    The default SearchFilter treats comma or whitespace-separated terms as individual
    search terms. This backend instead searches for the exact term.
    """

    def get_search_terms(self, request):
        value = request.query_params.get(self.search_param, "")
        field = DrfCharField(trim_whitespace=False, allow_blank=True)
        cleaned_value = field.run_validation(value)
        return [cleaned_value]


@extend_schema_view(
    get=extend_schema(
        operation_id="search_person",
        description="Get a list of persons, matching by partial name or email",
    ),
)
class RpcPersonSearch(generics.ListAPIView):
    # n.b. the OpenAPI schema for this can be generated by running
    # ietf/manage.py spectacular --file spectacular.yaml
    # and extracting / touching up the rpc_person_search_list operation
    api_key_endpoint = "ietf.api.views_rpc"
    queryset = Person.objects.all()
    serializer_class = PersonSerializer
    pagination_class = RpcLimitOffsetPagination

    # Searchable on all name-like fields or email addresses
    filter_backends = [SingleTermSearchFilter]
    search_fields = ["name", "plain", "email__address"]


@extend_schema_view(
    retrieve=extend_schema(
        operation_id="get_draft_by_id",
        summary="Get a draft",
        description="Returns the draft for the requested ID",
        parameters=[
            OpenApiParameter(
                name="doc_id",
                type=int,
                location="path",
                description="Doc ID identifying this draft.",
            ),
        ],
    ),
    submitted_to_rpc=extend_schema(
        operation_id="submitted_to_rpc",
        summary="List documents ready to enter the RFC Editor Queue",
        description="List documents ready to enter the RFC Editor Queue",
        responses=SubmittedToQueueSerializer(many=True),
    ),
)
class DraftViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Document.objects.filter(type_id="draft")
    serializer_class = FullDraftSerializer
    api_key_endpoint = "ietf.api.views_rpc"
    lookup_url_kwarg = "doc_id"

    @action(detail=False, serializer_class=SubmittedToQueueSerializer)
    def submitted_to_rpc(self, request):
        """Return documents in datatracker that have been submitted to the RPC but are not yet in the queue

        Those queries overreturn - there may be things, particularly not from the IETF stream that are already in the queue.
        """
        ietf_docs = Q(states__type_id="draft-iesg", states__slug__in=["ann"])
        irtf_iab_ise_docs = Q(
            states__type_id__in=[
                "draft-stream-iab",
                "draft-stream-irtf",
                "draft-stream-ise",
            ],
            states__slug__in=["rfc-edit"],
        )
        # TODO: Need a way to talk about editorial stream docs
        docs = (
            self.get_queryset()
            .filter(type_id="draft")
            .filter(ietf_docs | irtf_iab_ise_docs)
        )
        serializer = self.get_serializer(docs, many=True)
        return Response(serializer.data)

    @extend_schema(
        operation_id="get_draft_references",
        summary="Get normative references to I-Ds",
        description=(
            "Returns the id and name of each normatively "
            "referenced Internet-Draft for the given docId"
        ),
        parameters=[
            OpenApiParameter(
                name="doc_id",
                type=int,
                location="path",
                description="Doc ID identifying this draft.",
            ),
        ],
        responses=ReferenceSerializer(many=True),
    )
    @action(detail=True, serializer_class=ReferenceSerializer)
    def references(self, request, doc_id=None):
        doc = self.get_object()
        serializer = self.get_serializer(
            [
                reference
                for reference in doc.related_that_doc("refnorm")
                if reference.type_id == "draft"
            ],
            many=True,
        )
        return Response(serializer.data)

    @extend_schema(
        operation_id="get_draft_authors",
        summary="Gather authors of the drafts with the given names",
        description="returns a list mapping draft names to objects describing authors",
        request=list[str],
        responses=DraftWithAuthorsSerializer(many=True),
    )
    @action(detail=False, methods=["post"], serializer_class=DraftWithAuthorsSerializer)
    def bulk_authors(self, request):
        drafts = self.get_queryset().filter(name__in=request.data)
        serializer = self.get_serializer(drafts, many=True)
        return Response(serializer.data)


@extend_schema_view(
    rfc_original_stream=extend_schema(
        operation_id="get_rfc_original_streams",
        summary="Get the streams RFCs were originally published into",
        description="returns a list of dicts associating an RFC with its originally published stream",
        responses=OriginalStreamSerializer(many=True),
    )
)
class RfcViewSet(mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = Document.objects.filter(type_id="rfc")
    api_key_endpoint = "ietf.api.views_rpc"
    lookup_field = "rfc_number"
    serializer_class = EditableRfcSerializer

    def perform_update(self, serializer):
        DocEvent.objects.create(
            doc=serializer.instance,
            rev=serializer.instance.rev,
            by=Person.objects.get(name="(System)"),
            type="sync_from_rfc_editor",
            desc="Metadata sync from RFC Editor",
        )
        super().perform_update(serializer)

    @action(detail=False, serializer_class=OriginalStreamSerializer)
    def rfc_original_stream(self, request):
        rfcs = self.get_queryset().annotate(
            orig_stream_id=Coalesce(
                Subquery(
                    DocHistory.objects.filter(doc=OuterRef("pk"))
                    .exclude(stream__isnull=True)
                    .order_by("time")
                    .values_list("stream_id", flat=True)[:1]
                ),
                "stream_id",
                output_field=ModelCharField(),
            ),
        )
        serializer = self.get_serializer(rfcs, many=True)
        return Response(serializer.data)

    @extend_schema(
        operation_id="get_rfc_authors",
        summary="Gather authors of the RFCs with the given numbers",
        description="returns a list mapping rfc numbers to objects describing authors",
        request=list[int],
        responses=RfcWithAuthorsSerializer(many=True),
    )
    @action(detail=False, methods=["post"], serializer_class=RfcWithAuthorsSerializer)
    def bulk_authors(self, request):
        rfcs = self.get_queryset().filter(rfc_number__in=request.data)
        serializer = self.get_serializer(rfcs, many=True)
        return Response(serializer.data)


class DraftsByNamesView(APIView):
    api_key_endpoint = "ietf.api.views_rpc"

    @extend_schema(
        operation_id="get_drafts_by_names",
        summary="Get a batch of drafts by draft names",
        description="returns a list of drafts with matching names",
        request=list[str],
        responses=DraftSerializer(many=True),
    )
    def post(self, request):
        names = request.data
        docs = Document.objects.filter(type_id="draft", name__in=names)
        return Response(DraftSerializer(docs, many=True).data)


class RfcAuthorViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for RfcAuthor model
    
    Router needs to provide rfc_number as a kwarg
    """
    api_key_endpoint = "ietf.api.views_rpc"

    queryset = RfcAuthor.objects.all()
    serializer_class = RfcAuthorSerializer
    lookup_url_kwarg = "author_id"
    rfc_number_param = "rfc_number"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(
                document__type_id="rfc",
                document__rfc_number=self.kwargs[self.rfc_number_param],
            )
        )


class RfcPubNotificationView(APIView):
    api_key_endpoint = "ietf.api.views_rpc"

    @extend_schema(
        operation_id="notify_rfc_published",
        summary="Notify datatracker of RFC publication",
        request=RfcPubSerializer,
        responses=NotificationAckSerializer,
    )
    def post(self, request):
        serializer = RfcPubSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Create RFC
        try:
            serializer.save()
        except IntegrityError as err:
            if Document.objects.filter(
                rfc_number=serializer.validated_data["rfc_number"]
            ):
                raise serializers.ValidationError(
                    "RFC with that number already exists",
                    code="rfc-number-in-use",
                )
            raise serializers.ValidationError(
                f"Unable to publish: {err}",
                code="unknown-integrity-error",
            )
        return Response(NotificationAckSerializer().data)


class RfcPubFilesView(APIView):
    api_key_endpoint = "ietf.api.views_rpc"
    parser_classes = [parsers.MultiPartParser]

    def _fs_destination(self, filename: str | Path) -> Path:
        """Destination for an uploaded RFC file in the filesystem
        
        Strips any path components in filename and returns an absolute Path.
        """
        rfc_path = Path(settings.RFC_PATH)
        filename = Path(filename)  # could potentially have directory components
        extension = "".join(filename.suffixes)
        if extension == ".notprepped.xml":
            return rfc_path / "prerelease" / filename.name
        return rfc_path / filename.name

    def _blob_destination(self, filename: str | Path) -> str:
        """Destination name for an uploaded RFC file in the blob store
        
        Strips any path components in filename and returns an absolute Path.
        """
        filename = Path(filename)  # could potentially have directory components
        extension = "".join(filename.suffixes)
        if extension == ".notprepped.xml":
            file_type = "notprepped"
        elif extension[0] == ".":
            file_type = extension[1:]
        else:
            raise serializers.ValidationError(
                f"Extension does not begin with '.'!? ({filename})",
            )
        return f"{file_type}/{filename.name}"

    @extend_schema(
        operation_id="upload_rfc_files",
        summary="Upload files for a published RFC",
        request=RfcFileSerializer,
        responses=NotificationAckSerializer,
    )
    def post(self, request):
        serializer = RfcFileSerializer(
            # many=True,
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        rfc = serializer.validated_data["rfc"]
        uploaded_files = serializer.validated_data["contents"]  # list[UploadedFile]
        replace = serializer.validated_data["replace"]
        dest_stem = f"rfc{rfc.rfc_number}"
        mtime = serializer.validated_data["mtime"]
        mtimestamp = mtime.timestamp()
        blob_kind = "rfc"

        # List of files that might exist for an RFC
        possible_rfc_files = [
            self._fs_destination(dest_stem + ext)
            for ext in serializer.allowed_extensions
        ]
        possible_rfc_blobs = [
            self._blob_destination(dest_stem + ext)
            for ext in serializer.allowed_extensions
        ]
        if not replace:
            # this is the default: refuse to overwrite anything if not replacing
            for possible_existing_file in possible_rfc_files:
                if possible_existing_file.exists():
                    raise Conflict(
                        "File(s) already exist for this RFC",
                        code="files-exist",
                    )
            for possible_existing_blob in possible_rfc_blobs:
                if exists_in_storage(
                    kind=blob_kind, name=possible_existing_blob
                ):
                    raise Conflict(
                        "Blob(s) already exist for this RFC",
                        code="blobs-exist",
                    )

        with TemporaryDirectory() as tempdir:
            # Save files in a temporary directory. Use the uploaded filename
            # extensions to identify files, but ignore the stems and generate our own.
            files_to_move = []  # list[Path]
            tmpfile_stem = Path(tempdir) / dest_stem
            for upfile in uploaded_files:
                uploaded_filename = Path(upfile.name)  # name supplied by request
                uploaded_ext = "".join(uploaded_filename.suffixes)
                tempfile_path = tmpfile_stem.with_suffix(uploaded_ext)
                with tempfile_path.open("wb") as dest:
                    for chunk in upfile.chunks():
                        dest.write(chunk)
                os.utime(tempfile_path, (mtimestamp, mtimestamp))
                files_to_move.append(tempfile_path)
            # copy files to final location, removing any existing ones first if the
            # remove flag was set
            if replace:
                for possible_existing_file in possible_rfc_files:
                    possible_existing_file.unlink(missing_ok=True)
                for possible_existing_blob in possible_rfc_blobs:
                    remove_from_storage(
                        blob_kind, possible_existing_blob, warn_if_missing=False
                    )
            for ftm in files_to_move:
                with ftm.open("rb") as f:
                    store_file(
                        kind=blob_kind,
                        name=self._blob_destination(ftm),
                        file=f,
                        doc_name=rfc.name,
                        doc_rev=rfc.rev,  # expect blank, but match whatever it is
                        mtime=mtime,
                    )
                destination = self._fs_destination(ftm)
                if (
                    settings.SERVER_MODE != "production"
                    and not destination.parent.exists()
                ):
                    destination.parent.mkdir()
                shutil.move(ftm, destination)

        return Response(NotificationAckSerializer().data)
