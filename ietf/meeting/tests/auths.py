import sys
from django.test              import Client
from ietf.utils import TestCase
#from ietf.person.models import Person
from django.contrib.auth.models import User
from ietf.ietfauth.decorators import has_role

# from http://djangosnippets.org/snippets/850/

auth_wlo = {'REMOTE_USER':'wnl'}

auth_ietfchair = {'REMOTE_USER':'rhousley'}

# this is a generic user who has no special role
auth_joeblow = {'REMOTE_USER':'joeblow'}

# this is user who is an AD
auth_ferrel = {'REMOTE_USER':'stephen.farrell@cs.tcd.ie'}


class AuthDataTestCase(TestCase):
    # See ietf.utils.test_utils.TestCase for the use of perma_fixtures vs. fixtures
    perma_fixtures = [
                 'meeting83.json',
                 'constraint83.json',
                 'workinggroups.json',
                 'groupgroup.json',
                 'person.json', 'users.json' ]

    def test_wlo_is_secretariat(self):
        wnl = User.objects.filter(pk = 509)[0]
        self.assertIsNotNone(wnl)
        self.assertTrue(has_role(wnl, "Secretariat"))

    def test_housley_is_ad(self):
        rh = User.objects.filter(pk = 432)[0]
        self.assertIsNotNone(rh)
        self.assertTrue(has_role(rh, "Area Director"))

    def test_ferrel_is_ad(self):
        sf = User.objects.filter(pk = 491)[0]
        self.assertIsNotNone(sf)
        self.assertTrue(has_role(sf, "Area Director"))

    def test_joeblow_is_mortal(self):
        jb = User.objects.filter(pk = 99870)[0]
        self.assertIsNotNone(jb)
        self.assertFalse(has_role(jb, "Area Director"))
        self.assertFalse(has_role(jb, "Secretariat"))


