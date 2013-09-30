from django.core.urlresolvers import reverse
from ietf.utils import TestCase

from ietf.meeting.models import Meeting
from ietf.utils.test_data import make_test_data

from pyquery import PyQuery

SECR_USER='secretary'

class MainTestCase(TestCase):
    # See ietf.utils.test_utils.TestCase for the use of perma_fixtures vs. fixtures
    perma_fixtures = ['names']
                
    def test_main(self):
        "Main Test"
        url = reverse('meetings')
        response = self.client.get(url, REMOTE_USER=SECR_USER)
        self.assertEquals(response.status_code, 200)

    def test_view(self):
        "View Test"
        draft = make_test_data()
        meeting = Meeting.objects.all()[0]
        url = reverse('meetings_view', kwargs={'meeting_id':meeting.number})
        response = self.client.get(url, REMOTE_USER=SECR_USER)
        self.assertEquals(response.status_code, 200)
