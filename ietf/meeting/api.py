# Copyright The IETF Trust 2026, All Rights Reserved
from django.db.models import IntegerField
from django.db.models.functions import Cast
from rest_framework import generics

from ietf.meeting.models import Meeting
from ietf.meeting.serializers import PersonAttendedMeetingsSerializer
from ietf.person.models import Person


class MeetingsAttendedByEmail(generics.RetrieveAPIView):
    """List meetings attended by a person identified by email address

    Requires API key authentication
    """

    queryset = Person.objects.all()
    lookup_field = "email__address"
    lookup_url_kwarg = "email"
    serializer_class = PersonAttendedMeetingsSerializer
    api_key_endpoint = "ietf.meeting.api.meetings_attended_by_email"

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
                    person.registration_set.with_plenary_ticket_details().filter(
                        meeting_id__in=meetings_with_data
                    ).select_related(
                        "meeting"
                    )
                )
                if (
                    reg.attended
                    or reg.checkedin
                    or reg.meeting_id in has_attended_record
                )
            ],
            key=lambda reg: reg.meeting.date,
        )
