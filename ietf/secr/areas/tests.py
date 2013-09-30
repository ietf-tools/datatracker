from django.core.urlresolvers import reverse
from ietf.utils import TestCase
from django.contrib.auth.models import User

from ietf.group.models import Group, GroupEvent
from ietf.ietfauth.decorators import has_role
from ietf.person.models import Person
from ietf.utils.test_data import make_test_data

from pyquery import PyQuery

import datetime

SECR_USER='secretary'

def augment_data():
    system = Person.objects.get(name="(system)")
    area = Group.objects.get(acronym='farfut')
    GroupEvent.objects.create(group=area,
                              type='started',
                              by=system)
                              
class MainTestCase(TestCase):
    # See ietf.utils.test_utils.TestCase for the use of perma_fixtures vs. fixtures
    perma_fixtures = ['names', 'persons', 'groupgroup', 'groupevents']
                
    def test_main(self):
        "Main Test"
        draft = make_test_data()
        url = reverse('areas')
        response = self.client.get(url, REMOTE_USER=SECR_USER)
        self.assertEquals(response.status_code, 200)

    def test_view(self):
        "View Test"
        draft = make_test_data()
        augment_data()
        areas = Group.objects.filter(type='area',state='active')
        url = reverse('areas_view', kwargs={'name':areas[0].acronym})
        response = self.client.get(url, REMOTE_USER=SECR_USER)
        self.assertEquals(response.status_code, 200)
