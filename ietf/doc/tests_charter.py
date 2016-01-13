# -*- coding: utf-8 -*-
# Copyright The IETF Trust 2011, All Rights Reserved

import os, shutil, datetime
from StringIO import StringIO
from pyquery import PyQuery

from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.doc.models import ( Document, State, BallotDocEvent, BallotType, NewRevisionDocEvent,
    TelechatDocEvent, WriteupDocEvent )
from ietf.doc.utils_charter import next_revision, default_review_text, default_action_text 
from ietf.group.models import Group, GroupMilestone
from ietf.iesg.models import TelechatDate
from ietf.person.models import Person
from ietf.utils.test_utils import TestCase, unicontent
from ietf.utils.mail import outbox, empty_outbox
from ietf.utils.test_data import make_test_data
from ietf.utils.test_utils import login_testing_unauthorized

class EditCharterTests(TestCase):
    def setUp(self):
        self.charter_dir = os.path.abspath("tmp-charter-dir")
        os.mkdir(self.charter_dir)
        settings.CHARTER_PATH = self.charter_dir

    def tearDown(self):
        shutil.rmtree(self.charter_dir)

    def test_startstop_process(self):
        make_test_data()

        group = Group.objects.get(acronym="mars")
        charter = group.charter

        for option in ("recharter", "abandon"):
            self.client.logout()
            url = urlreverse('charter_startstop_process', kwargs=dict(name=charter.name, option=option))
            login_testing_unauthorized(self, "secretary", url)

            # normal get
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)

            # post
            r = self.client.post(url, dict(message="test message"))
            self.assertEqual(r.status_code, 302)
            if option == "abandon":
                self.assertTrue("abandoned" in charter.latest_event(type="changed_document").desc.lower())
            else:
                self.assertTrue("state changed" in charter.latest_event(type="changed_state").desc.lower())

    def test_change_state(self):
        make_test_data()

        group = Group.objects.get(acronym="ames")
        charter = group.charter

        url = urlreverse('charter_change_state', kwargs=dict(name=charter.name))
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

            if slug in ("intrev", "iesgrev"):
                self.assertTrue(find_event("created_ballot"))

            self.assertEqual(len(outbox), 3 if slug=="intrev" else 2 )

            if slug=="intrev":
                self.assertIn("Internal WG Review", outbox[-3]['Subject'])
                self.assertIn("iab@", outbox[-3]['To'])
                self.assertIn("iesg@", outbox[-3]['To'])
                self.assertIn("A new IETF WG", outbox[-3].get_payload())
                body = outbox[-3].get_payload()
                for word in ["Chairs", "Ames Man <ameschairman@ietf.org>",
                    "Secretaries", "Secretary <amessecretary@ietf.org>",
                    "Assigned Area Director", "Areað Irector <aread@ietf.org>",
                    "Area Directors", "Mailing list", "ames-wg@ietf.org",
                    "Charter", "Milestones"]:
                    self.assertIn(word, body)

            self.assertIn("state changed", outbox[-2]['Subject'].lower())
            self.assertIn("iesg-secretary@", outbox[-2]['To'])
            body = outbox[-2].get_payload()
            for word in ["WG", "Charter", ]:
                self.assertIn(word, body)

            self.assertIn("State Update Notice", outbox[-1]['Subject'])
            self.assertIn("ames-chairs@", outbox[-1]['To'])
            body = outbox[-1].get_payload()
            for word in ["State changed", "ID Tracker URL", ]:
                self.assertIn(word, body)


        # Exercise internal review of a recharter
        group = Group.objects.get(acronym="mars")
        charter = group.charter
        url = urlreverse('charter_change_state', kwargs=dict(name=charter.name))
        empty_outbox()
        r = self.client.post(url, dict(charter_state=str(State.objects.get(used=True,type="charter",slug="intrev").pk), message="test"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue("A new charter" in outbox[-3].get_payload())
                    
    def test_edit_telechat_date(self):
        make_test_data()

        group = Group.objects.get(acronym="mars")
        charter = group.charter

        url = urlreverse('charter_telechat_date', kwargs=dict(name=charter.name))
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
        make_test_data()

        group = Group.objects.get(acronym="ames")
        charter = group.charter
        url = urlreverse('charter_telechat_date', kwargs=dict(name=charter.name))
        login_testing_unauthorized(self, "secretary", url)
        login = Person.objects.get(user__username="secretary")

        # Make it so that the charter has been through internal review, and passed its external review
        # ballot on a previous telechat 
        last_week = datetime.date.today()-datetime.timedelta(days=7)
        BallotDocEvent.objects.create(type='created_ballot',by=login,doc=charter,
                                      ballot_type=BallotType.objects.get(doc_type=charter.type,slug='r-extrev'),
                                      time=last_week)
        TelechatDocEvent.objects.create(type='scheduled_for_telechat',doc=charter,by=login,telechat_date=last_week,returning_item=False)
        BallotDocEvent.objects.create(type='created_ballot',by=login,doc=charter,
                                      ballot_type=BallotType.objects.get(doc_type=charter.type,slug='approve'))
        
        # Put the charter onto a future telechat and verify returning item is not set
        telechat_date = TelechatDate.objects.active()[1].date
        r = self.client.post(url, dict(name=group.name, acronym=group.acronym, telechat_date=telechat_date.isoformat()))
        self.assertEqual(r.status_code, 302)
        
        charter = Document.objects.get(name=charter.name)
        telechat_event = charter.latest_event(TelechatDocEvent, "scheduled_for_telechat")
        self.assertEqual(telechat_event.telechat_date, telechat_date)
        self.assertFalse(telechat_event.returning_item)

    def test_edit_notify(self):
        make_test_data()

        charter = Group.objects.get(acronym="mars").charter

        url = urlreverse('charter_edit_notify', kwargs=dict(name=charter.name))
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
        make_test_data()

        charter = Group.objects.get(acronym="mars").charter

        url = urlreverse('charter_edit_ad', kwargs=dict(name=charter.name))
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
        make_test_data()

        group = Group.objects.get(acronym="mars")
        charter = group.charter

        url = urlreverse('charter_submit', kwargs=dict(name=charter.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form input[name=txt]')), 1)

        # faulty post
        test_file = StringIO("\x10\x11\x12") # post binary file
        test_file.name = "unnamed"

        r = self.client.post(url, dict(txt=test_file))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("does not appear to be a text file" in unicontent(r))

        # post
        prev_rev = charter.rev

        latin_1_snippet = '\xe5' * 10
        utf_8_snippet = '\xc3\xa5' * 10
        test_file = StringIO("Windows line\r\nMac line\rUnix line\n" + latin_1_snippet)
        test_file.name = "unnamed"

        r = self.client.post(url, dict(txt=test_file))
        self.assertEqual(r.status_code, 302)

        charter = Document.objects.get(name="charter-ietf-%s" % group.acronym)
        self.assertEqual(charter.rev, next_revision(prev_rev))
        self.assertTrue("new_revision" in charter.latest_event().type)

        with open(os.path.join(self.charter_dir, charter.canonical_name() + "-" + charter.rev + ".txt")) as f:
            self.assertEqual(f.read(),
                              "Windows line\nMac line\nUnix line\n" + utf_8_snippet)

    def test_edit_review_announcement_text(self):
        draft = make_test_data()
        charter = draft.group.charter

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

        (e1, e2) = default_review_text(draft.group, charter, by)
        announcement_text = e1.text
        new_work_text = e2.text

        empty_outbox()
        r = self.client.post(url, dict(
                announcement_text=announcement_text,
                new_work_text=new_work_text,
                send_both="1"))
        self.assertEqual(len(outbox), 2)
        self.assertTrue(all(['WG Review' in m['Subject'] for m in outbox]))
        self.assertTrue('ietf-announce@' in outbox[0]['To'])
        self.assertTrue('mars-wg@' in outbox[0]['Cc'])
        self.assertTrue('new-work@' in outbox[1]['To'])

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
        self.assertTrue(draft.group.name in charter.latest_event(WriteupDocEvent, type="changed_review_announcement").text)
        self.assertTrue(draft.group.name in charter.latest_event(WriteupDocEvent, type="changed_new_work_text").text)

    def test_edit_action_announcement_text(self):
        draft = make_test_data()
        charter = draft.group.charter

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
        self.assertTrue("This is a simple test" in charter.latest_event(WriteupDocEvent, type="changed_action_announcement").text)

        # test regenerate
        r = self.client.post(url, dict(
                announcement_text="This is a simple test.",
                regenerate_text="1"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(draft.group.name in charter.latest_event(WriteupDocEvent, type="changed_action_announcement").text)

    def test_edit_ballot_writeupnotes(self):
        draft = make_test_data()
        charter = draft.group.charter
        by = Person.objects.get(user__username="secretary")

        BallotDocEvent.objects.create(
            type="created_ballot",
            ballot_type=BallotType.objects.get(doc_type="charter", slug="approve"),
            by=by,
            doc=charter,
            desc="Created ballot",
            )

        url = urlreverse('ietf.doc.views_charter.ballot_writeupnotes', kwargs=dict(name=charter.name))
        login_testing_unauthorized(self, "secretary", url)

        default_action_text(draft.group, charter, by)

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
        make_test_data()

        group = Group.objects.get(acronym="ames")
        charter = group.charter

        url = urlreverse('charter_approve', kwargs=dict(name=charter.name))
        login_testing_unauthorized(self, "secretary", url)

        with open(os.path.join(self.charter_dir, "%s-%s.txt" % (charter.canonical_name(), charter.rev)), "w") as f:
            f.write("This is a charter.")

        p = Person.objects.get(name="Areað Irector")

        BallotDocEvent.objects.create(
            type="created_ballot",
            ballot_type=BallotType.objects.get(doc_type="charter", slug="approve"),
            by=p,
            doc=charter,
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
        body = outbox[0].get_payload()
        for word in ["WG",   "/wg/ames/charter/",
            "Charter", "/doc/charter-ietf-ames/", ]:
            self.assertIn(word, body)
        #
        self.assertTrue("WG Action" in outbox[1]['Subject'])
        self.assertTrue("ietf-announce" in outbox[1]['To'])
        self.assertTrue("ames-wg@ietf.org" in outbox[1]['Cc'])
        body = outbox[1].get_payload()
        for word in ["Chairs", "Ames Man <ameschairman@ietf.org>",
            "Secretaries", "Secretary <amessecretary@ietf.org>",
            "Assigned Area Director", "Areað Irector <aread@ietf.org>",
            "Area Directors", "Mailing list", "ames-wg@ietf.org",
            "Charter", "/doc/charter-ietf-ames/", "Milestones"]:
            self.assertIn(word, body)

        self.assertEqual(group.groupmilestone_set.filter(state="charter").count(), 0)
        self.assertEqual(group.groupmilestone_set.filter(state="active").count(), 2)
        self.assertEqual(group.groupmilestone_set.filter(state="active", desc=m1.desc).count(), 1)
        self.assertEqual(group.groupmilestone_set.filter(state="active", desc=m4.desc).count(), 1)

    def test_charter_with_milestones(self):
        draft = make_test_data()
        charter = draft.group.charter

        NewRevisionDocEvent.objects.create(doc=charter,
                                           type="new_revision",
                                           rev=charter.rev,
                                           by=Person.objects.get(name="(System)"))

        m = GroupMilestone.objects.create(group=draft.group,
                                          state_id="active",
                                          desc="Test milestone",
                                          due=datetime.date.today(),
                                          resolved="")

        url = urlreverse('charter_with_milestones_txt', kwargs=dict(name=charter.name, rev=charter.rev))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(m.desc in unicontent(r))
