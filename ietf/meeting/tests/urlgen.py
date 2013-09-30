import base64
import sys
from urlparse import urljoin

from django.test              import Client
from ietf.utils import TestCase

from django.contrib.auth.models import User
from ietf.person.models import Person
from ietf.meeting.models  import Meeting, TimeSlot, Session, ScheduledSession
from ietf.meeting.models  import Constraint
from ietf.group.models    import Group


class UrlGenTestCase(TestCase):
    # See ietf.utils.test_utils.TestCase for the use of perma_fixtures vs. fixtures
    perma_fixtures = [ 'names.xml',  # ietf/names/fixtures/names.xml for MeetingTypeName, and TimeSlotTypeName
                 'meeting83.json',
                 'constraint83.json',
                 'workinggroups.json',
                 'groupgroup.json',
                 'person.json', 'users.json' ]

    def test_meetingGeneratesUrl(self):
        mtg83 = Meeting.objects.get(pk=83)
        hostport = "http://datatracker.ietf.org"
        self.assertEqual(urljoin(hostport, mtg83.json_url()), "http://datatracker.ietf.org/meeting/83.json")

    def test_constraintGeneratesUrl(self):
        const1 = Constraint.objects.get(pk=21037)
        hostport = "http://datatracker.ietf.org"
        self.assertEqual(urljoin(hostport, const1.json_url()), "http://datatracker.ietf.org/meeting/83/constraint/21037.json")

    def test_groupGeneratesUrl(self):
        group1 = Group.objects.get(pk=1730)
        hostport = "http://datatracker.ietf.org"
        self.assertEqual(urljoin(hostport, group1.json_url()), "http://datatracker.ietf.org/group/roll.json")

    def test_sessionGeneratesUrl(self):
        sess1 = Session.objects.get(pk=22087)
        hostport = "http://datatracker.ietf.org"
        self.assertEqual(urljoin(hostport, sess1.json_url()), "http://datatracker.ietf.org/meeting/83/session/22087.json")

