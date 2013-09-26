import sys
from django.test import TestCase
from ietf.group.models import Group
from ietf.person.models import Person

class PersonFetchTestCase(TestCase):
    fixtures = [ 'person.json', 'users.json']

    def test_FindNoPerson(self):
        one = Person.objects.by_email('wlo@amsl.org')
        self.assertEqual(one, None)

    def test_FindOnePerson(self):
        one = Person.objects.by_email('wlo@amsl.com')
        self.assertNotEqual(one, None)

    def test_FindOnePersonByUsername(self):
        one = Person.objects.by_username('wnl')
        self.assertNotEqual(one, None)

        


        
