from django.db import connection
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.contrib.auth.models import User

from ietf.group.models import Group
from ietf.ietfauth.decorators import has_role
from ietf.person.models import Person
from ietf.utils.mail import outbox
from ietf.utils.test_data import make_test_data
from ietf.utils.test_utils import SimpleUrlTestCase, RealDatabaseTest

from pyquery import PyQuery

SECR_USER='secretary'
WG_USER=''
AD_USER=''

#class AnnouncementUrlTestCase(SimpleUrlTestCase):
#    def testUrls(self):
#        self.doTestUrls(__file__)


class MainTestCase(TestCase):
    fixtures = ['names']
    
    # ------- Test View -------- #
    def test_main(self):
        "Main Test"
        draft = make_test_data()
        url = reverse('announcement')
        r = self.client.get(url, REMOTE_USER=SECR_USER)
        self.assertEquals(r.status_code, 200)

class DummyCase(TestCase):
    name = connection.settings_dict['NAME']
    print name

class UnauthorizedCase(TestCase):
    fixtures = ['names']
                
    def test_unauthorized(self):
        "Unauthorized Test"
        draft = make_test_data()
        url = reverse('announcement')
        # get random working group chair
        person = Person.objects.filter(role__group__type='wg')[0]
        r = self.client.get(url,REMOTE_USER=person.user)
        self.assertEquals(r.status_code, 403)
    
class SubmitCase(TestCase):
    fixtures = ['names']
    
    def test_invalid_submit(self):
        "Invalid Submit"
        draft = make_test_data()
        url = reverse('announcement')
        post_data = {'id_subject':''}
        #self.client.login(remote_user='rcross')
        r = self.client.post(url,post_data, REMOTE_USER=SECR_USER)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)
        
    def test_valid_submit(self):
        "Valid Submit"
        draft = make_test_data()
        #ietf.utils.mail.test_mode = True
        url = reverse('announcement')
        redirect = reverse('announcement_confirm')
        post_data = {'to':'Other...',
                     'to_custom':'rcross@amsl.com',
                     'frm':'IETF Secretariat &lt;ietf-secretariat@ietf.org&gt;',
                     'subject':'Test Subject',
                     'body':'This is a test.'}
        r = self.client.post(url,post_data,follow=True, REMOTE_USER=SECR_USER)
        self.assertRedirects(r, redirect)
	# good enough if we get to confirm page
        #self.assertEqual(len(outbox), 1)
        #self.assertTrue(len(outbox) > mailbox_before)
