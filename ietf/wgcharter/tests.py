# Copyright The IETF Trust 2011, All Rights Reserved

import os, shutil, datetime
from StringIO import StringIO

import django.test
from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse
from ietf.utils.mail import outbox
from ietf.utils.test_data import make_test_data
from ietf.utils.test_utils import login_testing_unauthorized

from pyquery import PyQuery

from ietf.doc.models import *
from ietf.doc.utils import *
from ietf.group.models import *
from ietf.group.utils import *
from ietf.name.models import *
from ietf.person.models import *
from ietf.iesg.models import TelechatDate
from ietf.wgcharter.utils import *

class EditCharterTestCase(django.test.TestCase):
    fixtures = ['names']

    def setUp(self):
        self.charter_dir = os.path.abspath("tmp-charter-dir")
        os.mkdir(self.charter_dir)
        settings.CHARTER_PATH = self.charter_dir

    def tearDown(self):
        shutil.rmtree(self.charter_dir)

    def test_change_state(self):
        make_test_data()

        group = Group.objects.get(acronym="ames")
        charter = group.charter

        url = urlreverse('charter_change_state', kwargs=dict(name=charter.name))
        login_testing_unauthorized(self, "secretary", url)

        first_state = charter.get_state()

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form select[name=charter_state]')), 1)
        
        # faulty post
        r = self.client.post(url, dict(charter_state="-12345"))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)
        self.assertEquals(charter.get_state(), first_state)
        
        # change state
        for slug in ("intrev", "extrev", "iesgrev"):
            s = State.objects.get(type="charter", slug=slug)
            events_before = charter.docevent_set.count()
            mailbox_before = len(outbox)
        
            r = self.client.post(url, dict(charter_state=str(s.pk), message="test message"))
            self.assertEquals(r.status_code, 302)
        
            charter = Document.objects.get(name="charter-ietf-%s" % group.acronym)
            self.assertEquals(charter.get_state_slug(), slug)
            events_now = charter.docevent_set.count()
            self.assertTrue(events_now > events_before)

            def find_event(t):
                return [e for e in charter.docevent_set.all()[:events_now - events_before] if e.type == t]

            self.assertTrue("State changed" in find_event("changed_document")[0].desc)

            if slug in ("intrev", "iesgrev"):
                self.assertTrue(find_event("created_ballot"))

            self.assertEquals(len(outbox), mailbox_before + 1)
            self.assertTrue("State changed" in outbox[-1]['Subject'])
                    
    def test_edit_telechat_date(self):
        make_test_data()

        group = Group.objects.get(acronym="mars")
        charter = group.charter

        url = urlreverse('charter_telechat_date', kwargs=dict(name=charter.name))
        login_testing_unauthorized(self, "secretary", url)

        # add to telechat
        self.assertTrue(not charter.latest_event(TelechatDocEvent, "scheduled_for_telechat"))
        telechat_date = TelechatDate.objects.active()[0].date
        r = self.client.post(url, dict(name=group.name, acronym=group.acronym, telechat_date=telechat_date.isoformat()))
        self.assertEquals(r.status_code, 302)

        charter = Document.objects.get(name=charter.name)
        self.assertTrue(charter.latest_event(TelechatDocEvent, "scheduled_for_telechat"))
        self.assertEquals(charter.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date, telechat_date)

        # change telechat
        telechat_date = TelechatDate.objects.active()[1].date
        r = self.client.post(url, dict(name=group.name, acronym=group.acronym, telechat_date=telechat_date.isoformat()))
        self.assertEquals(r.status_code, 302)

        charter = Document.objects.get(name=charter.name)
        self.assertEquals(charter.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date, telechat_date)

        # remove from agenda
        telechat_date = ""
        r = self.client.post(url, dict(name=group.name, acronym=group.acronym, telechat_date=telechat_date))
        self.assertEquals(r.status_code, 302)

        charter = Document.objects.get(name=charter.name)
        self.assertTrue(not charter.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date)

    def test_edit_notify(self):
        make_test_data()

        charter = Group.objects.get(acronym="mars").charter

        url = urlreverse('charter_edit_notify', kwargs=dict(name=charter.name))
        login_testing_unauthorized(self, "secretary", url)

        # post
        self.assertTrue(not charter.notify)
        r = self.client.post(url, dict(notify="someone@example.com, someoneelse@example.com"))
        self.assertEquals(r.status_code, 302)

        charter = Document.objects.get(name=charter.name)
        self.assertEquals(charter.notify, "someone@example.com, someoneelse@example.com")

    def test_edit_ad(self):
        make_test_data()

        charter = Group.objects.get(acronym="mars").charter

        url = urlreverse('charter_edit_ad', kwargs=dict(name=charter.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('select[name=ad]')),1)

        # post
        self.assertTrue(not charter.ad)
        ad2 = Person.objects.get(name='Ad No2')
        r = self.client.post(url,dict(ad=str(ad2.pk)))
        self.assertEquals(r.status_code, 302)

        charter = Document.objects.get(name=charter.name)
        self.assertEquals(charter.ad, ad2)

    def test_submit_charter(self):
        make_test_data()

        group = Group.objects.get(acronym="mars")
        charter = group.charter

        url = urlreverse('charter_submit', kwargs=dict(name=charter.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[name=txt]')), 1)

        # faulty post
        test_file = StringIO("\x10\x11\x12") # post binary file
        test_file.name = "unnamed"

        r = self.client.post(url, dict(txt=test_file))
        self.assertEquals(r.status_code, 200)
        self.assertTrue("does not appear to be a text file" in r.content)

        # post
        prev_rev = charter.rev

        latin_1_snippet = '\xe5' * 10
        utf_8_snippet = '\xc3\xa5' * 10
        test_file = StringIO("Windows line\r\nMac line\rUnix line\n" + latin_1_snippet)
        test_file.name = "unnamed"

        r = self.client.post(url, dict(txt=test_file))
        self.assertEquals(r.status_code, 302)

        charter = Document.objects.get(name="charter-ietf-%s" % group.acronym)
        self.assertEquals(charter.rev, next_revision(prev_rev))
        self.assertTrue("new_revision" in charter.latest_event().type)

        with open(os.path.join(self.charter_dir, charter.canonical_name() + "-" + charter.rev + ".txt")) as f:
            self.assertEquals(f.read(),
                              "Windows line\nMac line\nUnix line\n" + utf_8_snippet)

class CharterApproveBallotTestCase(django.test.TestCase):
    fixtures = ['names']

    def setUp(self):
        self.charter_dir = os.path.abspath("tmp-charter-dir")
        os.mkdir(self.charter_dir)
        settings.CHARTER_PATH = self.charter_dir

    def tearDown(self):
        shutil.rmtree(self.charter_dir)

    def test_approve(self):
        make_test_data()

        group = Group.objects.get(acronym="ames")
        charter = group.charter

        url = urlreverse('charter_approve', kwargs=dict(name=charter.name))
        login_testing_unauthorized(self, "secretary", url)

        with open(os.path.join(self.charter_dir, "%s-%s.txt" % (charter.canonical_name(), charter.rev)), "w") as f:
            f.write("This is a charter.")

        p = Person.objects.get(name="Aread Irector")

        BallotDocEvent.objects.create(
            type="created_ballot",
            ballot_type=BallotType.objects.get(doc_type="charter", slug="approve"),
            by=p,
            doc=charter,
            desc="Created ballot",
            )

        charter.set_state(State.objects.get(type="charter", slug="iesgrev"))

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue("Send out the announcement" in q('input[type=submit]')[0].get('value'))
        self.assertEquals(len(q('pre')), 1)

        # approve
        mailbox_before = len(outbox)

        r = self.client.post(url, dict())
        self.assertEquals(r.status_code, 302)

        charter = Document.objects.get(name=charter.name)
        self.assertEquals(charter.get_state_slug(), "approved")
        self.assertTrue(not charter.ballot_open("approve"))

        self.assertEquals(charter.rev, "01")
        self.assertTrue(os.path.exists(os.path.join(self.charter_dir, "charter-ietf-%s-%s.txt" % (group.acronym, charter.rev))))

        self.assertEquals(len(outbox), mailbox_before + 2)
        self.assertTrue("WG Action" in outbox[-1]['Subject'])
        self.assertTrue("Charter approved" in outbox[-2]['Subject'])
