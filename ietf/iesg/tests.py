# Copyright The IETF Trust 2009-2021, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import io
import os
import shutil
import tarfile

from pyquery import PyQuery

from django.conf import settings
from django.urls import reverse as urlreverse
from django.utils.encoding import force_bytes
from django.utils.html import escape

import debug                            # pyflakes:ignore

from ietf.doc.models import DocEvent, BallotPositionDocEvent, TelechatDocEvent
from ietf.doc.models import Document, DocAlias, State, RelatedDocument
from ietf.doc.factories import WgDraftFactory, IndividualDraftFactory, ConflictReviewFactory, BaseDocumentFactory, CharterFactory, WgRfcFactory, IndividualRfcFactory
from ietf.doc.utils import create_ballot_if_not_open
from ietf.group.factories import RoleFactory, GroupFactory
from ietf.group.models import Group, GroupMilestone, Role
from ietf.iesg.agenda import get_agenda_date, agenda_data
from ietf.iesg.models import TelechatDate
from ietf.name.models import StreamName
from ietf.person.models import Person
from ietf.utils.test_utils import TestCase, login_testing_unauthorized, unicontent
from ietf.iesg.factories import IESGMgmtItemFactory


class IESGTests(TestCase):
    def test_feed(self):
        draft = WgDraftFactory(states=[('draft','active'),('draft-iesg','iesg-eva')],ad=Person.objects.get(user__username='ad'))

        ad = Person.objects.get(user__username="ad")
        ballot = create_ballot_if_not_open(None, draft, ad, 'approve')
        pos = BallotPositionDocEvent()
        pos.ballot = ballot
        pos.pos_id = "discuss"
        pos.type = "changed_ballot_position"
        pos.doc = draft
        pos.rev = draft.rev
        pos.balloter = pos.by = Person.objects.get(user__username="ad")
        pos.save()

        r = self.client.get(urlreverse("ietf.iesg.views.discusses"))
        self.assertEqual(r.status_code, 200)

        self.assertContains(r, draft.name)
        self.assertContains(r, escape(pos.balloter.plain_name()))

    def test_milestones_needing_review(self):
        draft = WgDraftFactory()
        RoleFactory(name_id='ad',group=draft.group,person=Person.objects.get(user__username='ad'))

        m = GroupMilestone.objects.create(group=draft.group,
                                          state_id="review",
                                          desc="Test milestone",
                                          due=datetime.date.today())

        url = urlreverse("ietf.iesg.views.milestones_needing_review")
        login_testing_unauthorized(self, "ad", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, m.desc)
        draft.group.state_id = 'conclude'
        draft.group.save()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, m.desc)
        

    def test_review_decisions(self):
        draft = WgDraftFactory()

        e = DocEvent(type="iesg_approved")
        e.doc = draft
        e.rev = draft.rev
        e.by = Person.objects.get(name="Areað Irector")
        e.save()

        url = urlreverse('ietf.iesg.views.review_decisions')

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.name)

    def test_photos(self):
        url = urlreverse("ietf.iesg.views.photos")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        ads = Role.objects.filter(group__type='area', group__state='active', name_id='ad')
        self.assertEqual(len(q('div.photo-thumbnail img')), ads.count())
        
class IESGAgendaTests(TestCase):
    def setUp(self):
        mars = GroupFactory(acronym='mars',parent=Group.objects.get(acronym='farfut'))
        wgdraft = WgDraftFactory(name='draft-ietf-mars-test', group=mars, intended_std_level_id='ps')
        rfc = IndividualRfcFactory.create(stream_id='irtf', other_aliases=['rfc6666',], states=[('draft','rfc'),('draft-iesg','pub')], std_level_id='inf', )
        wgdraft.relateddocument_set.create(target=rfc.docalias.get(name='rfc6666'), relationship_id='refnorm')
        ise_draft = IndividualDraftFactory(name='draft-imaginary-independent-submission')
        ise_draft.stream = StreamName.objects.get(slug="ise")
        ise_draft.save_with_history([DocEvent(doc=ise_draft, rev=ise_draft.rev, type="changed_stream", by=Person.objects.get(user__username="secretary"), desc="Test")])
        ConflictReviewFactory(name='conflict-review-imaginary-irtf-submission', review_of=ise_draft)
        BaseDocumentFactory(type_id='statchg',name='status-change-imaginary-mid-review')
        WgRfcFactory(std_level_id='inf')
        WgRfcFactory(std_level_id='ps')
        CharterFactory(states=[('charter','iesgrev')])

        self.telechat_docs = {
            "ietf_draft": Document.objects.get(name="draft-ietf-mars-test"),
            "ise_draft": ise_draft,
            "conflrev": Document.objects.get(name="conflict-review-imaginary-irtf-submission"),
            "statchg": Document.objects.get(name="status-change-imaginary-mid-review"),
            "charter": Document.objects.filter(type="charter")[0],
            }

        by = Person.objects.get(name="Areað Irector")
        date = get_agenda_date()

        self.draft_dir = self.tempdir('agenda-draft')
        self.saved_internet_draft_path = settings.INTERNET_DRAFT_PATH
        settings.INTERNET_DRAFT_PATH = self.draft_dir

        for d in list(self.telechat_docs.values()):
            TelechatDocEvent.objects.create(type="scheduled_for_telechat",
                                            doc=d,
                                            rev=d.rev,
                                            by=by,
                                            telechat_date=date,
                                            returning_item=True)

        self.mgmt_items = [ ]
        for i in range(0, 10):
            self.mgmt_items.append(IESGMgmtItemFactory())

    def tearDown(self):
        settings.INTERNET_DRAFT_PATH = self.saved_internet_draft_path
        shutil.rmtree(self.draft_dir)

    def test_fill_in_agenda_docs(self):
        draft = self.telechat_docs["ietf_draft"]
        statchg = self.telechat_docs["statchg"]
        conflrev = self.telechat_docs["conflrev"]
        charter = self.telechat_docs["charter"]
        mgmtitem = self.mgmt_items

        # put on agenda
        date = datetime.date.today() + datetime.timedelta(days=50)
        TelechatDate.objects.create(date=date)
        telechat_event = TelechatDocEvent.objects.create(
            type="scheduled_for_telechat",
            doc=draft,
            rev=draft.rev,
            by=Person.objects.get(name="Areað Irector"),
            telechat_date=date,
            returning_item=False)
        date_str = date.isoformat()

        # 2.1 protocol WG submissions
        draft.intended_std_level_id = "ps"
        draft.group = GroupFactory(acronym="mars")
        draft.save_with_history([DocEvent.objects.create(doc=draft, rev=draft.rev, type="changed_group", by=Person.objects.get(user__username="secretary"), desc="Test")])
        draft.set_state(State.objects.get(type="draft-iesg", slug="iesg-eva"))
        self.assertTrue(draft in agenda_data(date_str)["sections"]["2.1.1"]["docs"])

        telechat_event.returning_item = True
        telechat_event.save()
        self.assertTrue(draft in agenda_data(date_str)["sections"]["2.1.2"]["docs"])

        telechat_event.returning_item = False
        telechat_event.save()
        draft.set_state(State.objects.get(type="draft-iesg", slug="pub-req"))
        self.assertTrue(draft in agenda_data(date_str)["sections"]["2.1.3"]["docs"])

        # 2.2 protocol individual submissions
        draft.group = Group.objects.get(type="individ")
        draft.save_with_history([DocEvent.objects.create(doc=draft, rev=draft.rev, type="changed_group", by=Person.objects.get(user__username="secretary"), desc="Test")])
        draft.set_state(State.objects.get(type="draft-iesg", slug="iesg-eva"))
        self.assertTrue(draft in agenda_data(date_str)["sections"]["2.2.1"]["docs"])

        telechat_event.returning_item = True
        telechat_event.save()
        self.assertTrue(draft in agenda_data(date_str)["sections"]["2.2.2"]["docs"])

        telechat_event.returning_item = False
        telechat_event.save()
        draft.set_state(State.objects.get(type="draft-iesg", slug="pub-req"))
        self.assertTrue(draft in agenda_data(date_str)["sections"]["2.2.3"]["docs"])

        # 3.1 document WG submissions
        draft.intended_std_level_id = "inf"
        draft.group = Group.objects.get(acronym="mars")
        draft.save_with_history([DocEvent.objects.create(doc=draft, rev=draft.rev, type="changed_group", by=Person.objects.get(user__username="secretary"), desc="Test")])
        draft.set_state(State.objects.get(type="draft-iesg", slug="iesg-eva"))
        self.assertTrue(draft in agenda_data(date_str)["sections"]["3.1.1"]["docs"])

        telechat_event.returning_item = True
        telechat_event.save()
        self.assertTrue(draft in agenda_data(date_str)["sections"]["3.1.2"]["docs"])

        telechat_event.returning_item = False
        telechat_event.save()
        draft.set_state(State.objects.get(type="draft-iesg", slug="pub-req"))
        self.assertTrue(draft in agenda_data(date_str)["sections"]["3.1.3"]["docs"])

        # 3.2 document individual submissions
        draft.group = Group.objects.get(type="individ")
        draft.save_with_history([DocEvent.objects.create(doc=draft, rev=draft.rev, type="changed_group", by=Person.objects.get(user__username="secretary"), desc="Test")])
        draft.set_state(State.objects.get(type="draft-iesg", slug="iesg-eva"))
        self.assertTrue(draft in agenda_data(date_str)["sections"]["3.2.1"]["docs"])

        telechat_event.returning_item = True
        telechat_event.save()
        self.assertTrue(draft in agenda_data(date_str)["sections"]["3.2.2"]["docs"])

        telechat_event.returning_item = False
        telechat_event.save()
        draft.set_state(State.objects.get(type="draft-iesg", slug="pub-req"))
        self.assertTrue(draft in agenda_data(date_str)["sections"]["3.2.3"]["docs"])

        # 2.3 protocol status changes
        telechat_event.doc = statchg
        telechat_event.save()

        relation = RelatedDocument.objects.create(
            source=statchg,
            target=DocAlias.objects.filter(name__startswith='rfc', docs__std_level="ps")[0],
            relationship_id="tohist")

        statchg.group = Group.objects.get(acronym="mars")
        statchg.save_with_history([DocEvent.objects.create(doc=statchg, rev=statchg.rev, type="changed_group", by=Person.objects.get(user__username="secretary"), desc="Test")])
        statchg.set_state(State.objects.get(type="statchg", slug="iesgeval"))
        self.assertTrue(statchg in agenda_data(date_str)["sections"]["2.3.1"]["docs"])

        telechat_event.returning_item = True
        telechat_event.save()
        self.assertTrue(statchg in agenda_data(date_str)["sections"]["2.3.2"]["docs"])

        telechat_event.returning_item = False
        telechat_event.save()
        statchg.set_state(State.objects.get(type="statchg", slug="adrev"))
        self.assertTrue(statchg in agenda_data(date_str)["sections"]["2.3.3"]["docs"])
        
        # 3.3 document status changes
        relation.target = DocAlias.objects.filter(name__startswith='rfc', docs__std_level="inf")[0]
        relation.save()

        statchg.group = Group.objects.get(acronym="mars")
        statchg.save_with_history([DocEvent.objects.create(doc=statchg, rev=statchg.rev, type="changed_group", by=Person.objects.get(user__username="secretary"), desc="Test")])
        statchg.set_state(State.objects.get(type="statchg", slug="iesgeval"))
        self.assertTrue(statchg in agenda_data(date_str)["sections"]["3.3.1"]["docs"])

        telechat_event.returning_item = True
        telechat_event.save()
        self.assertTrue(statchg in agenda_data(date_str)["sections"]["3.3.2"]["docs"])

        telechat_event.returning_item = False
        telechat_event.save()
        statchg.set_state(State.objects.get(type="statchg", slug="adrev"))
        self.assertTrue(statchg in agenda_data(date_str)["sections"]["3.3.3"]["docs"])

        # 3.4 IRTF/ISE conflict reviews
        telechat_event.doc = conflrev
        telechat_event.save()

        conflrev.group = Group.objects.get(acronym="mars")
        conflrev.save_with_history([DocEvent.objects.create(doc=conflrev, rev=conflrev.rev, type="changed_group", by=Person.objects.get(user__username="secretary"), desc="Test")])
        conflrev.set_state(State.objects.get(type="conflrev", slug="iesgeval"))
        self.assertTrue(conflrev in agenda_data(date_str)["sections"]["3.4.1"]["docs"])

        telechat_event.returning_item = True
        telechat_event.save()
        self.assertTrue(conflrev in agenda_data(date_str)["sections"]["3.4.2"]["docs"])

        telechat_event.returning_item = False
        telechat_event.save()
        conflrev.set_state(State.objects.get(type="conflrev", slug="needshep"))
        self.assertTrue(conflrev in agenda_data(date_str)["sections"]["3.4.3"]["docs"])

        # 4 WGs
        telechat_event.doc = charter
        telechat_event.save()

        charter.group = Group.objects.get(acronym="mars")
        charter.save_with_history([DocEvent.objects.create(doc=charter, rev=charter.rev, type="changed_group", by=Person.objects.get(user__username="secretary"), desc="Test")])

        charter.group.state_id = "bof"
        charter.group.save()

        charter.set_state(State.objects.get(type="charter", slug="infrev"))
        self.assertTrue(charter in agenda_data(date_str)["sections"]["4.1.1"]["docs"])

        charter.set_state(State.objects.get(type="charter", slug="iesgrev"))
        self.assertTrue(charter in agenda_data(date_str)["sections"]["4.1.2"]["docs"])

        charter.group.state_id = "active"
        charter.group.save()

        charter.set_state(State.objects.get(type="charter", slug="infrev"))
        self.assertTrue(charter in agenda_data(date_str)["sections"]["4.2.1"]["docs"])

        charter.set_state(State.objects.get(type="charter", slug="iesgrev"))
        self.assertTrue(charter in agenda_data(date_str)["sections"]["4.2.2"]["docs"])

        #for n, s in agenda_data(date_str)["sections"].iteritems():
        #    print n, s.get("docs") if "docs" in s else s["title"]

        # 10 Management Items
        for i, mi in enumerate(mgmtitem, start=1):
            s = "6." + str(i)
            self.assertEqual(mi.title, agenda_data(date_str)["sections"][s]['title'])

    def test_feed(self):
        r = self.client.get("/feed/iesg-agenda/")
        self.assertEqual(r.status_code, 200)

        for d in list(self.telechat_docs.values()):
            self.assertContains(r, d.name)
            self.assertContains(r, d.title)

    def test_agenda_json(self):
        r = self.client.get(urlreverse("ietf.iesg.views.agenda_json"))
        self.assertEqual(r.status_code, 200)

        for k, d in self.telechat_docs.items():
            if d.type_id == "charter":
                self.assertContains(r, d.group.name, msg_prefix="%s '%s' not in response" % (k, d.group.name))
                self.assertContains(r, d.group.acronym, msg_prefix="%s '%s' acronym not in response" % (k, d.group.acronym))
            else:
                self.assertContains(r, d.name, msg_prefix="%s '%s' not in response" % (k, d.name))
                self.assertContains(r, d.title, msg_prefix="%s '%s' title not in response" % (k, d.title))

        self.assertTrue(r.json())

    def test_agenda(self):
        r = self.client.get(urlreverse("ietf.iesg.views.agenda"))
        self.assertEqual(r.status_code, 200)

        for k, d in self.telechat_docs.items():
            if d.type_id == "charter":
                self.assertContains(r, d.group.name, msg_prefix="%s '%s' not in response" % (k, d.group.name))
                self.assertContains(r, d.group.acronym, msg_prefix="%s '%s' acronym not in response" % (k, d.group.acronym))
            else:
                self.assertContains(r, d.name, msg_prefix="%s '%s' not in response" % (k, d.name))
                self.assertContains(r, d.title, msg_prefix="%s '%s' title not in response" % (k, d.title))

        for i, mi in enumerate(self.mgmt_items, start=1):
            s = "6." + str(i)
            self.assertContains(r, s, msg_prefix="Section '%s' not in response" % s)
            self.assertContains(r, mi.title, msg_prefix="Management item title '%s' not in response" % mi.title)

        # Make sure the sort places 6.9 before 6.10
        self.assertLess(r.content.find(b"6.9"), r.content.find(b"6.10"))

    def test_agenda_txt(self):
        r = self.client.get(urlreverse("ietf.iesg.views.agenda_txt"))
        self.assertEqual(r.status_code, 200)

        for k, d in self.telechat_docs.items():
            if d.type_id == "charter":
                self.assertContains(r, d.group.name, msg_prefix="%s '%s' not in response" % (k, d.group.name))
                self.assertContains(r, d.group.acronym, msg_prefix="%s '%s' acronym not in response" % (k, d.group.acronym))
            else:
                self.assertContains(r, d.name, msg_prefix="%s '%s' not in response" % (k, d.name))
                self.assertContains(r, d.title, msg_prefix="%s '%s' title not in response" % (k, d.title))

        for i, mi in enumerate(self.mgmt_items, start=1):
            s = "6." + str(i)
            self.assertContains(r, s, msg_prefix="Section '%s' not in response" % s)
            self.assertContains(r, mi.title, msg_prefix="Management item title '%s' not in response" % mi.title)

        # Make sure the sort places 6.9 before 6.10
        self.assertLess(r.content.find(b"6.9"), r.content.find(b"6.10"))

    def test_agenda_scribe_template(self):
        r = self.client.get(urlreverse("ietf.iesg.views.agenda_scribe_template"))
        self.assertEqual(r.status_code, 200)

        for k, d in self.telechat_docs.items():
            if d.type_id == "charter":
                continue # scribe template doesn't contain chartering info

            self.assertContains(r, d.name, msg_prefix="%s '%s' not in response" % (k, d.name))
            self.assertContains(r, d.title, msg_prefix="%s '%s' title not in response" % (k, d.title))

    def test_agenda_moderator_package(self):
        url = urlreverse("ietf.iesg.views.agenda_moderator_package")
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        for k, d in self.telechat_docs.items():
            if d.type_id == "charter":
                self.assertContains(r, d.group.name, msg_prefix="%s '%s' not in response" % (k, d.group.name))
                self.assertContains(r, d.group.acronym, msg_prefix="%s '%s' acronym not in response" % (k, d.group.acronym))
            else:
                if d.type_id == "draft" and d.name == "draft-ietf-mars-test":
                    self.assertContains(r, d.name, msg_prefix="%s '%s' not in response" % (k, d.name))
                    self.assertContains(r, d.title, msg_prefix="%s '%s' title not in response" % (k, d.title))
                    self.assertContains(r, "Has downref: Yes", msg_prefix="%s downref not in response" % (k, ))
                    self.assertContains(r, "Add rfc6666", msg_prefix="%s downref not in response" % (k, ))
                else:
                    self.assertContains(r, d.name, msg_prefix="%s '%s' not in response" % (k, d.name))
                    self.assertContains(r, d.title, msg_prefix="%s '%s' title not in response" % (k, d.title))        

    def test_agenda_package(self):
        url = urlreverse("ietf.iesg.views.agenda_package")
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        for k, d in self.telechat_docs.items():
            if d.type_id == "charter":
                self.assertContains(r, d.group.name, msg_prefix="%s '%s' not in response" % (k, d.group.name, ))
                self.assertContains(r, d.group.acronym, msg_prefix="%s '%s' acronym not in response" % (k, d.group.acronym, ))
            else:
                self.assertContains(r, d.name, msg_prefix="%s '%s' not in response" % (k, d.name, ))
                self.assertContains(r, d.title, msg_prefix="%s '%s' title not in response" % (k, d.title, ))

    def test_agenda_documents_txt(self):
        url = urlreverse("ietf.iesg.views.agenda_documents_txt")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        for k, d in self.telechat_docs.items():
            self.assertContains(r, d.name, msg_prefix="%s '%s' not in response" % (k, d.name, ))

    def test_agenda_documents(self):
        url = urlreverse("ietf.iesg.views.agenda_documents")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        for k, d in self.telechat_docs.items():
            self.assertContains(r, d.name, msg_prefix="%s '%s' not in response" % (k, d.name, ))
            self.assertContains(r, d.title, msg_prefix="%s '%s' title not in response" % (k, d.title, ))

    def test_past_documents(self):
        url = urlreverse("ietf.iesg.views.past_documents")
        # We haven't put any documents on past telechats, so this should be empty
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        for k, d in self.telechat_docs.items():
            self.assertNotIn(d.name, unicontent(r))
            self.assertNotIn(d.title, unicontent(r))
        # Add the documents to a past telechat
        by = Person.objects.get(name="Areað Irector")
        date = datetime.date.today() - datetime.timedelta(days=14)
        approved = State.objects.get(type='draft-iesg', slug='approved')
        iesg_eval = State.objects.get(type='draft-iesg', slug='iesg-eva')
        for d in list(self.telechat_docs.values()):
            if d.type_id in ['draft', 'charter']:
                create_ballot_if_not_open(None, d, by, 'approve')
            TelechatDocEvent.objects.create(type="scheduled_for_telechat",
                doc=d, rev=d.rev, by=by, telechat_date=date, returning_item=False)
            s = d.get_state('draft-iesg')
            d.states.clear()
            if s and s.slug == 'pub-req':
                d.states.add(iesg_eval)
            else:
                d.states.add(approved)
        # Now check that they are present on the past documents page
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        for k, d in self.telechat_docs.items():
            if d.states.get(type='draft-iesg').slug in ['approved', 'iesg-eva', ]:
                self.assertIn(d.name, unicontent(r))
            else:
                self.assertNotIn(d.name, unicontent(r))

    def test_agenda_telechat_docs(self):
        d1 = self.telechat_docs["ietf_draft"]
        d2 = self.telechat_docs["ise_draft"]

        d1_filename = "%s-%s.txt" % (d1.name, d1.rev)
        d2_filename = "%s-%s.txt" % (d2.name, d2.rev)

        with io.open(os.path.join(self.draft_dir, d1_filename), "w") as f:
            f.write("test content")

        url = urlreverse("ietf.iesg.views.telechat_docs_tarfile", kwargs=dict(date=get_agenda_date().isoformat()))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        tar = tarfile.open(None, fileobj=io.BytesIO(r.content))
        names = tar.getnames()
        self.assertIn(d1_filename, names)
        self.assertNotIn(d2_filename, names)
        self.assertIn("manifest.txt", names)

        f = tar.extractfile(d1_filename)
        self.assertEqual(f.read(), b"test content")

        f = tar.extractfile("manifest.txt")
        lines = list(f.readlines())
        d1fn = force_bytes(d1_filename)
        d2fn = force_bytes(d2_filename)
        self.assertTrue(b"Included" in [l for l in lines if d1fn in l][0])
        self.assertTrue(b"Not found" in [l for l in lines if d2fn in l][0])

    def test_admin_change(self):
        draft = Document.objects.get(name="draft-ietf-mars-test")
        today = datetime.date.today()
        telechat_date = TelechatDate.objects.get(date=draft.telechat_date())
        url = urlreverse('admin:iesg_telechatdate_change', args=(telechat_date.id,))
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post(url, {'initial-date': telechat_date.date.strftime('%Y-%m-%d'), 'date':today.strftime('%Y-%m-%d')})
        self.assertRedirects(r, urlreverse('admin:iesg_telechatdate_changelist'))
        draft = Document.objects.get(name="draft-ietf-mars-test")
        self.assertEqual(draft.telechat_date(),today)

class RescheduleOnAgendaTests(TestCase):
    def test_reschedule(self):
        draft = WgDraftFactory()

        # add to schedule
        e = TelechatDocEvent(type="scheduled_for_telechat")
        e.doc = draft
        e.rev = draft.rev
        e.by = Person.objects.get(name="Areað Irector")
        e.telechat_date = TelechatDate.objects.active()[0].date
        e.returning_item = True
        e.save()
        
        form_id = draft.name
        
        url = urlreverse('ietf.iesg.views.agenda_documents')
        
        self.client.login(username="secretary", password="secretary+password")

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        
        self.assertEqual(len(q('form select[name=%s-telechat_date]' % form_id)), 1)
        self.assertEqual(len(q('form input[name=%s-clear_returning_item]' % form_id)), 1)

        # reschedule
        events_before = draft.docevent_set.count()
        d = TelechatDate.objects.active()[3].date

        r = self.client.post(url, { '%s-telechat_date' % form_id: d.isoformat(),
                                    '%s-clear_returning_item' % form_id: "1" })

        self.assertEqual(r.status_code, 302)

        # check that it moved below the right header in the DOM on the
        # agenda docs page
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        content = unicontent(r)
        d_header_pos = content.find("IESG telechat %s" % d.isoformat())
        draft_pos = content[d_header_pos:].find(draft.name)
        self.assertTrue(draft_pos>0)

        self.assertTrue(draft.latest_event(TelechatDocEvent, "scheduled_for_telechat"))
        self.assertEqual(draft.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date, d)
        self.assertTrue(not draft.latest_event(TelechatDocEvent, "scheduled_for_telechat").returning_item)
        self.assertEqual(draft.docevent_set.count(), events_before + 1)
