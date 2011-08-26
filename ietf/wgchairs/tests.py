import datetime, os, shutil

from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse as urlreverse
import django.test
from StringIO import StringIO
from pyquery import PyQuery

from ietf.utils.test_utils import login_testing_unauthorized
from ietf.utils.test_runner import mail_outbox
from ietf.utils.test_data import make_test_data

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    from redesign.person.models import Person, Email
    from redesign.group.models import Group, Role
        
class ManageDelegatesTestCase(django.test.TestCase):
    fixtures = ['names']

    def test_delete_delegate(self):
        make_test_data()

        url = urlreverse('manage_delegates', kwargs=dict(acronym="mars"))
        login_testing_unauthorized(self, "secretary", url)
        
        delegates = Role.objects.filter(name="delegate", group__acronym="mars")
        self.assertTrue(len(delegates) > 0)
        
        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[name=delete]')), len(delegates))

        # delete
        r = self.client.post(url,
                             dict(remove="1",
                                  delete=[d.pk for d in delegates]))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[name=delete]')), 0)
        self.assertEquals(Role.objects.filter(name="delegate", group__acronym="mars").count(), 0)
        
    def test_add_not_existing_delegate(self):
        make_test_data()

        url = urlreverse('manage_delegates', kwargs=dict(acronym="mars"))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[name=email]')), 1)

        # add non-existing
        r = self.client.post(url,
                             dict(email="unknown@example.com",
                                  form_type="single"))
        self.assertEquals(r.status_code, 200)
        self.assertTrue("unknown@example.com" in r.content)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[type=submit][value*="Send email"]')), 1)

        # we get back a warning and offer to send email, do that
        mailbox_before = len(mail_outbox)
        r = self.client.post(url,
                             dict(email="unknown@example.com",
                                  form_type="notexist"))
        self.assertEquals(r.status_code, 200)
        self.assertTrue("Email sent" in r.content)
        self.assertEquals(len(mail_outbox), mailbox_before + 3)
        
        
if not settings.USE_DB_REDESIGN_PROXY_CLASSES:
    # the above tests only work with the new schema
    del ManageDelegatesTestCase 
