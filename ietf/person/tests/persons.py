import sys
from ietf.utils import TestCase
from ietf.group.models import Group
from ietf.person.models import Person

class PersonFetchTestCase(TestCase):
    # See ietf.utils.test_utils.TestCase for the use of perma_fixtures vs. fixtures
    perma_fixtures = [ 'persons']

    def test_FindNoPerson(self):
        one = Person.objects.by_email('wlo@amsl.org')
        self.assertEqual(one, None)

    def test_FindOnePerson(self):
        one = Person.objects.by_email('wlo@amsl.com')
        self.assertNotEqual(one, None)

    def test_FindOnePersonByUsername(self):
        one = Person.objects.by_username('wnl')
        self.assertNotEqual(one, None)

        


        
