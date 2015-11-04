# -*- coding: utf-8 -*-
import os
import shutil
import json
import datetime

from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse

from pyquery import PyQuery

from ietf.doc.models import DocEvent, BallotDocEvent, BallotPositionDocEvent, TelechatDocEvent
from ietf.doc.models import Document, DocAlias, State, RelatedDocument
from ietf.group.models import Group, GroupMilestone
from ietf.iesg.agenda import get_agenda_date, agenda_data
from ietf.iesg.models import TelechatDate
from ietf.name.models import StreamName
from ietf.person.models import Person
from ietf.utils.test_data import make_test_data
from ietf.utils.test_utils import TestCase, login_testing_unauthorized, unicontent

class IESGTests(TestCase):
    def test_feed(self):
        draft = make_test_data()
        draft.set_state(State.objects.get(type="draft-iesg", slug="iesg-eva"))

        pos = BallotPositionDocEvent()
        pos.ballot = draft.latest_event(BallotDocEvent, type="created_ballot")
        pos.pos_id = "discuss"
        pos.type = "changed_ballot_position"
        pos.doc = draft
        pos.ad = pos.by = Person.objects.get(user__username="ad")
        pos.save()

        r = self.client.get(urlreverse("ietf.iesg.views.discusses"))
        self.assertEqual(r.status_code, 200)

        self.assertTrue(draft.name in unicontent(r))
        self.assertTrue(pos.ad.plain_name() in unicontent(r))

    def test_milestones_needing_review(self):
        draft = make_test_data()

        m = GroupMilestone.objects.create(group=draft.group,
                                          state_id="review",
                                          desc="Test milestone",
                                          due=datetime.date.today())

        url = urlreverse("ietf.iesg.views.milestones_needing_review")
        login_testing_unauthorized(self, "ad", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(m.desc in unicontent(r))

    def test_review_decisions(self):
        draft = make_test_data()

        e = DocEvent(type="iesg_approved")
        e.doc = draft
        e.by = Person.objects.get(name="Areað Irector")
        e.save()

        url = urlreverse('ietf.iesg.views.review_decisions')

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.name in unicontent(r))

class IESGAgendaTests(TestCase):
    def setUp(self):
        make_test_data()

        ise_draft = Document.objects.get(name="draft-imaginary-independent-submission")
        ise_draft.stream = StreamName.objects.get(slug="ise")
        ise_draft.save()

        self.telechat_docs = {
            "ietf_draft": Document.objects.get(name="draft-ietf-mars-test"),
            "ise_draft": ise_draft,
            "conflrev": Document.objects.get(name="conflict-review-imaginary-irtf-submission"),
            "statchg": Document.objects.get(name="status-change-imaginary-mid-review"),
            "charter": Document.objects.filter(type="charter")[0],
            }

        by = Person.objects.get(name="Areað Irector")
        date = get_agenda_date()

        self.draft_dir = os.path.abspath("tmp-agenda-draft-dir")
        if not os.path.exists(self.draft_dir):
            os.mkdir(self.draft_dir)
        settings.INTERNET_DRAFT_PATH = self.draft_dir

        for d in self.telechat_docs.values():
            TelechatDocEvent.objects.create(type="scheduled_for_telechat",
                                            doc=d,
                                            by=by,
                                            telechat_date=date,
                                            returning_item=True)


    def tearDown(self):
        shutil.rmtree(self.draft_dir)

    def test_fill_in_agenda_docs(self):
        draft = self.telechat_docs["ietf_draft"]
        statchg = self.telechat_docs["statchg"]
        conflrev = self.telechat_docs["conflrev"]
        charter = self.telechat_docs["charter"]

        # put on agenda
        date = datetime.date.today() + datetime.timedelta(days=50)
        TelechatDate.objects.create(date=date)
        telechat_event = TelechatDocEvent.objects.create(
            type="scheduled_for_telechat",
            doc=draft,
            by=Person.objects.get(name="Areað Irector"),
            telechat_date=date,
            returning_item=False)
        date_str = date.isoformat()

        # 2.1 protocol WG submissions
        draft.intended_std_level_id = "ps"
        draft.group = Group.objects.get(acronym="mars")
        draft.save()
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
        draft.save()
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
        draft.save()
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
        draft.save()
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
            target=DocAlias.objects.filter(name__startswith='rfc', document__std_level="ps")[0],
            relationship_id="tohist")

        statchg.group = Group.objects.get(acronym="mars")
        statchg.save()
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
        relation.target = DocAlias.objects.filter(name__startswith='rfc', document__std_level="inf")[0]
        relation.save()

        statchg.group = Group.objects.get(acronym="mars")
        statchg.save()
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
        conflrev.save()
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
        charter.save()

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

    def test_feed(self):
        r = self.client.get("/feed/iesg-agenda/")
        self.assertEqual(r.status_code, 200)

        for d in self.telechat_docs.values():
            self.assertTrue(d.name in unicontent(r))
            self.assertTrue(d.title in unicontent(r))

    def test_agenda_json(self):
        r = self.client.get(urlreverse("ietf.iesg.views.agenda_json"))
        self.assertEqual(r.status_code, 200)

        for k, d in self.telechat_docs.iteritems():
            if d.type_id == "charter":
                self.assertTrue(d.group.name in unicontent(r), "%s not in response" % k)
                self.assertTrue(d.group.acronym in unicontent(r), "%s acronym not in response" % k)
            else:
                self.assertTrue(d.name in unicontent(r), "%s not in response" % k)
                self.assertTrue(d.title in unicontent(r), "%s title not in response" % k)

        self.assertTrue(json.loads(r.content))

    def test_agenda(self):
        r = self.client.get(urlreverse("ietf.iesg.views.agenda"))
        self.assertEqual(r.status_code, 200)

        for k, d in self.telechat_docs.iteritems():
            self.assertTrue(d.name in unicontent(r), "%s not in response" % k)
            self.assertTrue(d.title in unicontent(r), "%s title not in response" % k)

    def test_agenda_txt(self):
        r = self.client.get(urlreverse("ietf.iesg.views.agenda_txt"))
        self.assertEqual(r.status_code, 200)

        for k, d in self.telechat_docs.iteritems():
            if d.type_id == "charter":
                self.assertTrue(d.group.name in unicontent(r), "%s not in response" % k)
                self.assertTrue(d.group.acronym in unicontent(r), "%s acronym not in response" % k)
            else:
                self.assertTrue(d.name in unicontent(r), "%s not in response" % k)
                self.assertTrue(d.title in unicontent(r), "%s title not in response" % k)

    def test_agenda_scribe_template(self):
        r = self.client.get(urlreverse("ietf.iesg.views.agenda_scribe_template"))
        self.assertEqual(r.status_code, 200)

        for k, d in self.telechat_docs.iteritems():
            if d.type_id == "charter":
                continue # scribe template doesn't contain chartering info

            self.assertTrue(d.name in unicontent(r), "%s not in response" % k)
            self.assertTrue(d.title in unicontent(r), "%s title not in response" % k)

    def test_agenda_moderator_package(self):
        url = urlreverse("ietf.iesg.views.agenda_moderator_package")
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        for k, d in self.telechat_docs.iteritems():
            if d.type_id == "charter":
                self.assertTrue(d.group.name in unicontent(r), "%s not in response" % k)
                self.assertTrue(d.group.acronym in unicontent(r), "%s acronym not in response" % k)
            else:
                self.assertTrue(d.name in unicontent(r), "%s not in response" % k)
                self.assertTrue(d.title in unicontent(r), "%s title not in response" % k)

    def test_agenda_package(self):
        url = urlreverse("ietf.iesg.views.agenda_package")
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        for k, d in self.telechat_docs.iteritems():
            if d.type_id == "charter":
                self.assertTrue(d.group.name in unicontent(r), "%s not in response" % k)
                self.assertTrue(d.group.acronym in unicontent(r), "%s acronym not in response" % k)
            else:
                self.assertTrue(d.name in unicontent(r), "%s not in response" % k)
                self.assertTrue(d.title in unicontent(r), "%s title not in response" % k)

    def test_agenda_documents_txt(self):
        url = urlreverse("ietf.iesg.views.agenda_documents_txt")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        for k, d in self.telechat_docs.iteritems():
            self.assertTrue(d.name in unicontent(r), "%s not in response" % k)

    def test_agenda_documents(self):
        url = urlreverse("ietf.iesg.views.agenda_documents")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        for k, d in self.telechat_docs.iteritems():
            self.assertTrue(d.name in unicontent(r), "%s not in response" % k)
            self.assertTrue(d.title in unicontent(r), "%s title not in response" % k)

    def test_agenda_telechat_docs(self):
        d1 = self.telechat_docs["ietf_draft"]
        d2 = self.telechat_docs["ise_draft"]

        d1_filename = "%s-%s.txt" % (d1.name, d1.rev)
        d2_filename = "%s-%s.txt" % (d2.name, d2.rev)

        with open(os.path.join(self.draft_dir, d1_filename), "w") as f:
            f.write("test content")

        url = urlreverse("ietf.iesg.views.telechat_docs_tarfile", kwargs=dict(date=get_agenda_date().isoformat()))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        import tarfile, StringIO

        tar = tarfile.open(None, fileobj=StringIO.StringIO(r.content))
        names = tar.getnames()
        self.assertTrue(d1_filename in names)
        self.assertTrue(d2_filename not in names)
        self.assertTrue("manifest.txt" in names)

        f = tar.extractfile(d1_filename)
        self.assertEqual(f.read(), "test content")

        f = tar.extractfile("manifest.txt")
        lines = list(f.readlines())
        self.assertTrue("Included" in [l for l in lines if d1_filename in l][0])
        self.assertTrue("Not found" in [l for l in lines if d2_filename in l][0])

class RescheduleOnAgendaTests(TestCase):
    def test_reschedule(self):
        draft = make_test_data()

        # add to schedule
        e = TelechatDocEvent(type="scheduled_for_telechat")
        e.doc = draft
        e.by = Person.objects.get(name="Areað Irector")
        e.telechat_date = TelechatDate.objects.active()[0].date
        e.returning_item = True
        e.save()
        
        form_id = draft.pk
        
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
        d_header_pos = r.content.find("IESG telechat %s" % d.isoformat())
        draft_pos = r.content[d_header_pos:].find(draft.name)
        self.assertTrue(draft_pos>0)

        self.assertTrue(draft.latest_event(TelechatDocEvent, "scheduled_for_telechat"))
        self.assertEqual(draft.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date, d)
        self.assertTrue(not draft.latest_event(TelechatDocEvent, "scheduled_for_telechat").returning_item)
        self.assertEqual(draft.docevent_set.count(), events_before + 1)

