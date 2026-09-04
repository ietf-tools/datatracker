# Copyright The IETF Trust 2026, All Rights Reserved
from django.core.files.base import ContentFile
from django.db.models import IntegerField
from django.db.models.functions import Cast
from django.template.loader import render_to_string
from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers, status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from ietf.meeting.models import Meeting, Session
from ietf.meeting.serializers import (
    PersonAttendedMeetingsSerializer,
    SessionBluesheetSerializer,
    SessionChatlogSerializer,
    SessionPollsSerializer,
    SessionRecordingNameSerializer,
    SessionUpdatedSerializer,
    SessionVideoUrlSerializer,
)
from ietf.meeting.utils import (
    save_bluesheet,
    save_session_json_doc,
    save_session_video_url,
)
from ietf.person.models import Person


class MeetingsAttendedByEmail(generics.RetrieveAPIView):
    """List meetings attended by a person identified by email address

    Requires API key authentication
    """

    queryset = Person.objects.all()
    lookup_field = "email__address"
    lookup_url_kwarg = "email"
    serializer_class = PersonAttendedMeetingsSerializer
    api_key_endpoint = "ietf.api.meeting.registration.attended"

    def get_object(self):
        person = super().get_object()
        assert isinstance(person, Person)
        person.attended_registrations = self._attended_registrations(person)
        return person

    @staticmethod
    def _attended_registrations(person: Person):
        meetings_with_data = (
            Meeting.objects.filter(type="ietf")
            .annotate(number_as_int=Cast("number", output_field=IntegerField()))
            .exclude(number_as_int__lt=110)
            .values_list("pk")
        )
        has_attended_record = (
            person.attended_set.filter(
                session__meeting_id__in=meetings_with_data,
                session__meeting__type="ietf",
            )
            .values_list("session__meeting__id", flat=True)
            .distinct()
        )
        return sorted(
            [
                reg
                for reg in (
                    person.registration_set.onsite_or_remote()
                    .with_plenary_ticket_details()
                    .filter(meeting_id__in=meetings_with_data)
                    .select_related("meeting")
                )
                if (
                    reg.attended
                    or reg.checkedin
                    or reg.meeting_id in has_attended_record
                )
            ],
            key=lambda reg: reg.meeting.date,
        )


@extend_schema(tags=["meeting"])
class SessionDataView(APIView):
    """Base for the endpoints that push data about one session

    The session is addressed by its pk. Only person references use UUIDs.

    These endpoints authenticate an application by token, so there is no requesting
    person; document events are authored by the (System) Person.
    """

    request_serializer_class: type

    def get_session(self, session_id):
        return get_object_or_404(Session, pk=session_id)

    def validated(self, request):
        serializer = self.request_serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def applied(self, session, save_error=None):
        if save_error:
            raise serializers.ValidationError({"detail": save_error})
        return Response(
            SessionUpdatedSerializer({"session_id": session.pk}).data,
            status=status.HTTP_200_OK,
        )


class SessionVideoUrlView(SessionDataView):
    api_key_endpoint = "ietf.api.meeting.session.video_url"
    request_serializer_class = SessionVideoUrlSerializer

    @extend_schema(
        operation_id="meeting_session_set_video_url",
        summary="Set a session's video recording URL",
        description=(
            "Points the session's video recording at the given URL, updating the newest "
            "existing video recording document or creating one."
        ),
        request=SessionVideoUrlSerializer,
        responses={200: SessionUpdatedSerializer},
    )
    def post(self, request, session_id):
        session = self.get_session(session_id)
        data = self.validated(request)
        return self.applied(
            session,
            save_session_video_url(
                session, data["url"], Person.objects.get(name="(System)")
            ),
        )


class SessionRecordingNameView(SessionDataView):
    api_key_endpoint = "ietf.api.meeting.session.recording_name"
    request_serializer_class = SessionRecordingNameSerializer

    @extend_schema(
        operation_id="meeting_session_set_recording_name",
        summary="Set the name of a session's recording",
        description="Sets the name the recording is served under by the player.",
        request=SessionRecordingNameSerializer,
        responses={200: SessionUpdatedSerializer},
    )
    def post(self, request, session_id):
        session = self.get_session(session_id)
        data = self.validated(request)
        session.meetecho_recording_name = data["name"]
        session.save()
        return self.applied(session)


class SessionBluesheetView(SessionDataView):
    api_key_endpoint = "ietf.api.meeting.session.bluesheet"
    request_serializer_class = SessionBluesheetSerializer

    @extend_schema(
        operation_id="meeting_session_upload_bluesheet",
        summary="Upload a session's bluesheet",
        description=(
            "Renders the entries into a new revision of the session's bluesheet "
            "document. Entries are free text: they are what the uploader observed, and "
            "are not resolved to datatracker persons."
        ),
        request=SessionBluesheetSerializer,
        responses={200: SessionUpdatedSerializer},
    )
    def post(self, request, session_id):
        session = self.get_session(session_id)
        data = self.validated(request)
        text = render_to_string(
            "meeting/bluesheet.txt",
            {"data": data["bluesheet"], "session": session},
        )
        return self.applied(
            session,
            save_bluesheet(
                request,
                session,
                ContentFile(text.encode("utf-8"), name="bluesheet.txt"),
                Person.objects.get(name="(System)"),
            ),
        )


class SessionChatlogView(SessionDataView):
    api_key_endpoint = "ietf.api.meeting.session.chatlog"
    request_serializer_class = SessionChatlogSerializer

    @extend_schema(
        operation_id="meeting_session_upload_chatlog",
        summary="Upload a session's chat log",
        description=(
            "Stores the entries as a new revision of the session's chatlog document. "
            "Entries are stored as sent; `author` is a display name, not a person "
            "reference."
        ),
        request=SessionChatlogSerializer,
        responses={200: SessionUpdatedSerializer},
    )
    def post(self, request, session_id):
        session = self.get_session(session_id)
        data = self.validated(request)
        return self.applied(
            session,
            save_session_json_doc(
                session,
                "chatlog",
                data["chatlog"],
                Person.objects.get(name="(System)"),
            ),
        )


class SessionPollsView(SessionDataView):
    api_key_endpoint = "ietf.api.meeting.session.polls"
    request_serializer_class = SessionPollsSerializer

    @extend_schema(
        operation_id="meeting_session_upload_polls",
        summary="Upload a session's polls",
        description=(
            "Stores the polls as a new revision of the session's polls document. Polls "
            "carry aggregate counts, not per-person responses."
        ),
        request=SessionPollsSerializer,
        responses={200: SessionUpdatedSerializer},
    )
    def post(self, request, session_id):
        session = self.get_session(session_id)
        data = self.validated(request)
        return self.applied(
            session,
            save_session_json_doc(
                session, "polls", data["polls"], Person.objects.get(name="(System)")
            ),
        )
