from django.core.urlresolvers import reverse
from ietf.utils import TestCase

from ietf.meeting.models import Meeting, Schedule
from ietf.utils.test_data import make_test_data

from pyquery import PyQuery

SECR_USER='secretary'

class MainTestCase(TestCase):
    def test_main(self):
        "Main Test"
        url = reverse('meetings')
        response = self.client.get(url, REMOTE_USER=SECR_USER)
        self.assertEqual(response.status_code, 200)

    def test_view(self):
        "View Test"
        draft = make_test_data()
        meeting = Meeting.objects.all()[0]
        url = reverse('meetings_view', kwargs={'meeting_id':meeting.number})
        response = self.client.get(url, REMOTE_USER=SECR_USER)
        self.assertEqual(response.status_code, 200)

    def test_add_meeting(self):
        "Add Meeting"
        url = reverse('meetings_add')
        post_data = dict(number=1,city='Seattle',date='2014-07-20',country='US',
                         time_zone='America/Los_Angeles',venue_name='Hilton',
                         venue_addr='100 First Ave')
        response = self.client.post(url, post_data,follow=True,REMOTE_USER=SECR_USER)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Meeting.objects.count(),1)
        self.assertEqual(Schedule.objects.count(),1)
