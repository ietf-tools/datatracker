from django.core.urlresolvers import reverse
from django.test import TestCase
from django.contrib.auth.models import User

from ietf.group.models import Group
from ietf.ietfauth.decorators import has_role
from ietf.person.models import Person
from ietf.utils.mail import outbox

from pyquery import PyQuery

SEC_USER='rcross'
WG_USER=''
AD_USER=''

class MainTestCase(TestCase):
    fixtures = ['names',
                'test-group',
                'test-person',
                'test-user',
                'test-email',
                'test-role']
                
    def test_main(self):
        "Main Test"
        url = reverse('areas')
        response = self.client.get(url,REMOTE_USER=SEC_USER)
        self.assertEquals(response.status_code, 200)

    def test_view(self):
        "View Test"
        areas = Group.objects.filter(type='area',state='active')
        url = reverse('areas_view', kwargs={'name':areas[0].acronym})
        response = self.client.get(url,REMOTE_USER=SEC_USER)
        self.assertEquals(response.status_code, 200)
