from ietf.utils import TestCase

from ietf.person.models import Person
from ietf.meeting.models  import Meeting, TimeSlot, Session, ScheduledSession
from ietf.meeting.models  import Constraint
from ietf.group.models    import Group


class UrlGenTestCase(TestCase):
    # See ietf.utils.test_utils.TestCase for the use of perma_fixtures vs. fixtures
    perma_fixtures = [
                 'meeting83.json',
                 'constraint83.json',
                 'workinggroups.json',
                 'groupgroup.json',
                 'person.json', 'users.json' ]

    def test_meetingGeneratesUrl(self):
        mtg83 = Meeting.objects.get(pk=83)
        self.assertEqual(mtg83.json_url(), "/meeting/83.json")

    def test_constraintGeneratesUrl(self):
        const1 = Constraint.objects.get(pk=21037)
        self.assertEqual(const1.json_url(), "/meeting/83/constraint/21037.json")

    def test_groupGeneratesUrl(self):
        group1 = Group.objects.get(pk=1730)
        self.assertEqual(group1.json_url(), "/group/roll.json")

    def test_sessionGeneratesUrl(self):
        sess1 = Session.objects.get(pk=22087)
        self.assertEqual(sess1.json_url(), "/meeting/83/session/22087.json")

