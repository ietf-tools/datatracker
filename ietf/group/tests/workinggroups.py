import sys
from ietf.utils import TestCase
from ietf.group.models import Group

class WorkingGroupTestCase(TestCase):
    # See ietf.utils.test_utils.TestCase for the use of perma_fixtures vs. fixtures
    fixtures = [ 'workinggroups', ]
    perma_fixtures = []

    def test_FindOneWg(self):
        one = Group.objects.filter(acronym = 'roll')
        self.assertIsNotNone(one)
        
    def test_ActiveWgGroupList(self):
        groups = Group.objects.active_wgs()
        self.assertEqual(groups.count(), 151)


        
