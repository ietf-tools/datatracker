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
    from redesign.doc.models import Document
        
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
        
    def test_add_delegate(self):
        make_test_data()

        url = urlreverse('manage_delegates', kwargs=dict(acronym="mars"))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[name=email]')), 1)

        # add existing person
        r = self.client.post(url,
                             dict(email="plain@example.com",
                                  form_type="single"))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue("new delegate" in r.content)
        self.assertTrue(Email.objects.get(address="plain@example.com").person.name in r.content)
        

class ManageShepherdsTestCase(django.test.TestCase):
    fixtures = ['names']

    def test_manage_shepherds(self):
        make_test_data()

        url = urlreverse('manage_shepherds', kwargs=dict(acronym="mars"))
        login_testing_unauthorized(self, "secretary", url)

        # setup test documents
        group = Group.objects.get(acronym="mars")

        from redesign.doc.models import Document
        common = dict(group=group,
                      state_id="active",
                      ad=Person.objects.get(user__username="ad"),
                      type_id="draft")
        Document.objects.create(name="test-no-shepherd",
                                title="No shepherd",
                                shepherd=None,
                                **common)
        Document.objects.create(name="test-shepherd-me",
                                title="Shepherd me",
                                shepherd=Person.objects.get(user__username="secretary"),
                                **common)
        Document.objects.create(name="test-shepherd-other", title="Shepherd other",
                                shepherd=Person.objects.get(user__username="plain"),
                                **common)
        
        # get and make sure they are divided correctly
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('div#noshepherd a:contains("No shepherd")')), 1)
        self.assertEquals(len(q('div#mydocs a:contains("Shepherd me")')), 1)
        self.assertEquals(len(q('div#othershepherds a:contains("Shepherd other")')), 1)

    def test_set_shepherd(self):
        draft = make_test_data()

        url = urlreverse('doc_managing_shepherd', kwargs=dict(acronym="mars", name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('input[type=submit][name=setme]')), 1)

        # set me
        events_before = draft.docevent_set.count()
        r = self.client.post(url,
                             dict(setme="1"))
        self.assertEquals(r.status_code, 200)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue(draft.shepherd)
        self.assertEquals(draft.shepherd.user.username, "secretary")
        self.assertEquals(draft.docevent_set.count(), events_before + 1)

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        self.assertTrue(Person.objects.get(user__username="secretary").name in r.content)
        q = PyQuery(r.content)
        self.assertEquals(len(q('input[type=submit][name=remove_shepherd]')), 1)
        
        # unassign
        events_before = draft.docevent_set.count()
        r = self.client.post(url,
                             dict(remove_shepherd="1"))
        self.assertEquals(r.status_code, 200)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue(not draft.shepherd)
        self.assertEquals(draft.docevent_set.count(), events_before + 1)
        
        # change to existing person
        events_before = draft.docevent_set.count()
        r = self.client.post(url,
                             dict(email="plain@example.com",
                                  form_type="single"))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue("Shepherd assigned" in r.content)
        self.assertTrue(Email.objects.get(address="plain@example.com").person.name in r.content)
        self.assertEquals(draft.docevent_set.count(), events_before + 1)

if not settings.USE_DB_REDESIGN_PROXY_CLASSES:
    # the above tests only work with the new schema
    del ManageDelegatesTestCase 
    del ManageShepherdsTestCase 
