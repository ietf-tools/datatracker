# Copyright The IETF Trust 2026, All Rights Reserved

from django.utils import timezone
from rest_framework import serializers

from ietf.meeting.models import Registration


class AttendedMeetingSerializer(serializers.ModelSerializer):
    """Serialize a plenary meeting attendance record"""
    meeting = serializers.SlugRelatedField(slug_field="number", read_only=True)
    attendance_type = serializers.CharField(
        source="plenary_attendance_type", read_only=True
    )
    ticket_type = serializers.CharField(
        source="plenary_ticket_type", read_only=True
    )
    
    class Meta:
        model = Registration
        fields = [
            "meeting",
            "attendance_type",
            "ticket_type",
        ]


class PersonAttendedMeetingsSerializer(serializers.Serializer):
    attended = AttendedMeetingSerializer(source="attended_registrations", many=True)


class SessionVideoUrlSerializer(serializers.Serializer):
    """A session's video recording URL"""

    # max_length matches Document.external_url
    url = serializers.URLField(max_length=200)


class SessionRecordingNameSerializer(serializers.Serializer):
    """The name the recording is served under by the player"""

    # max_length matches Session.meetecho_recording_name
    name = serializers.CharField(max_length=64)


class BluesheetEntrySerializer(serializers.Serializer):
    """One line of a bluesheet

    Free text, not a person reference: the uploader cannot always resolve an attendee
    to a datatracker Person.
    """

    name = serializers.CharField()
    affiliation = serializers.CharField(allow_blank=True, default="")


class SessionBluesheetSerializer(serializers.Serializer):
    bluesheet = BluesheetEntrySerializer(many=True, allow_empty=True)


class AwareDateTimeField(serializers.DateTimeField):
    """DateTimeField that requires an explicit UTC offset

    DateTimeField makes a naive value aware in the process timezone, which silently
    shifts a timestamp the caller meant as UTC.
    """

    default_error_messages = {  # noqa: RUF012
        "naive": "Datetime must include a UTC offset.",
    }

    def enforce_timezone(self, value):
        if timezone.is_naive(value):
            self.fail("naive")
        return super().enforce_timezone(value)


class SessionAttendeeSerializer(serializers.Serializer):
    """One session attendee, identified by any UUID the datatracker issued them"""

    person_uuid = serializers.UUIDField()
    join_time = AwareDateTimeField()


class SessionAttendeesSerializer(serializers.Serializer):
    attendees = SessionAttendeeSerializer(many=True, allow_empty=True)


class SessionChatlogSerializer(serializers.Serializer):
    """A session's chat log

    Entries are stored as sent. `author` is a display name, not a person reference.
    """

    chatlog = serializers.ListField(child=serializers.DictField(), allow_empty=True)


class SessionPollsSerializer(serializers.Serializer):
    """A session's polls, as aggregate counts"""

    polls = serializers.ListField(child=serializers.DictField(), allow_empty=True)


class SessionUpdatedSerializer(serializers.Serializer):
    """Confirmation that a session data push was applied"""

    session_id = serializers.IntegerField()
