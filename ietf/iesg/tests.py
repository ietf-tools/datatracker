import os, shutil, json

import django.test
from django.core.urlresolvers import reverse as urlreverse
from django.conf import settings

from pyquery import PyQuery

from ietf.utils.test_utils import SimpleUrlTestCase, RealDatabaseTest, canonicalize_feed, login_testing_unauthorized
from ietf.utils.test_data import make_test_data
from ietf.doc.models import Document, DocEvent, TelechatDocEvent, State
from ietf.person.models import Person
from ietf.group.models import Group
from ietf.name.models import StreamName
from ietf.iesg.models import *
from ietf.iesg.agenda import get_agenda_date

class ReviewDecisionsTests(django.test.TestCase):
    def test_review_decisions(self):
        draft = make_test_data()

        e = DocEvent(type="iesg_approved")
        e.doc = draft
        e.by = Person.objects.get(name="Aread Irector")
        e.save()

        url = urlreverse('ietf.iesg.views.review_decisions')

        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        self.assertTrue(draft.name in r.content)


class IESGAgendaTests(django.test.TestCase):
    def setUp(self):
        make_test_data()

        ise_draft = Document.objects.get(name="draft-imaginary-independent-submission")
        ise_draft.stream = StreamName.objects.get(slug="ise")
        ise_draft.save()

        self.telechat_docs = {
            "ietf_draft": Document.objects.get(name="draft-ietf-mars-test"),
            "ise_draft": ise_draft,
            "conflrev": Document.objects.get(name="conflict-review-imaginary-irtf-submission"),
            "statusch": Document.objects.get(name="status-change-imaginary-mid-review"),
            "charter": Document.objects.filter(type="charter")[0],
            }

        by = Person.objects.get(name="Aread Irector")
        date = get_agenda_date()

        for d in self.telechat_docs.values():
            TelechatDocEvent.objects.create(type="scheduled_for_telechat",
                                            doc=d,
                                            by=by,
                                            telechat_date=date,
                                            returning_item=True)

    def test_feed(self):
        url = "/feed/iesg-agenda/"

        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)

        for d in self.telechat_docs.values():
            self.assertTrue(d.name in r.content)
            self.assertTrue(d.title in r.content)

    def test_agenda_json(self):
        r = self.client.get(urlreverse("ietf.iesg.views.agenda_json"))
        self.assertEquals(r.status_code, 200)

        for k, d in self.telechat_docs.iteritems():
            if d.type_id == "charter":
                self.assertTrue(d.group.name in r.content, "%s not in response" % k)
                self.assertTrue(d.group.acronym in r.content, "%s acronym not in response" % k)
            else:
                self.assertTrue(d.name in r.content, "%s not in response" % k)
                self.assertTrue(d.title in r.content, "%s title not in response" % k)

        self.assertTrue(json.loads(r.content))

    def test_agenda(self):
        r = self.client.get(urlreverse("ietf.iesg.views.agenda"))
        self.assertEquals(r.status_code, 200)

        for k, d in self.telechat_docs.iteritems():
            self.assertTrue(d.name in r.content, "%s not in response" % k)
            self.assertTrue(d.title in r.content, "%s title not in response" % k)

    def test_agenda_txt(self):
        r = self.client.get(urlreverse("ietf.iesg.views.agenda_txt"))
        self.assertEquals(r.status_code, 200)

        for k, d in self.telechat_docs.iteritems():
            if d.type_id == "charter":
                self.assertTrue(d.group.name in r.content, "%s not in response" % k)
                self.assertTrue(d.group.acronym in r.content, "%s acronym not in response" % k)
            else:
                self.assertTrue(d.name in r.content, "%s not in response" % k)
                self.assertTrue(d.title in r.content, "%s title not in response" % k)

    def test_agenda_scribe_template(self):
        r = self.client.get(urlreverse("ietf.iesg.views.agenda_scribe_template"))
        self.assertEquals(r.status_code, 200)

        for k, d in self.telechat_docs.iteritems():
            if d.type_id == "charter":
                continue # scribe template doesn't contain chartering info

            self.assertTrue(d.name in r.content, "%s not in response" % k)
            self.assertTrue(d.title in r.content, "%s title not in response" % k)

    def test_agenda_moderator_package(self):
        url = urlreverse("ietf.iesg.views.agenda_moderator_package")
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)

        for k, d in self.telechat_docs.iteritems():
            if d.type_id == "charter":
                self.assertTrue(d.group.name in r.content, "%s not in response" % k)
                self.assertTrue(d.group.acronym in r.content, "%s acronym not in response" % k)
            else:
                self.assertTrue(d.name in r.content, "%s not in response" % k)
                self.assertTrue(d.title in r.content, "%s title not in response" % k)

    def test_agenda_package(self):
        url = urlreverse("ietf.iesg.views.agenda_package")
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)

        for k, d in self.telechat_docs.iteritems():
            if d.type_id == "charter":
                self.assertTrue(d.group.name in r.content, "%s not in response" % k)
                self.assertTrue(d.group.acronym in r.content, "%s acronym not in response" % k)
            else:
                self.assertTrue(d.name in r.content, "%s not in response" % k)
                self.assertTrue(d.title in r.content, "%s title not in response" % k)

class RescheduleOnAgendaTestCase(django.test.TestCase):
    def test_reschedule(self):
        draft = make_test_data()

        # add to schedule
        e = TelechatDocEvent(type="scheduled_for_telechat")
        e.doc = draft
        e.by = Person.objects.get(name="Aread Irector")
        e.telechat_date = TelechatDate.objects.active()[0].date
        e.returning_item = True
        e.save()
        
        form_id = draft.pk
        telechat_date_before = e.telechat_date
        
        url = urlreverse('ietf.iesg.views.agenda_documents')
        
        self.client.login(remote_user="secretary")

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        
        self.assertEquals(len(q('form select[name=%s-telechat_date]' % form_id)), 1)
        self.assertEquals(len(q('form input[name=%s-clear_returning_item]' % form_id)), 1)

        # reschedule
        events_before = draft.docevent_set.count()
        d = TelechatDate.objects.active()[3].date

        r = self.client.post(url, { '%s-telechat_date' % form_id: d.isoformat(),
                                    '%s-clear_returning_item' % form_id: "1" })

        self.assertEquals(r.status_code, 200)

        # check that it moved below the right header in the DOM on the
        # agenda docs page
        d_header_pos = r.content.find("IESG telechat %s" % d.isoformat())
        draft_pos = r.content.find(draft.name)
        self.assertTrue(d_header_pos < draft_pos)

        self.assertTrue(draft.latest_event(TelechatDocEvent, "scheduled_for_telechat"))
        self.assertEquals(draft.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date, d)
        self.assertTrue(not draft.latest_event(TelechatDocEvent, "scheduled_for_telechat").returning_item)
        self.assertEquals(draft.docevent_set.count(), events_before + 1)


class WorkingGroupActionsTestCaseREDESIGN(django.test.TestCase):
    def setUp(self):
        super(self.__class__, self).setUp()

        curdir = os.path.dirname(os.path.abspath(__file__))
        self.evaldir = os.path.join(curdir, "tmp-testdir")
        os.mkdir(self.evaldir)
        
        src = os.path.join(curdir, "fixtures", "sieve-charter.txt")
        shutil.copy(src, self.evaldir)
        
        settings.IESG_WG_EVALUATION_DIR = self.evaldir

    def tearDown(self):
        super(self.__class__, self).tearDown()
        shutil.rmtree(self.evaldir)
        
    
    def test_working_group_actions(self):
        make_test_data()
        
        url = urlreverse('iesg_working_group_actions')
        login_testing_unauthorized(self, "secretary", url)

        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        for wga in WGAction.objects.all():
            self.assertTrue(wga.group_acronym.name in r.content)

        self.assertTrue('(sieve)' in r.content)

    def test_delete_wgaction(self):
        make_test_data()
        
        wga = WGAction.objects.all()[0]
        url = urlreverse('iesg_edit_working_group_action', kwargs=dict(wga_id=wga.pk))
        login_testing_unauthorized(self, "secretary", url)

        r = self.client.post(url, dict(delete="1"))
        self.assertEquals(r.status_code, 302)
        self.assertTrue(not WGAction.objects.filter(pk=wga.pk))

    def test_edit_wgaction(self):
        make_test_data()
        
        wga = WGAction.objects.all()[0]
        url = urlreverse('iesg_edit_working_group_action', kwargs=dict(wga_id=wga.pk))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form select[name=token_name]')), 1)
        self.assertEquals(len(q('form select[name=telechat_date]')), 1)

        # change
        dates = TelechatDate.objects.active()
        token_name = Person.objects.get(name="Ad No1").plain_name()
        old = wga.pk
        r = self.client.post(url, dict(status_date=dates[0].date.isoformat(),
                                       token_name=token_name,
                                       category="23",
                                       note="Testing.",
                                       telechat_date=dates[3].date.isoformat()))
        self.assertEquals(r.status_code, 302)

        wga = WGAction.objects.get(pk=old)
        self.assertEquals(wga.status_date, dates[0].date)
        self.assertEquals(wga.token_name, token_name)
        self.assertEquals(wga.category, 23)
        self.assertEquals(wga.note, "Testing.")
        self.assertEquals(wga.telechat_date, dates[3].date)
        
    def test_add_possible_wg(self):
        make_test_data()
        
        url = urlreverse('iesg_working_group_actions')
        login_testing_unauthorized(self, "secretary", url)
        
        r = self.client.post(url, dict(add="1",
                                       filename='sieve-charter.txt'))
        self.assertEquals(r.status_code, 302)

        # now we got back a URL we can use for adding, but first make
        # sure we got a proposed group with the acronym
        group = Group.objects.create(
            name="Sieve test test",
            acronym="sieve",
            state_id="proposed",
            type_id="wg",
            parent=None
            )
        
        add_url = r['Location']
        r = self.client.get(add_url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue('(sieve)' in r.content)
        self.assertEquals(len(q('form select[name=token_name]')), 1)
        self.assertEquals(q('form input[name=status_date]')[0].get("value"), "2010-05-07")
        self.assertEquals(len(q('form select[name=telechat_date]')), 1)

        wgas_before = WGAction.objects.all().count()
        dates = TelechatDate.objects.active()
        token_name = Person.objects.get(name="Ad No1").plain_name()
        r = self.client.post(add_url,
                             dict(status_date=dates[0].date.isoformat(),
                                  token_name=token_name,
                                  category="23",
                                  note="Testing.",
                                  telechat_date=dates[3].date.isoformat()))
        self.assertEquals(r.status_code, 302)
        self.assertEquals(wgas_before + 1, WGAction.objects.all().count())
        
    def test_delete_possible_wg(self):
        make_test_data()
        
        url = urlreverse('iesg_working_group_actions')
        login_testing_unauthorized(self, "secretary", url)
        
        r = self.client.post(url, dict(delete="1",
                                       filename='sieve-charter.txt'))
        self.assertEquals(r.status_code, 200)

        self.assertTrue('(sieve)' not in r.content)


class IesgUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)
    def doCanonicalize(self, url, content):
        if url.startswith("/feed/"):
            return canonicalize_feed(content)
        else:
            return content

class DeferUndeferTestCase(django.test.TestCase):
    def helper_test_defer(self,name):

        doc = Document.objects.get(name=name)
        url = urlreverse('doc_defer_ballot',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, "ad", url)

        # some additional setup
        dates = TelechatDate.objects.active().order_by("date")
        first_date = dates[0].date
        second_date = dates[1].date

        e = TelechatDocEvent(type="scheduled_for_telechat",
                             doc = doc,
                             by = Person.objects.get(name="Aread Irector"),
                             telechat_date = first_date,
                             returning_item = False, 
                            )
        e.save()

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form.defer')),1)

        # defer
        self.assertEquals(doc.telechat_date(), first_date)
        r = self.client.post(url,dict())
        self.assertEquals(r.status_code, 302)
        doc = Document.objects.get(name=name)
        self.assertEquals(doc.telechat_date(), second_date)
        self.assertTrue(doc.returning_item())
        defer_states = dict(draft=['draft-iesg','defer'],conflrev=['conflrev','defer'])
        if doc.type_id in defer_states:
           self.assertEquals(doc.get_state(defer_states[doc.type_id][0]).slug,defer_states[doc.type_id][1])


    def helper_test_undefer(self,name):

        doc = Document.objects.get(name=name)
        url = urlreverse('doc_undefer_ballot',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, "ad", url)

        # some additional setup
        dates = TelechatDate.objects.active().order_by("date")
        first_date = dates[0].date
        second_date = dates[1].date

        e = TelechatDocEvent(type="scheduled_for_telechat",
                             doc = doc,
                             by = Person.objects.get(name="Aread Irector"),
                             telechat_date = second_date,
                             returning_item = True, 
                            )
        e.save()
        defer_states = dict(draft=['draft-iesg','defer'],conflrev=['conflrev','defer'])
        if doc.type_id in defer_states:
            doc.set_state(State.objects.get(used=True, type=defer_states[doc.type_id][0],slug=defer_states[doc.type_id][1]))
            doc.save()

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form.undefer')),1)

        # undefer
        self.assertEquals(doc.telechat_date(), second_date)
        r = self.client.post(url,dict())
        self.assertEquals(r.status_code, 302)
        doc = Document.objects.get(name=name)
        self.assertEquals(doc.telechat_date(), first_date)
        self.assertTrue(doc.returning_item()) 
        undefer_states = dict(draft=['draft-iesg','iesg-eva'],conflrev=['conflrev','iesgeval'])
        if doc.type_id in undefer_states:
           self.assertEquals(doc.get_state(undefer_states[doc.type_id][0]).slug,undefer_states[doc.type_id][1])

    def test_defer_draft(self):
        self.helper_test_defer('draft-ietf-mars-test')

    def test_defer_conflict_review(self):
        self.helper_test_defer('conflict-review-imaginary-irtf-submission')

    def test_undefer_draft(self):
        self.helper_test_undefer('draft-ietf-mars-test')

    def test_undefer_conflict_review(self):
        self.helper_test_undefer('conflict-review-imaginary-irtf-submission')

    # when charters support being deferred, be sure to test them here

    def setUp(self):
        make_test_data()
