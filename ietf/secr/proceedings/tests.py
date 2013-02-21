from django.core.urlresolvers import reverse
from django.test import TestCase

from ietf.meeting.models import Meeting
from ietf.utils.test_data import make_test_data

from pyquery import PyQuery

SEC_USER='secretary'

class MainTestCase(TestCase):
    fixtures = ['names']
                
    def test_main(self):
        "Main Test"
        url = reverse('proceedings')
        response = self.client.get(url,REMOTE_USER=SEC_USER)
        self.assertEquals(response.status_code, 200)

    def test_view(self):
        "View Test"
        draft = make_test_data()
        meeting = Meeting.objects.all()[0]
        url = reverse('meetings_view', kwargs={'meeting_id':meeting.number})
        response = self.client.get(url,REMOTE_USER=SEC_USER)
        self.assertEquals(response.status_code, 200)
