# Copyright The IETF Trust 2021, All Rights Reserved

import factory

from ietf.stats.models import MeetingRegistration
from ietf.meeting.factories import MeetingFactory
from ietf.person.factories import PersonFactory

class MeetingRegistrationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MeetingRegistration

    meeting = factory.SubFactory(MeetingFactory)
    person = factory.SubFactory(PersonFactory)
    reg_type = 'onsite'
    first_name = factory.LazyAttribute(lambda obj: obj.person.first_name())
    last_name = factory.LazyAttribute(lambda obj: obj.person.last_name())
    attended = False
    checkedin = False
