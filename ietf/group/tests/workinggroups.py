import sys
from django.test import TestCase
from ietf.group.models import Group

class WorkingGroupTestCase(TestCase):
    fixtures = [ 'workinggroups.json']

    def test_FindOneWg(self):
        one = Group.objects.filter(acronym = 'roll')
        self.assertIsNotNone(one)
        
    def test_ActiveWgGroupList(self):
        groups = Group.objects.active_wgs()
        self.assertEqual(groups.count(), 151)


        
