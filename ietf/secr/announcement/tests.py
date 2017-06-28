from django.db import connection
from django.urls import reverse

from pyquery import PyQuery

from ietf.utils.test_utils import TestCase
from ietf.group.models import Group
from ietf.message.models import Message
from ietf.nomcom.test_data import nomcom_test_data
from ietf.person.models import Person
from ietf.utils.test_data import make_test_data
from ietf.utils.mail import outbox, empty_outbox

SECR_USER='secretary'
WG_USER=''
AD_USER=''

class SecrAnnouncementTestCase(TestCase):
    # ------- Test View -------- #
    def test_main(self):
        "Main Test"
        make_test_data()
        url = reverse('ietf.secr.announcement.views.main')
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

class DummyCase(TestCase):
    name = connection.settings_dict['NAME']

class UnauthorizedAnnouncementCase(TestCase):
    def test_unauthorized(self):
        "Unauthorized Test"
        make_test_data()
        url = reverse('ietf.secr.announcement.views.main')
        person = Person.objects.filter(role__group__acronym='mars')[0]
        self.client.login(username=person.user.username, password=person.user.username+"+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)
    
class SubmitAnnouncementCase(TestCase):
    def test_invalid_submit(self):
        "Invalid Submit"
        make_test_data()
        url = reverse('ietf.secr.announcement.views.main')
        post_data = {'id_subject':''}
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post(url,post_data)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)
        
    def test_valid_submit(self):
        "Valid Submit"
        make_test_data()
        nomcom_test_data()
        empty_outbox()
        url = reverse('ietf.secr.announcement.views.main')
        confirm_url = reverse('ietf.secr.announcement.views.confirm')
        nomcom = Group.objects.get(type='nomcom')
        post_data = {'nomcom': nomcom.pk,
                     'to':'Other...',
                     'to_custom':'rcross@amsl.com',
                     'frm':'IETF Secretariat &lt;ietf-secretariat@ietf.org&gt;',
                     'subject':'Test Subject',
                     'body':'This is a test.'}
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url,post_data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue('Confirm Announcement' in response.content)
        response = self.client.post(confirm_url,post_data,follow=True)
        self.assertRedirects(response, url)
        self.assertEqual(len(outbox),1)
        self.assertEqual(outbox[0]['subject'],'Test Subject')
        self.assertEqual(outbox[0]['to'],'<rcross@amsl.com>')
        message = Message.objects.last()
        self.assertEqual(message.subject,'Test Subject')
        self.assertTrue(nomcom in message.related_groups.all())
