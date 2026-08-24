# Copyright The IETF Trust 2026, All Rights Reserved

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
