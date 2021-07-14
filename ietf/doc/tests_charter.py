# -*- coding: utf-8 -*-
# Copyright The IETF Trust 2011-2020, All Rights Reserved


import datetime
import io
import os
import shutil

from pyquery import PyQuery

from django.conf import settings
from django.urls import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.doc.factories import CharterFactory, NewRevisionDocEventFactory, TelechatDocEventFactory
from ietf.doc.models import ( Document, State, BallotDocEvent, BallotType, NewRevisionDocEvent,
    TelechatDocEvent, WriteupDocEvent )
from ietf.doc.utils_charter import ( next_revision, default_review_text, default_action_text,
    charter_name_for_group )
from ietf.doc.utils import close_open_ballots
from ietf.group.factories import RoleFactory, GroupFactory
from ietf.group.models import Group, GroupMilestone
from ietf.iesg.models import TelechatDate
from ietf.person.models import Person
from ietf.utils.test_utils import TestCase
from ietf.utils.mail import outbox, empty_outbox, get_payload_text
from ietf.utils.test_utils import login_testing_unauthorized

class ViewCharterTests(TestCase):
    def test_view_revisions(self):
        charter = CharterFactory()
        e = NewRevisionDocEventFactory(doc=charter,rev="01")
        charter.rev = e.rev
        charter.save_with_history([e])
        e = NewRevisionDocEventFactory(doc=charter,rev="01-00")
        charter.rev = e.rev
        charter.save_with_history([e])
        e =NewRevisionDocEventFactory(doc=charter,rev="02")
        charter.rev = e.rev
        charter.save_with_history([e])
        e =NewRevisionDocEventFactory(doc=charter,rev="02-00")
        charter.rev = e.rev
        charter.save_with_history([e])
        e = NewRevisionDocEventFactory(doc=charter,rev="02-01")
        charter.rev = e.rev
        charter.save_with_history([e])

        url = urlreverse('ietf.doc.views_doc.document_main',kwargs={'name':charter.name})
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertIn('The information below is for a proposed recharter. The current approved charter is',q('#message-row').text())

        url = urlreverse('ietf.doc.views_doc.document_main',kwargs={'name':charter.name,'rev':'02-00'})
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertIn('The information below is for an older version of the current proposed rechartering effort',q('#message-row').text())
            
        url = urlreverse('ietf.doc.views_doc.document_main',kwargs={'name':charter.name,'rev':'02'})
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertIn('The information below is for the currently approved charter, but newer proposed charter text exists',q('#message-row').text())

        url = urlreverse('ietf.doc.views_doc.document_main',kwargs={'name':charter.name,'rev':'01-00'})
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertIn('The information below is for an older proposed',q('#message-row').text())

        url = urlreverse('ietf.doc.views_doc.document_main',kwargs={'name':charter.name,'rev':'01'})
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertIn('The information below is for an older approved',q('#message-row').text())

        e = NewRevisionDocEventFactory(doc=charter,rev="03")
        charter.rev='03'
        charter.save_with_history([e])

        url = urlreverse('ietf.doc.views_doc.document_main',kwargs={'name':charter.name})
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertEqual('',q('#message-row').text())

            

class EditCharterTests(TestCase):
    def setUp(self):
        self.charter_dir = self.tempdir('charter')
        self.saved_charter_path = settings.CHARTER_PATH
        settings.CHARTER_PATH = self.charter_dir

    def tearDown(self):
        settings.CHARTER_PATH = self.saved_charter_path
        shutil.rmtree(self.charter_dir)

    def write_charter_file(self, charter):
        with io.open(os.path.join(self.charter_dir, "%s-%s.txt" % (charter.canonical_name(), charter.rev)), "w") as f:
            f.write("This is a charter.")

    def test_startstop_process(self):
        CharterFactory(group__acronym='mars')

        group = Group.objects.get(acronym="mars")
        charter = group.charter

        for option in ("recharter", "abandon"):
            self.client.logout()
            url = urlreverse('ietf.doc.views_charter.change_state', kwargs=dict(name=charter.name, option=option))
            login_testing_unauthorized(self, "secretary", url)

            if option == 'recharter':
                TelechatDocEventFactory(doc=charter)

            # normal get
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)

            # post
            self.write_charter_file(charter)

            r = self.client.post(url, dict(message="test message"))
            self.assertEqual(r.status_code, 302)
            if option == "abandon":
                self.assertTrue("abandoned" in charter.latest_event(type="changed_document").desc.lower())
                telechat_doc_event = charter.latest_event(TelechatDocEvent)
                self.assertIsNone(telechat_doc_event.telechat_date)
            else:
                self.assertTrue("state changed" in charter.latest_event(type="changed_state").desc.lower())

    def test_change_state(self):

        area = GroupFactory(type_id='area')
        RoleFactory(name_id='ad',group=area,person=Person.objects.get(user__username='ad'))

        ames = GroupFactory(acronym='ames',state_id='proposed',list_email='ames-wg@ietf.org',parent=area)
        RoleFactory(name_id='ad',group=ames,person=Person.objects.get(user__username='ad'))
        RoleFactory(name_id='chair',group=ames,person__name='Ames Man',person__user__email='ameschairman@example.org')
        RoleFactory(name_id='secr',group=ames,person__name='Secretary',person__user__email='amessecretary@example.org')
        CharterFactory(group=ames)

        mars = GroupFactory(acronym='mars',parent=area)
        CharterFactory(group=mars)


        group = Group.objects.get(acronym="ames")
        charter = group.charter

        url = urlreverse('ietf.doc.views_charter.change_state', kwargs=dict(name=charter.name))
        login_testing_unauthorized(self, "secretary", url)

        first_state = charter.get_state()

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form select[name=charter_state]')), 1)
        
        # faulty post
        r = self.client.post(url, dict(charter_state="-12345"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .has-error')) > 0)
        self.assertEqual(charter.get_state(), first_state)
        
        # change state
        for slug in ("intrev", "extrev", "iesgrev"):
            s = State.objects.get(used=True, type="charter", slug=slug)
            events_before = charter.docevent_set.count()

            empty_outbox()
        
            r = self.client.post(url, dict(charter_state=str(s.pk), message="test message"))
            self.assertEqual(r.status_code, 302)
        
            charter = Document.objects.get(name="charter-ietf-%s" % group.acronym)
            self.assertEqual(charter.get_state_slug(), slug)
            events_now = charter.docevent_set.count()
            self.assertTrue(events_now > events_before)

            def find_event(t):
                return [e for e in charter.docevent_set.all()[:events_now - events_before] if e.type == t]

            self.assertTrue("state changed" in find_event("changed_state")[0].desc.lower())

            if slug in ("intrev", "extrev"):
                self.assertTrue(find_event("created_ballot"))

            self.assertEqual(len(outbox), 3 if slug=="intrev" else 2 )

            if slug=="intrev":
                self.assertIn("Internal WG Review", outbox[-3]['Subject'])
                self.assertIn("iab@", outbox[-3]['To'])
                self.assertIn("iesg@", outbox[-3]['To'])
                body = get_payload_text(outbox[-3])
                for word in ["A new IETF WG", "Chairs", "Ames Man <ameschairman@example.org>",
                    "Secretaries", "Secretary <amessecretary@example.org>",
                    "Assigned Area Director", "Areað Irector <aread@example.org>",
                    "Mailing list", "ames-wg@ietf.org",
                    "Charter", "Milestones"]:

                    self.assertIn(word, body)

            self.assertIn("state changed", outbox[-2]['Subject'].lower())
            self.assertIn("iesg-secretary@", outbox[-2]['To'])
            body = get_payload_text(outbox[-2])
            for word in ["WG", "Charter", ]:
                self.assertIn(word, body)

            self.assertIn("State Update Notice", outbox[-1]['Subject'])
            self.assertIn("ames-chairs@", outbox[-1]['To'])
            body = get_payload_text(outbox[-1])
            for word in ["State changed", "Datatracker URL", ]:
                self.assertIn(word, body)

        by = Person.objects.get(user__username="secretary")
        for slug in ('extrev','iesgrev'):
            close_open_ballots(charter,by)
            r = self.client.post(url, dict(charter_state=str(State.objects.get(used=True,type='charter',slug=slug).pk) ))
            self.assertTrue(r.status_code,302)
            charter = Document.objects.get(name="charter-ietf-%s" % group.acronym)
            self.assertTrue(charter.ballot_open('approve'))


        # Exercise internal review of a recharter
        group = Group.objects.get(acronym="mars")
        charter = group.charter
        url = urlreverse('ietf.doc.views_charter.change_state', kwargs=dict(name=charter.name))
        empty_outbox()
        r = self.client.post(url, dict(charter_state=str(State.objects.get(used=True,type="charter",slug="intrev").pk), message="test"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue("A new charter" in get_payload_text(outbox[-3]))

    def test_change_rg_state(self):

        irtf = Group.objects.get(acronym='irtf')

        group = GroupFactory(acronym='somerg', type_id='rg', state_id='proposed',list_email='somerg@ietf.org',parent=irtf)
        charter = CharterFactory(group=group)

        url = urlreverse('ietf.doc.views_charter.change_state', kwargs=dict(name=charter.name))
        login_testing_unauthorized(self, "secretary", url)

        s = State.objects.get(used=True, type="charter", slug="intrev")
        empty_outbox()
    
        r = self.client.post(url, dict(charter_state=str(s.pk), message="test message"))
        self.assertEqual(r.status_code, 302)
    
        self.assertIn("Internal RG Review", outbox[-3]['Subject'])
        self.assertIn("iab@", outbox[-3]['To'])
        self.assertIn("irsg@", outbox[-3]['To'])
        body = get_payload_text(outbox[-3])
        for word in ["A new IRTF RG", 
            "Mailing list", "somerg@ietf.org",
            "Charter", "Milestones"]:

                self.assertIn(word, body)

        self.assertIn("state changed", outbox[-2]['Subject'].lower())
        self.assertIn("iesg-secretary@", outbox[-2]['To'])
        body = get_payload_text(outbox[-2])
        for word in ["RG", "Charter", ]:
            self.assertIn(word, body)

        self.assertIn("State Update Notice", outbox[-1]['Subject'])
        self.assertIn("somerg-chairs@", outbox[-1]['To'])
        body = get_payload_text(outbox[-1])
        for word in ["State changed", "Datatracker URL", ]:
            self.assertIn(word, body)

    def test_abandon_bof(self):
        charter = CharterFactory(group__state_id='bof',group__type_id='wg')
        url = urlreverse('ietf.doc.views_charter.change_state',kwargs={'name':charter.name,'option':'abandon'})
        login_testing_unauthorized(self, "secretary", url)
        response=self.client.get(url)
        self.assertEqual(response.status_code,200)
        response = self.client.post(url,{'comment':'Testing Abandoning a BOF Charter'})
        self.assertEqual(response.status_code,302)
        charter = Document.objects.get(pk=charter.pk)
        self.assertEqual(charter.group.state_id,'abandon')
        self.assertTrue('Testing Abandoning' in charter.docevent_set.filter(type='added_comment').first().desc)

    def test_change_title(self):
        charter = CharterFactory(group__type_id='wg')
        url = urlreverse('ietf.doc.views_charter.change_title',kwargs={'name':charter.name})
        login_testing_unauthorized(self, "secretary", url)
        response=self.client.get(url)
        self.assertEqual(response.status_code,200)
        response=self.client.post(url,{'charter_title':'New Test Title'})
        self.assertEqual(response.status_code,302)
        charter=Document.objects.get(pk=charter.pk)
        self.assertEqual(charter.title,'New Test Title')
        

    def test_already_open_charter_ballot(self):
        # make sure the right thing happens to the charter ballots as the Secretariat
        # does the unusual state sequence of: intrev --> extrev --> intrev
        area = GroupFactory(type_id='area')
        RoleFactory(name_id='ad',group=area,person=Person.objects.get(user__username='ad'))
        group = GroupFactory(acronym='ames',state_id='proposed',list_email='ames-wg@ietf.org',parent=area)
        CharterFactory(group=group)

        charter = group.charter

        url = urlreverse('ietf.doc.views_charter.change_state', kwargs=dict(name=charter.name))
        login_testing_unauthorized(self, "secretary", url)

        # get the charter state change page
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # put the charter in "intrev" state
        s = State.objects.get(used=True, type="charter", slug="intrev")
        r = self.client.post(url, dict(charter_state=str(s.pk), message="test message"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(charter.get_state_slug(), "intrev")
        self.assertTrue(charter.ballot_open("r-extrev"))

        events_before = charter.docevent_set.count()

        # get the charter state change page again
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # put the charter in "extrev" state without closing the previous ballot
        s = State.objects.get(used=True, type="charter", slug="extrev")
        r = self.client.post(url, dict(charter_state=str(s.pk), message="test message"))
        self.assertEqual(r.status_code, 302)
        charter = Document.objects.get(name="charter-ietf-%s" % group.acronym)
        self.assertEqual(charter.get_state_slug(), "extrev")
        self.assertTrue(charter.ballot_open("approve"))

        # make sure there is a closed_ballot event and a create_ballot event
        events_now = charter.docevent_set.count()
        self.assertTrue(events_now > events_before)

        def find_event(t):
            return [e for e in charter.docevent_set.all()[:events_now - events_before] if e.type == t]

        self.assertTrue(find_event("closed_ballot"))
        self.assertTrue(find_event("created_ballot"))

        events_before = events_now

        # get the charter state change page for a third time
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # put the charter back in "intrev" state without closing the previous ballot
        s = State.objects.get(used=True, type="charter", slug="intrev")
        r = self.client.post(url, dict(charter_state=str(s.pk), message="test message"))
        self.assertEqual(r.status_code, 302)
        charter = Document.objects.get(name="charter-ietf-%s" % group.acronym)
        self.assertEqual(charter.get_state_slug(), "intrev")
        self.assertTrue(charter.ballot_open("r-extrev"))

        # make sure there is a closed_ballot event and a create_ballot event
        events_now = charter.docevent_set.count()
        self.assertTrue(events_now > events_before)
        self.assertTrue(find_event("closed_ballot"))
        self.assertTrue(find_event("created_ballot"))

    def test_edit_telechat_date(self):
        charter = CharterFactory()
        group = charter.group

        url = urlreverse('ietf.doc.views_doc.telechat_date;charter', kwargs=dict(name=charter.name))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # add to telechat
        self.assertTrue(not charter.latest_event(TelechatDocEvent, "scheduled_for_telechat"))
        telechat_date = TelechatDate.objects.active()[0].date
        r = self.client.post(url, dict(name=group.name, acronym=group.acronym, telechat_date=telechat_date.isoformat()))
        self.assertEqual(r.status_code, 302)

        charter = Document.objects.get(name=charter.name)
        self.assertTrue(charter.latest_event(TelechatDocEvent, "scheduled_for_telechat"))
        self.assertEqual(charter.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date, telechat_date)

        # change telechat
        telechat_date = TelechatDate.objects.active()[1].date
        r = self.client.post(url, dict(name=group.name, acronym=group.acronym, telechat_date=telechat_date.isoformat()))
        self.assertEqual(r.status_code, 302)

        charter = Document.objects.get(name=charter.name)
        self.assertEqual(charter.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date, telechat_date)

        # remove from agenda
        telechat_date = ""
        r = self.client.post(url, dict(name=group.name, acronym=group.acronym, telechat_date=telechat_date))
        self.assertEqual(r.status_code, 302)

        charter = Document.objects.get(name=charter.name)
        self.assertTrue(not charter.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date)

    def test_no_returning_item_for_different_ballot(self):
        charter = CharterFactory()
        group = charter.group

        url = urlreverse('ietf.doc.views_doc.telechat_date;charter', kwargs=dict(name=charter.name))
        login_testing_unauthorized(self, "secretary", url)
        login = Person.objects.get(user__username="secretary")

        # Make it so that the charter has been through internal review, and passed its external review
        # ballot on a previous telechat 
        last_week = datetime.date.today()-datetime.timedelta(days=7)
        BallotDocEvent.objects.create(type='created_ballot',by=login,doc=charter, rev=charter.rev,
                                      ballot_type=BallotType.objects.get(doc_type=charter.type,slug='r-extrev'),
                                      time=last_week)
        TelechatDocEvent.objects.create(type='scheduled_for_telechat', doc=charter, rev=charter.rev, by=login, telechat_date=last_week, returning_item=False)
        BallotDocEvent.objects.create(type='created_ballot', by=login, doc=charter, rev=charter.rev,
                                      ballot_type=BallotType.objects.get(doc_type=charter.type, slug='approve'))
        
        # Put the charter onto a future telechat and verify returning item is not set
        telechat_date = TelechatDate.objects.active()[1].date
        r = self.client.post(url, dict(name=group.name, acronym=group.acronym, telechat_date=telechat_date.isoformat()))
        self.assertEqual(r.status_code, 302)
        
        charter = Document.objects.get(name=charter.name)
        telechat_event = charter.latest_event(TelechatDocEvent, "scheduled_for_telechat")
        self.assertEqual(telechat_event.telechat_date, telechat_date)
        self.assertFalse(telechat_event.returning_item)

    def test_edit_notify(self):
        charter=CharterFactory()

        url = urlreverse('ietf.doc.views_doc.edit_notify;charter', kwargs=dict(name=charter.name))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # post
        self.assertTrue(not charter.notify)
        newlist = "someone@example.com, someoneelse@example.com"
        r = self.client.post(url, dict(notify=newlist,save_addresses="1"))
        self.assertEqual(r.status_code, 302)

        charter = Document.objects.get(name=charter.name)
        self.assertEqual(charter.notify, newlist)

        # Ask the form to regenerate the list
        r = self.client.post(url,dict(regenerate_addresses="1"))
        self.assertEqual(r.status_code,200)
        charter= Document.objects.get(name=charter.name)
        # Regenerate does not save!
        self.assertEqual(charter.notify,newlist)
        q = PyQuery(r.content)
        formlist = q('form input[name=notify]')[0].value
        self.assertEqual(formlist, None)

    def test_edit_ad(self):

        charter = CharterFactory()

        url = urlreverse('ietf.doc.views_charter.edit_ad', kwargs=dict(name=charter.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('select[name=ad]')),1)

        # post
        self.assertTrue(not charter.ad)
        ad2 = Person.objects.get(name='Ad No2')
        r = self.client.post(url,dict(ad=str(ad2.pk)))
        self.assertEqual(r.status_code, 302)

        charter = Document.objects.get(name=charter.name)
        self.assertEqual(charter.ad, ad2)

    def test_submit_charter(self):
        charter = CharterFactory()
        group = charter.group

        url = urlreverse('ietf.doc.views_charter.submit', kwargs=dict(name=charter.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form input[name=txt]')), 1)

        # faulty post
        test_file = io.StringIO("\x10\x11\x12") # post binary file
        test_file.name = "unnamed"

        r = self.client.post(url, dict(txt=test_file))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "does not appear to be a text file")

        # post
        prev_rev = charter.rev

        latin_1_snippet = b'\xe5' * 10
        utf_8_snippet = b'\xc3\xa5' * 10
        test_file = io.StringIO("Windows line\r\nMac line\rUnix line\n" + latin_1_snippet.decode('latin-1'))
        test_file.name = "unnamed"

        r = self.client.post(url, dict(txt=test_file))
        self.assertEqual(r.status_code, 302)

        charter = Document.objects.get(name="charter-ietf-%s" % group.acronym)
        self.assertEqual(charter.rev, next_revision(prev_rev))
        self.assertTrue("new_revision" in charter.latest_event().type)

        with io.open(os.path.join(self.charter_dir, charter.canonical_name() + "-" + charter.rev + ".txt"), encoding='utf-8') as f:
            self.assertEqual(f.read(), "Windows line\nMac line\nUnix line\n" + utf_8_snippet.decode('utf-8'))

    def test_submit_initial_charter(self):
        group = GroupFactory(type_id='wg',acronym='mars',list_email='mars-wg@ietf.org')

        url = urlreverse('ietf.doc.views_charter.submit', kwargs=dict(name=charter_name_for_group(group)))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form input[name=txt]')), 1)

        # create charter
        test_file = io.StringIO("Simple test")
        test_file.name = "unnamed"

        r = self.client.post(url, dict(txt=test_file))
        self.assertEqual(r.status_code, 302)

        charter = Document.objects.get(name="charter-ietf-%s" % group.acronym)
        self.assertEqual(charter.rev, "00-00")
        self.assertTrue("new_revision" in charter.latest_event().type)

        group = Group.objects.get(pk=group.pk)
        self.assertEqual(group.charter, charter)

    def test_edit_review_announcement_text(self):
        area = GroupFactory(type_id='area')
        RoleFactory(name_id='ad',group=area,person=Person.objects.get(user__username='ad'))
        charter = CharterFactory(group__parent=area,group__list_email='mars-wg@ietf.org')
        group = charter.group

        url = urlreverse('ietf.doc.views_charter.review_announcement_text', kwargs=dict(name=charter.name))
        self.client.logout()
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('textarea[name=announcement_text]')), 1)
        self.assertEqual(len(q('textarea[name=new_work_text]')), 1)

        by = Person.objects.get(user__username="secretary")

        (e1, e2) = default_review_text(group, charter, by)
        announcement_text = e1.text
        new_work_text = e2.text

        empty_outbox()
        r = self.client.post(url, dict(
                announcement_text=announcement_text,
                new_work_text=new_work_text,
                send_both="1"))
        self.assertEqual(len(outbox), 2)
        self.assertTrue(all(['WG Review' in m['Subject'] for m in outbox]))
        self.assertIn('ietf-announce@', outbox[0]['To'])
        self.assertIn('mars-wg@', outbox[0]['Cc'])
        self.assertIn('new-work@', outbox[1]['To'])
        self.assertIsNotNone(outbox[0]['Reply-To'])
        self.assertIsNotNone(outbox[1]['Reply-To'])
        self.assertIn('iesg@ietf.org', outbox[0]['Reply-To'])
        self.assertIn('iesg@ietf.org', outbox[1]['Reply-To'])

        empty_outbox()
        r = self.client.post(url, dict(
                announcement_text=announcement_text,
                new_work_text=new_work_text,
                send_annc_only="1"))
        self.assertEqual(len(outbox), 1)
        self.assertTrue('ietf-announce@' in outbox[0]['To'])

        empty_outbox()
        r = self.client.post(url, dict(
                announcement_text=announcement_text,
                new_work_text=new_work_text,
                send_nw_only="1"))
        self.assertEqual(len(outbox), 1)
        self.assertTrue('new-work@' in outbox[0]['To'])

        # save
        r = self.client.post(url, dict(
                announcement_text="This is a simple test.",
                new_work_text="New work gets something different.",
                save_text="1"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue("This is a simple test" in charter.latest_event(WriteupDocEvent, type="changed_review_announcement").text)
        self.assertTrue("New work gets something different." in charter.latest_event(WriteupDocEvent, type="changed_new_work_text").text)

        # test regenerate
        r = self.client.post(url, dict(
                announcement_text="This is a simple test.",
                new_work_text="Too simple perhaps?",
                regenerate_text="1"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        charter = Document.objects.get(name=charter.name)
        self.assertTrue(group.name in charter.latest_event(WriteupDocEvent, type="changed_review_announcement").text)
        self.assertTrue(charter.group.name in charter.latest_event(WriteupDocEvent, type="changed_new_work_text").text)

    def test_rg_edit_review_announcement_text(self):
        irtf = Group.objects.get(acronym='irtf')
        charter = CharterFactory(
            group__acronym = 'somerg',
            group__type_id = 'rg',
            group__list_email = 'somerg@ietf.org',
            group__parent = irtf,
        )
        group = charter.group

        url = urlreverse('ietf.doc.views_charter.review_announcement_text', kwargs=dict(name=charter.name))
        self.client.logout()
        login_testing_unauthorized(self, "secretary", url)

        by = Person.objects.get(user__username="secretary")
        (e1, e2) = default_review_text(group, charter, by)
        announcement_text = e1.text
        new_work_text = e2.text

        empty_outbox()
        r = self.client.post(url, dict(
                announcement_text=announcement_text,
                new_work_text=new_work_text,
                send_both="1"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(outbox), 2)
        self.assertTrue(all(['RG Review' in m['Subject'] for m in outbox]))
        self.assertTrue('ietf-announce@' in outbox[0]['To'])
        self.assertTrue('somerg@' in outbox[0]['Cc'])
        self.assertTrue('new-work@' in outbox[1]['To'])
        self.assertIsNotNone(outbox[0]['Reply-To'])
        self.assertIsNotNone(outbox[1]['Reply-To'])
        self.assertTrue('irsg@irtf.org' in outbox[0]['Reply-To'])
        self.assertTrue('irsg@irtf.org' in outbox[1]['Reply-To'])

    def test_edit_action_announcement_text(self):
        area = GroupFactory(type_id='area')
        RoleFactory(name_id='ad',group=area,person=Person.objects.get(user__username='ad'))
        charter = CharterFactory(group__parent=area)
        group = charter.group

        url = urlreverse('ietf.doc.views_charter.action_announcement_text', kwargs=dict(name=charter.name))
        self.client.logout()
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('textarea[name=announcement_text]')), 1)

        # save
        r = self.client.post(url, dict(
                announcement_text="This is a simple test.",
                save_text="1"))
        self.assertEqual(r.status_code, 302)
        charter = Document.objects.get(name=charter.name)
        self.assertTrue("This is a simple test" in charter.latest_event(WriteupDocEvent, type="changed_action_announcement").text)

        # test regenerate
        r = self.client.post(url, dict(
                announcement_text="This is a simple test.",
                regenerate_text="1"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        charter = Document.objects.get(name=charter.name)
        self.assertTrue(group.name in charter.latest_event(WriteupDocEvent, type="changed_action_announcement").text)

    def test_edit_ballot_writeupnotes(self):
        area = GroupFactory(type_id='area')
        RoleFactory(name_id='ad',group=area,person=Person.objects.get(user__username='ad'))
        charter = CharterFactory(group__parent=area)
        by = Person.objects.get(user__username="secretary")

        BallotDocEvent.objects.create(
            type="created_ballot",
            ballot_type=BallotType.objects.get(doc_type="charter", slug="approve"),
            by=by,
            doc=charter,
            rev=charter.rev,
            desc="Created ballot",
            )

        url = urlreverse('ietf.doc.views_charter.ballot_writeupnotes', kwargs=dict(name=charter.name))
        login_testing_unauthorized(self, "secretary", url)

        e = default_action_text(charter.group, charter, by)
        e.save()

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('textarea[name=ballot_writeup]')), 1)

        # save
        r = self.client.post(url, dict(
            ballot_writeup="This is a simple test.",
            save_ballot_writeup="1"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("This is a simple test" in charter.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text").text)

        # send
        empty_outbox()
        r = self.client.post(url, dict(
            ballot_writeup="This is a simple test.",
            send_ballot="1"))
        self.assertEqual(len(outbox), 1)
        self.assertTrue('Evaluation' in outbox[0]['Subject'])
        
    def test_approve(self):
        area = GroupFactory(type_id='area')
        RoleFactory(name_id='ad',group=area,person=Person.objects.get(user__username='ad'))
        charter = CharterFactory(group__acronym='ames',group__list_email='ames-wg@ietf.org',group__parent=area,group__state_id='bof')
        group = charter.group
        RoleFactory(name_id='chair',group=group,person__name='Ames Man',person__user__email='ameschairman@example.org')
        RoleFactory(name_id='secr',group=group,person__name='Secretary',person__user__email='amessecretary@example.org')

        url = urlreverse('ietf.doc.views_charter.approve', kwargs=dict(name=charter.name))
        login_testing_unauthorized(self, "secretary", url)

        self.write_charter_file(charter)

        p = Person.objects.get(name="Areað Irector")

        BallotDocEvent.objects.create(
            type="created_ballot",
            ballot_type=BallotType.objects.get(doc_type="charter", slug="approve"),
            by=p,
            doc=charter,
            rev=charter.rev,
            desc="Created ballot",
            )

        charter.set_state(State.objects.get(used=True, type="charter", slug="iesgrev"))

        due_date = datetime.date.today() + datetime.timedelta(days=180)
        m1 = GroupMilestone.objects.create(group=group,
                                           state_id="active",
                                           desc="Has been copied",
                                           due=due_date,
                                           resolved="")
        GroupMilestone.objects.create(group=group,
                                      state_id="active",
                                      desc="To be deleted",
                                      due=due_date,
                                      resolved="")
        GroupMilestone.objects.create(group=group,
                                      state_id="charter",
                                      desc="Has been copied",
                                      due=due_date,
                                      resolved="")
        m4 = GroupMilestone.objects.create(group=group,
                                           state_id="charter",
                                           desc="New charter milestone",
                                           due=due_date,
                                           resolved="")

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('[type=submit]:contains("Send announcement")'))
        self.assertEqual(len(q('pre')), 1)

        # approve
        empty_outbox()

        r = self.client.post(url, dict())
        self.assertEqual(r.status_code, 302)

        charter = Document.objects.get(name=charter.name)
        self.assertEqual(charter.get_state_slug(), "approved")
        self.assertTrue(not charter.ballot_open("approve"))

        self.assertEqual(charter.rev, "01")
        self.assertTrue(os.path.exists(os.path.join(self.charter_dir, "charter-ietf-%s-%s.txt" % (group.acronym, charter.rev))))

        self.assertEqual(len(outbox), 2)
        #
        self.assertTrue("approved" in outbox[0]['Subject'].lower())
        self.assertTrue("iesg-secretary" in outbox[0]['To'])
        body = get_payload_text(outbox[0])
        for word in ["WG",   "/wg/ames/about/",
            "Charter", "/doc/charter-ietf-ames/", ]:
            self.assertIn(word, body)
        #
        self.assertTrue("WG Action" in outbox[1]['Subject'])
        self.assertTrue("ietf-announce" in outbox[1]['To'])
        self.assertTrue("ames-wg@ietf.org" in outbox[1]['Cc'])
        body = get_payload_text(outbox[1])
        for word in ["Chairs", "Ames Man <ameschairman@example.org>",
            "Secretaries", "Secretary <amessecretary@example.org>",
            "Assigned Area Director", "Areað Irector <aread@example.org>",
            "Area Directors", "Mailing list", "ames-wg@ietf.org",
            "Charter", "/doc/charter-ietf-ames/", "Milestones"]:
            self.assertIn(word, body)

        self.assertEqual(group.groupmilestone_set.filter(state="charter").count(), 0)
        self.assertEqual(group.groupmilestone_set.filter(state="active").count(), 2)
        self.assertEqual(group.groupmilestone_set.filter(state="active", desc=m1.desc).count(), 1)
        self.assertEqual(group.groupmilestone_set.filter(state="active", desc=m4.desc).count(), 1)

    def test_charter_with_milestones(self):
        charter = CharterFactory()

        NewRevisionDocEvent.objects.create(doc=charter,
                                           type="new_revision",
                                           rev=charter.rev,
                                           by=Person.objects.get(name="(System)"))

        m = GroupMilestone.objects.create(group=charter.group,
                                          state_id="active",
                                          desc="Test milestone",
                                          due=datetime.date.today(),
                                          resolved="")

        url = urlreverse('ietf.doc.views_charter.charter_with_milestones_txt', kwargs=dict(name=charter.name, rev=charter.rev))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, m.desc)

    def test_chartering_from_bof(self):
        ad_role = RoleFactory(group__type_id='area',name_id='ad')
        charter = CharterFactory(group__type_id='wg',group__state_id='bof',group__parent=ad_role.group)
        e1,_ = default_review_text(charter.group, charter, Person.objects.get(name="(System)"))
        self.assertTrue('A new IETF WG has been proposed' in e1.text)
