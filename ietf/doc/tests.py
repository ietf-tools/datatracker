# Copyright The IETF Trust 2012-2024, All Rights Reserved
# -*- coding: utf-8 -*-


import os
import datetime
import io
import lxml
import bibtexparser
import mock
import json
import copy
import random

from http.cookies import SimpleCookie
from pathlib import Path
from pyquery import PyQuery
from urllib.parse import urlparse, parse_qs
from collections import defaultdict
from zoneinfo import ZoneInfo

from django.urls import reverse as urlreverse
from django.conf import settings
from django.forms import Form
from django.utils.html import escape
from django.test import override_settings
from django.utils import timezone
from django.utils.text import slugify

from tastypie.test import ResourceTestCaseMixin

from weasyprint.urls import URLFetchingError

import debug                            # pyflakes:ignore

from ietf.doc.models import ( Document, DocRelationshipName, RelatedDocument, State,
    DocEvent, BallotPositionDocEvent, LastCallDocEvent, WriteupDocEvent, NewRevisionDocEvent, BallotType,
    EditedAuthorsDocEvent, StateType)
from ietf.doc.factories import ( DocumentFactory, DocEventFactory, CharterFactory,
    ConflictReviewFactory, WgDraftFactory, IndividualDraftFactory, WgRfcFactory, 
    IndividualRfcFactory, StateDocEventFactory, BallotPositionDocEventFactory, 
    BallotDocEventFactory, DocumentAuthorFactory, NewRevisionDocEventFactory,
    StatusChangeFactory, DocExtResourceFactory, RgDraftFactory, BcpFactory)
from ietf.doc.forms import NotifyForm
from ietf.doc.fields import SearchableDocumentsField
from ietf.doc.utils import (
    create_ballot_if_not_open,
    investigate_fragment,
    uppercase_std_abbreviated_name,
    DraftAliasGenerator,
    generate_idnits2_rfc_status,
    generate_idnits2_rfcs_obsoleted,
    get_doc_email_aliases,
)
from ietf.group.models import Group, Role
from ietf.group.factories import GroupFactory, RoleFactory
from ietf.ipr.factories import HolderIprDisclosureFactory
from ietf.meeting.models import Meeting, SessionPresentation, SchedulingEvent
from ietf.meeting.factories import ( MeetingFactory, SessionFactory, SessionPresentationFactory,
     ProceedingsMaterialFactory )

from ietf.name.models import SessionStatusName, BallotPositionName, DocTypeName, RoleName
from ietf.person.models import Person
from ietf.person.factories import PersonFactory, EmailFactory
from ietf.utils.mail import outbox, empty_outbox
from ietf.utils.test_utils import login_testing_unauthorized, unicontent
from ietf.utils.test_utils import TestCase
from ietf.utils.text import normalize_text
from ietf.utils.timezone import date_today, datetime_today, DEADLINE_TZINFO, RPC_TZINFO
from ietf.doc.utils_search import AD_WORKLOAD


class SearchTests(TestCase):
    def test_search(self):

        draft = WgDraftFactory(name='draft-ietf-mars-test',group=GroupFactory(acronym='mars',parent=Group.objects.get(acronym='farfut')),authors=[PersonFactory()],ad=PersonFactory())
        rfc = WgRfcFactory()
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="pub-req"))
        old_draft = IndividualDraftFactory(name='draft-foo-mars-test',authors=[PersonFactory()],title="Optimizing Martian Network Topologies")
        old_draft.set_state(State.objects.get(used=True, type="draft", slug="expired"))

        base_url = urlreverse('ietf.doc.views_search.search')

        # only show form, no search yet
        r = self.client.get(base_url)
        self.assertEqual(r.status_code, 200)

        # no match
        r = self.client.get(base_url + "?activedrafts=on&name=thisisnotadocumentname")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "No documents match")

        r = self.client.get(base_url + "?rfcs=on&name=xyzzy")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "No documents match")

        r = self.client.get(base_url + "?olddrafts=on&name=bar")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "No documents match")

        r = self.client.get(base_url + "?olddrafts=on&name=foo")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "draft-foo-mars-test")

        r = self.client.get(base_url + "?olddrafts=on&name=FoO")  # mixed case
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "draft-foo-mars-test")

        # find by RFC
        r = self.client.get(base_url + "?rfcs=on&name=%s" % rfc.name)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, rfc.title)

        # find by active/inactive

        draft.set_state(State.objects.get(type="draft", slug="active"))
        r = self.client.get(base_url + "?activedrafts=on&name=%s" % draft.name)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.title)

        draft.set_state(State.objects.get(type="draft", slug="expired"))
        r = self.client.get(base_url + "?olddrafts=on&name=%s" % draft.name)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.title)
        
        draft.set_state(State.objects.get(type="draft", slug="active"))

        # find by title
        r = self.client.get(base_url + "?activedrafts=on&name=%s" % draft.title.split()[0])
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.title)

        # find by author
        r = self.client.get(base_url + "?activedrafts=on&by=author&author=%s" % draft.documentauthor_set.first().person.name_parts()[1])
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.title)

        # find by group
        r = self.client.get(base_url + "?activedrafts=on&by=group&group=%s" % draft.group.acronym)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.title)

        r = self.client.get(base_url + "?activedrafts=on&by=group&group=%s" % draft.group.acronym.swapcase())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.title)

        # find by area
        r = self.client.get(base_url + "?activedrafts=on&by=area&area=%s" % draft.group.parent_id)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.title)

        # find by area
        r = self.client.get(base_url + "?activedrafts=on&by=area&area=%s" % draft.group.parent_id)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.title)

        # find by AD
        r = self.client.get(base_url + "?activedrafts=on&by=ad&ad=%s" % draft.ad_id)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.title)

        # find by IESG state
        r = self.client.get(base_url + "?activedrafts=on&by=state&state=%s&substate=" % draft.get_state("draft-iesg").pk)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.title)

    def test_search_became_rfc(self):
        draft = WgDraftFactory()
        rfc = WgRfcFactory()
        draft.set_state(State.objects.get(type="draft", slug="rfc"))
        draft.relateddocument_set.create(relationship_id="became_rfc", target=rfc)
        base_url = urlreverse('ietf.doc.views_search.search')

        # find by RFC
        r = self.client.get(base_url + f"?rfcs=on&name={rfc.name}")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, rfc.title)

        # find by draft
        r = self.client.get(base_url + f"?activedrafts=on&rfcs=on&name={draft.name}")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, rfc.title)

    def test_search_for_name(self):
        draft = WgDraftFactory(name='draft-ietf-mars-test',group=GroupFactory(acronym='mars',parent=Group.objects.get(acronym='farfut')),authors=[PersonFactory()],ad=PersonFactory())
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="pub-req"))
        CharterFactory(group=draft.group,name='charter-ietf-mars')
        DocumentFactory(type_id='conflrev',name='conflict-review-imaginary-irtf-submission')
        DocumentFactory(type_id='statchg',name='status-change-imaginary-mid-review')
        DocumentFactory(type_id='agenda',name='agenda-72-mars')
        DocumentFactory(type_id='minutes',name='minutes-72-mars')
        DocumentFactory(type_id='slides',name='slides-72-mars')

        draft.save_with_history([DocEvent.objects.create(doc=draft, rev=draft.rev, type="changed_document", by=Person.objects.get(user__username="secretary"), desc="Test")])

        prev_rev = draft.rev
        draft.rev = "%02d" % (int(prev_rev) + 1)
        draft.save_with_history([DocEvent.objects.create(doc=draft, rev=draft.rev, type="changed_document", by=Person.objects.get(user__username="secretary"), desc="Test")])

        # exact match
        r = self.client.get(urlreverse('ietf.doc.views_search.search_for_name', kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse(r["Location"]).path, urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))

        # mixed-up case exact match
        r = self.client.get(urlreverse('ietf.doc.views_search.search_for_name', kwargs=dict(name=draft.name.swapcase())))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse(r["Location"]).path, urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))

        # prefix match
        r = self.client.get(urlreverse('ietf.doc.views_search.search_for_name', kwargs=dict(name="-".join(draft.name.split("-")[:-1]))))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse(r["Location"]).path, urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))

        # mixed-up case prefix match
        r = self.client.get(
            urlreverse(
                'ietf.doc.views_search.search_for_name',
                kwargs=dict(name="-".join(draft.name.swapcase().split("-")[:-1])),
            ))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse(r["Location"]).path, urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))

        # non-prefix match
        r = self.client.get(urlreverse('ietf.doc.views_search.search_for_name', kwargs=dict(name="-".join(draft.name.split("-")[1:]))))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse(r["Location"]).path, urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))

        # mixed-up case non-prefix match
        r = self.client.get(
            urlreverse(
                'ietf.doc.views_search.search_for_name',
                kwargs=dict(name="-".join(draft.name.swapcase().split("-")[1:])),
            ))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse(r["Location"]).path, urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))

        # other doctypes than drafts
        doc = Document.objects.get(name='charter-ietf-mars')
        r = self.client.get(urlreverse('ietf.doc.views_search.search_for_name', kwargs=dict(name='charter-ietf-ma')))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse(r["Location"]).path, urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc.name)))

        doc = Document.objects.filter(name__startswith='conflict-review-').first()
        r = self.client.get(urlreverse('ietf.doc.views_search.search_for_name', kwargs=dict(name="-".join(doc.name.split("-")[:-1]))))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse(r["Location"]).path, urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc.name)))

        doc = Document.objects.filter(name__startswith='status-change-').first()
        r = self.client.get(urlreverse('ietf.doc.views_search.search_for_name', kwargs=dict(name="-".join(doc.name.split("-")[:-1]))))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse(r["Location"]).path, urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc.name)))

        doc = Document.objects.filter(name__startswith='agenda-').first()
        r = self.client.get(urlreverse('ietf.doc.views_search.search_for_name', kwargs=dict(name="-".join(doc.name.split("-")[:-1]))))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse(r["Location"]).path, urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc.name)))

        doc = Document.objects.filter(name__startswith='minutes-').first()
        r = self.client.get(urlreverse('ietf.doc.views_search.search_for_name', kwargs=dict(name="-".join(doc.name.split("-")[:-1]))))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse(r["Location"]).path, urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc.name)))

        doc = Document.objects.filter(name__startswith='slides-').first()
        r = self.client.get(urlreverse('ietf.doc.views_search.search_for_name', kwargs=dict(name="-".join(doc.name.split("-")[:-1]))))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse(r["Location"]).path, urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc.name)))

        # match with revision
        r = self.client.get(urlreverse('ietf.doc.views_search.search_for_name', kwargs=dict(name=draft.name + "-" + prev_rev)))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse(r["Location"]).path, urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name, rev=prev_rev)))

        # match with non-existing revision
        r = self.client.get(urlreverse('ietf.doc.views_search.search_for_name', kwargs=dict(name=draft.name + "-09")))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse(r["Location"]).path, urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))

        # match with revision and extension
        r = self.client.get(urlreverse('ietf.doc.views_search.search_for_name', kwargs=dict(name=draft.name + "-" + prev_rev + ".txt")))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse(r["Location"]).path, urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name, rev=prev_rev)))
        
        # no match
        r = self.client.get(urlreverse('ietf.doc.views_search.search_for_name', kwargs=dict(name="draft-ietf-doesnotexist-42")))
        self.assertEqual(r.status_code, 302)

        parsed = urlparse(r["Location"])
        self.assertEqual(parsed.path, urlreverse('ietf.doc.views_search.search'))
        self.assertEqual(parse_qs(parsed.query)["name"][0], "draft-ietf-doesnotexist-42")
    
    def test_search_rfc(self):
        rfc = WgRfcFactory(name="rfc0000")
        
        # search for existing RFC should redirect directly to the RFC page
        r = self.client.get(urlreverse('ietf.doc.views_search.search_for_name', kwargs=dict(name=rfc.name)))
        self.assertRedirects(r, f'/doc/{rfc.name}/', status_code=302, target_status_code=200)

        # search for existing RFC with revision number should redirect to the RFC page
        r = self.client.get(urlreverse('ietf.doc.views_search.search_for_name', kwargs=dict(name=rfc.name + "-99")), follow=True)
        self.assertRedirects(r, f'/doc/{rfc.name}/', status_code=302, target_status_code=200)

    def test_frontpage(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Document Search")

    def test_ad_workload(self):
        Role.objects.filter(name_id="ad").delete()
        ad = RoleFactory(
            name_id="ad",
            group__type_id="area",
            group__state_id="active",
            person__name="Example Areadirector",
        ).person
        expected = defaultdict(lambda: 0)
        for doc_type_slug in AD_WORKLOAD:
            for state in AD_WORKLOAD[doc_type_slug]:
                target_num = random.randint(0, 2)
                for _ in range(target_num):
                    if (
                        doc_type_slug == "draft"
                        or doc_type_slug == "rfc"
                        and state == "rfcqueue"
                    ):
                        IndividualDraftFactory(
                            ad=ad,
                            states=[
                                ("draft-iesg", state),
                                ("draft", "rfc" if state == "pub" else "active"),
                            ],
                        )
                    elif doc_type_slug == "rfc":
                        WgRfcFactory.create(
                            states=[("draft", "rfc"), ("draft-iesg", "pub")]
                        )

                    elif doc_type_slug == "charter":
                        CharterFactory(ad=ad, states=[(doc_type_slug, state)])
                    elif doc_type_slug == "conflrev":
                        ConflictReviewFactory(
                            ad=ad,
                            states=State.objects.filter(
                                type_id=doc_type_slug, slug=state
                            ),
                        )
                    elif doc_type_slug == "statchg":
                        StatusChangeFactory(
                            ad=ad,
                            states=State.objects.filter(
                                type_id=doc_type_slug, slug=state
                            ),
                        )
        self.client.login(username="ad", password="ad+password")
        url = urlreverse("ietf.doc.views_search.ad_workload")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        for group_type, ad, group in expected:
            self.assertEqual(
                int(q(f"#{group_type}-{ad}-{group}").text()),
                expected[(group_type, ad, group)],
            )

    def test_docs_for_ad(self):
        ad = RoleFactory(name_id='ad',group__type_id='area',group__state_id='active').person
        draft = IndividualDraftFactory(ad=ad)
        draft.action_holders.set([PersonFactory()])
        draft.set_state(State.objects.get(type='draft-iesg', slug='lc'))
        rfc = IndividualRfcFactory(ad=ad)
        conflrev = DocumentFactory(type_id='conflrev',ad=ad)
        conflrev.set_state(State.objects.get(type='conflrev', slug='iesgeval'))
        statchg = DocumentFactory(type_id='statchg',ad=ad)
        statchg.set_state(State.objects.get(type='statchg', slug='iesgeval'))
        charter = CharterFactory(name='charter-ietf-ames',ad=ad)
        charter.set_state(State.objects.get(type='charter', slug='iesgrev'))

        ballot_type = BallotType.objects.get(doc_type_id='draft',slug='approve')
        ballot = BallotDocEventFactory(ballot_type=ballot_type, doc__states=[('draft-iesg','iesg-eva')])
        discuss_pos = BallotPositionName.objects.get(slug='discuss')
        discuss_other = BallotPositionDocEventFactory(ballot=ballot, doc=ballot.doc, balloter=ad, pos=discuss_pos)

        blockedcharter = CharterFactory(name='charter-ietf-mars',ad=ad)
        blockedcharter.set_state(State.objects.get(type='charter',slug='extrev'))
        charter_ballot_type = BallotType.objects.get(doc_type_id='charter',slug='approve')
        charterballot = BallotDocEventFactory(ballot_type=charter_ballot_type, doc__states=[('charter','extrev')])
        block_pos = BallotPositionName.objects.get(slug='block')
        block_other = BallotPositionDocEventFactory(ballot=charterballot, doc=ballot.doc, balloter=ad, pos=block_pos)

        r = self.client.get(urlreverse('ietf.doc.views_search.docs_for_ad', kwargs=dict(name=ad.full_name_as_key())))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.name)
        self.assertContains(r, escape(draft.action_holders.first().name))
        self.assertContains(r, rfc.name)
        self.assertContains(r, conflrev.name)
        self.assertContains(r, statchg.name)
        self.assertContains(r, charter.name)

        self.assertContains(r, discuss_other.doc.name)
        self.assertContains(r, block_other.doc.name)

    def test_auth48_doc_for_ad(self):
        """Docs in AUTH48 state should have a decoration"""
        ad = RoleFactory(name_id='ad', group__type_id='area', group__state_id='active').person
        draft = IndividualDraftFactory(ad=ad,
                                       states=[('draft', 'active'),
                                               ('draft-iesg', 'rfcqueue'),
                                               ('draft-rfceditor', 'auth48')])
        r = self.client.get(urlreverse('ietf.doc.views_search.docs_for_ad',
                                       kwargs=dict(name=ad.full_name_as_key())))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.name)
        self.assertContains(r, 'title="AUTH48"')  # title attribute of AUTH48 badge in auth48_alert_badge filter

    def test_drafts_in_last_call(self):
        draft = IndividualDraftFactory(pages=1)
        draft.action_holders.set([PersonFactory()])
        draft.set_state(State.objects.get(type="draft-iesg", slug="lc"))
        r = self.client.get(urlreverse('ietf.doc.views_search.drafts_in_last_call'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.title)
        self.assertContains(r, escape(draft.action_holders.first().name))

    def test_in_iesg_process(self):
        doc_in_process = IndividualDraftFactory()
        doc_in_process.action_holders.set([PersonFactory()])
        doc_in_process.set_state(State.objects.get(type='draft-iesg', slug='lc'))
        doc_not_in_process = IndividualDraftFactory()
        r = self.client.get(urlreverse('ietf.doc.views_search.drafts_in_iesg_process'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, doc_in_process.title)
        self.assertContains(r, escape(doc_in_process.action_holders.first().name))
        self.assertNotContains(r, doc_not_in_process.title)
        
    def test_indexes(self):
        draft = IndividualDraftFactory()
        rfc = WgRfcFactory()

        r = self.client.get(urlreverse('ietf.doc.views_search.index_all_drafts'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.name)
        self.assertContains(r, rfc.name.upper())

        r = self.client.get(urlreverse('ietf.doc.views_search.index_active_drafts'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.title)

    def test_ajax_search_docs(self):
        draft = IndividualDraftFactory(name="draft-ietf-rfc1234bis")
        rfc = IndividualRfcFactory(rfc_number=1234)
        bcp = IndividualRfcFactory(name="bcp12345", type_id="bcp")

        url = urlreverse('ietf.doc.views_search.ajax_select2_search_docs', kwargs={
            "model_name": "document",
            "doc_type": "draft",
        })
        r = self.client.get(url, dict(q=draft.name))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data[0]["id"], draft.pk)

        url = urlreverse('ietf.doc.views_search.ajax_select2_search_docs', kwargs={
            "model_name": "document",
            "doc_type": "rfc",
        })
        r = self.client.get(url, dict(q=rfc.name))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data[0]["id"], rfc.pk)

        url = urlreverse('ietf.doc.views_search.ajax_select2_search_docs', kwargs={
            "model_name": "document",
            "doc_type": "all",
        })
        r = self.client.get(url, dict(q="1234"))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data), 3)
        pks = set([data[i]["id"] for i in range(3)])
        self.assertEqual(pks, set([bcp.pk, rfc.pk, draft.pk]))



    def test_recent_drafts(self):
        # Three drafts to show with various warnings
        drafts = WgDraftFactory.create_batch(3,states=[('draft','active'),('draft-iesg','ad-eval')])
        for index, draft in enumerate(drafts):
            StateDocEventFactory(doc=draft, state=('draft-iesg','ad-eval'), time=timezone.now()-datetime.timedelta(days=[1,15,29][index]))
            draft.action_holders.set([PersonFactory()])

        # And one draft that should not show (with the default of 7 days to view)
        old = WgDraftFactory()
        old.docevent_set.filter(newrevisiondocevent__isnull=False).update(time=timezone.now()-datetime.timedelta(days=8))
        StateDocEventFactory(doc=old, time=timezone.now()-datetime.timedelta(days=8))

        url = urlreverse('ietf.doc.views_search.recent_drafts')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('td.doc')),3)
        self.assertTrue(q('td.status span.text-bg-warning[title*="%s"]' % "for 15 days"))
        self.assertTrue(q('td.status span.text-bg-danger[title*="%s"]' % "for 29 days"))
        for ah in [draft.action_holders.first() for draft in drafts]:
            self.assertContains(r, escape(ah.name))

class DocDraftTestCase(TestCase):
    draft_text = """



Martian Special Interest Group (mars)                             P. Man
Internet-Draft                                            March 21, 2015
Intended status: Informational
Expires: September 22, 2015


                 Optimizing Martian Network Topologies
                      draft-ietf-mars-test-02.txt

Abstract

   Techniques for achieving near-optimal Martian networks.

Status of This Memo

   This Internet-Draft is submitted in full conformance with the
   provisions of BCP 78 and BCP 79.

   Internet-Drafts are working documents of the Internet Engineering
   Task Force (IETF).  Note that other groups may also distribute
   working documents as Internet-Drafts.  The list of current Internet-
   Drafts is at http://datatracker.ietf.org/drafts/current/.

   Internet-Drafts are draft documents valid for a maximum of six months
   and may be updated, replaced, or obsoleted by other documents at any
   time.  It is inappropriate to use Internet-Drafts as reference
   material or to cite them other than as "work in progress."

   This Internet-Draft will expire on September 22, 2015.

Copyright Notice

   Copyright (c) 2015 IETF Trust and the persons identified as the
   document authors.  All rights reserved.

   This document is subject to BCP 78 and the IETF Trust's Legal
   Provisions Relating to IETF Documents
   (http://trustee.ietf.org/license-info) in effect on the date of
   publication of this document.  Please review these documents
   carefully, as they describe your rights and restrictions with respect
   to this document.  Code Components extracted from this document must
   include Simplified BSD License text as described in Section 4.e of
   the Trust Legal Provisions and are provided without warranty as
   described in the Simplified BSD License.

   This document may contain material from IETF Documents or IETF
   Contributions published or made publicly available before November
   10, 2008.  The person(s) controlling the copyright in some of this



Man                    Expires September 22, 2015               [Page 1]

Internet-Draft    Optimizing Martian Network Topologies       March 2015


   material may not have granted the IETF Trust the right to allow
   modifications of such material outside the IETF Standards Process.
   Without obtaining an adequate license from the person(s) controlling
   the copyright in such materials, this document may not be modified
   outside the IETF Standards Process, and derivative works of it may
   not be created outside the IETF Standards Process, except to format
   it for publication as an RFC or to translate it into languages other
   than English.

Table of Contents

   1.  Introduction  . . . . . . . . . . . . . . . . . . . . . . . .   2
   2.  Security Considerations . . . . . . . . . . . . . . . . . . .   2
   3.  IANA Considerations . . . . . . . . . . . . . . . . . . . . .   2
   4.  Acknowledgements  . . . . . . . . . . . . . . . . . . . . . .   3
   5.  Normative References  . . . . . . . . . . . . . . . . . . . .   3
   Author's Address  . . . . . . . . . . . . . . . . . . . . . . . .   3

1.  Introduction

   This document describes how to make the Martian networks work.  The
   methods used in Earth do not directly translate to the efficient
   networks on Mars, as the topographical differences caused by planets.
   For example the avian carriers, cannot be used in the Mars, thus
   RFC1149 ([RFC1149]) cannot be used in Mars.

   Some optimizations can be done because Mars is smaller than Earth,
   thus the round trip times are smaller.  Also as Mars has two moons
   instead of only one as we have in Earth, we can use both Deimos and
   Phobos when using reflecting radio links off the moon.

   The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT",
   "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this
   document are to be interpreted as described in [RFC2119].

2.  Security Considerations

   As Martians are known to listen all traffic in Mars, all traffic in
   the Mars MUST be encrypted.

3.  IANA Considerations

   There is no new IANA considerations in this document.








Man                    Expires September 22, 2015               [Page 2]

Internet-Draft    Optimizing Martian Network Topologies       March 2015


4.  Acknowledgements

   This document is created in the IETF-92 CodeSprint in Dallas, TX.

5.  Normative References

   [RFC1149]  Waitzman, D., "Standard for the transmission of IP
              datagrams on avian carriers", RFC 1149, April 1990.

   [RFC2119]  Bradner, S., "Key words for use in RFCs to Indicate
              Requirement Levels", BCP 14, RFC 2119, March 1997.

Author's Address

   Plain Man
   Deimos street
   Mars City  MARS-000000
   Mars

   Email: aliens@example.mars































Man                    Expires September 22, 2015               [Page 3]
"""

    def setUp(self):
        super().setUp()
        for dir in [settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR, settings.INTERNET_DRAFT_PATH]:
            with (Path(dir) / 'draft-ietf-mars-test-01.txt').open('w') as f:
                f.write(self.draft_text)

    def test_document_draft(self):
        draft = WgDraftFactory(name='draft-ietf-mars-test',rev='01', create_revisions=range(0,2))

        HolderIprDisclosureFactory(docs=[draft])
        
        # Docs for testing relationships. Does not test 'possibly-replaces'. The 'replaced_by' direction
        # is tested separately below.
        replaced = IndividualDraftFactory()
        draft.relateddocument_set.create(relationship_id='replaces',source=draft,target=replaced)
        obsoleted = IndividualDraftFactory()
        draft.relateddocument_set.create(relationship_id='obs',source=draft,target=obsoleted)
        obsoleted_by = IndividualDraftFactory()
        obsoleted_by.relateddocument_set.create(relationship_id='obs',source=obsoleted_by,target=draft)
        updated = IndividualDraftFactory()
        draft.relateddocument_set.create(relationship_id='updates',source=draft,target=updated)
        updated_by = IndividualDraftFactory()
        updated_by.relateddocument_set.create(relationship_id='updates',source=obsoleted_by,target=draft)

        DocExtResourceFactory(doc=draft)

        # these tests aren't testing all attributes yet, feel free to
        # expand them

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Active Internet-Draft")
        if settings.USER_PREFERENCE_DEFAULTS['full_draft'] == 'off':
            self.assertContains(r, "Show full document")
            self.assertNotContains(r, "Deimos street")
        self.assertContains(r, replaced.name)
        self.assertContains(r, replaced.title)

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)) + "?include_text=0")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Active Internet-Draft")
        self.assertContains(r, "Show full document")
        self.assertNotContains(r, "Deimos street")
        self.assertContains(r, replaced.name)
        self.assertContains(r, replaced.title)

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)) + "?include_text=foo")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Active Internet-Draft")
        self.assertNotContains(r, "Show full document")
        self.assertContains(r, "Deimos street")
        self.assertContains(r, replaced.name)
        self.assertContains(r, replaced.title)

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)) + "?include_text=1")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Active Internet-Draft")
        self.assertNotContains(r, "Show full document")
        self.assertContains(r, "Deimos street")
        self.assertContains(r, replaced.name)
        self.assertContains(r, replaced.title)

        self.client.cookies = SimpleCookie({str('full_draft'): str('on')})
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Active Internet-Draft")
        self.assertNotContains(r, "Show full document")
        self.assertContains(r, "Deimos street")
        self.assertContains(r, replaced.name)
        self.assertContains(r, replaced.title)

        self.client.cookies = SimpleCookie({str('full_draft'): str('off')})
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Active Internet-Draft")
        self.assertContains(r, "Show full document")
        self.assertNotContains(r, "Deimos street")
        self.assertContains(r, replaced.name)
        self.assertContains(r, replaced.title)

        self.client.cookies = SimpleCookie({str('full_draft'): str('foo')})
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Active Internet-Draft")
        if settings.USER_PREFERENCE_DEFAULTS['full_draft'] == 'off':
            self.assertContains(r, "Show full document")
            self.assertNotContains(r, "Deimos street")
        self.assertContains(r, replaced.name)
        self.assertContains(r, replaced.title)

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_html", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Select version")
        self.assertContains(r, "Deimos street")
        q = PyQuery(r.content)
        self.assertEqual(q('title').text(), 'draft-ietf-mars-test-01')
        self.assertEqual(len(q('.rfcmarkup pre')), 3)
        self.assertEqual(len(q('.rfcmarkup span.h1, .rfcmarkup h1')), 2)
        self.assertEqual(len(q('.rfcmarkup a[href]')), 27)

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_html", kwargs=dict(name=draft.name, rev=draft.rev)))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(q('title').text(), 'draft-ietf-mars-test-01')

        # check that revision list has expected versions
        self.assertEqual(len(q('#sidebar .revision-list .page-item.active a.page-link[href$="draft-ietf-mars-test-01"]')), 1)

        # check that diff dropdowns have expected versions
        self.assertEqual(len(q('#sidebar option[value="draft-ietf-mars-test-00"][selected="selected"]')), 1)

        rfc = WgRfcFactory()
        rfc.save_with_history([DocEventFactory(doc=rfc)])
        (Path(settings.RFC_PATH) / rfc.get_base_name()).touch()
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_html", kwargs=dict(name=rfc.name)))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(q('title').text(), f'RFC {rfc.rfc_number} - {rfc.title}')

        # synonyms for the rfc should be redirected to its canonical view
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_html", kwargs=dict(name=rfc.rfc_number)))
        self.assertRedirects(r, urlreverse("ietf.doc.views_doc.document_html", kwargs=dict(name=rfc.name)))
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_html", kwargs=dict(name=f'RFC {rfc.rfc_number}')))
        self.assertRedirects(r, urlreverse("ietf.doc.views_doc.document_html", kwargs=dict(name=rfc.name)))

        # expired draft
        draft.set_state(State.objects.get(type="draft", slug="expired"))

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Expired Internet-Draft")

        # replaced draft
        draft.set_state(State.objects.get(type="draft", slug="repl"))

        replacement = WgDraftFactory(
            name="draft-ietf-replacement",
            time=timezone.now(),
            title="Replacement Draft",
            stream_id=draft.stream_id, group_id=draft.group_id, abstract=draft.abstract,stream=draft.stream, rev=draft.rev,
            pages=draft.pages, intended_std_level_id=draft.intended_std_level_id,
            shepherd_id=draft.shepherd_id, ad_id=draft.ad_id, expires=draft.expires,
            notify=draft.notify)
        rel = RelatedDocument.objects.create(source=replacement,
                                             target=draft,
                                             relationship_id="replaces")

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Replaced Internet-Draft")
        self.assertContains(r, replacement.name)
        self.assertContains(r, replacement.title)
        rel.delete()

        # draft published as RFC
        draft.set_state(State.objects.get(type="draft", slug="rfc"))
        draft.std_level_id = "ps"

        rfc = WgRfcFactory(group=draft.group, name="rfc123456")
        rfc.save_with_history([DocEvent.objects.create(doc=rfc, rev=None, type="published_rfc", by=Person.objects.get(name="(System)"))])

        draft.relateddocument_set.create(relationship_id="became_rfc", target=rfc)

        obsoleted = IndividualRfcFactory()
        rfc.relateddocument_set.create(relationship_id='obs',target=obsoleted)
        obsoleted_by = IndividualRfcFactory()
        obsoleted_by.relateddocument_set.create(relationship_id='obs',target=rfc)
        updated = IndividualRfcFactory()
        rfc.relateddocument_set.create(relationship_id='updates',target=updated)
        updated_by = IndividualRfcFactory()
        updated_by.relateddocument_set.create(relationship_id='updates',target=rfc)

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name, rev=draft.rev)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "This is an older version of an Internet-Draft that was ultimately published as")

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 302)

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=rfc.name)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "RFC 123456")
        self.assertContains(r, draft.name)
        # obs/updates included with RFC
        self.assertContains(r, obsoleted.name)
        self.assertContains(r, obsoleted.title)
        self.assertContains(r, obsoleted_by.name)
        self.assertContains(r, obsoleted_by.title)
        self.assertContains(r, updated.name)
        self.assertContains(r, updated.title)
        self.assertContains(r, updated_by.name)
        self.assertContains(r, updated_by.title)

        # naked RFC - also weird that we test a PS from the ISE
        rfc = IndividualDraftFactory(
            name="rfc1234567",
            title="RFC without a Draft",
            stream_id="ise",
            std_level_id="ps")
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=rfc.name)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "RFC 1234567")

        # unknown draft
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name="draft-xyz123")))
        self.assertEqual(r.status_code, 404)

    def assert_correct_wg_group_link(self, r, group):
        """Assert correct format for WG-like group types"""
        self.assertContains(
            r,
            '(<a href="%(about_url)s">%(group_acro)s %(group_type)s</a>)' % {
                "group_acro": group.acronym,
                "group_type": group.type,
                "about_url": group.about_url(),
            },
            msg_prefix='WG-like group %s (%s) should include group type in link' % (group.acronym, group.type),
        )

    def test_draft_status_changes(self):
        draft = WgRfcFactory()
        status_change_doc = StatusChangeFactory(
            group=draft.group,
            changes_status_of=[('tops', draft)],
        )
        status_change_url = urlreverse(
            'ietf.doc.views_doc.document_main',
            kwargs={'name': status_change_doc.name},
        )
        proposed_status_change_doc = StatusChangeFactory(
            group=draft.group,
            changes_status_of=[('tobcp', draft)],
            states=[State.objects.get(slug='needshep', type='statchg')],
        )
        proposed_status_change_url = urlreverse(
            'ietf.doc.views_doc.document_main',
            kwargs={'name': proposed_status_change_doc.name},
        )

        r = self.client.get(
            urlreverse(
                'ietf.doc.views_doc.document_main',
                kwargs={'name': draft.name},
            )
        )
        self.assertEqual(r.status_code, 200)
        response_content = r.content.decode()
        self.assertInHTML(
            'Status changed by <a href="{url}" title="{title}">{name}</a>'.format(
                name=status_change_doc.name,
                title=status_change_doc.title,
                url=status_change_url,
            ),
            response_content,
        )
        self.assertInHTML(
            'Proposed status changed by <a href="{url}" title="{title}">{name}</a>'.format(
                name=proposed_status_change_doc.name,
                title=proposed_status_change_doc.title,
                url=proposed_status_change_url,
            ),
            response_content,
        )

    def assert_correct_non_wg_group_link(self, r, group):
        """Assert correct format for non-WG-like group types"""
        self.assertContains(
            r,
            '(<a href="%(about_url)s">%(group_acro)s</a>)' % {
                "group_acro": group.acronym,
                "about_url": group.about_url(),
            },
            msg_prefix='Non-WG-like group %s (%s) should not include group type in link' % (group.acronym, group.type),
        )

    def login(self, username):
        self.client.login(username=username, password=username + '+password')

    def test_edit_authors_permissions(self):
        """Only the secretariat may edit authors"""
        draft = WgDraftFactory(authors=PersonFactory.create_batch(3))
        RoleFactory(group=draft.group, name_id='chair')
        RoleFactory(group=draft.group, name_id='ad', person=Person.objects.get(user__username='ad'))
        url = urlreverse('ietf.doc.views_doc.edit_authors', kwargs=dict(name=draft.name))

        # Relevant users not authorized to edit authors
        unauthorized_usernames = [
            'plain',
            *[author.user.username for author in draft.authors()],
            draft.group.get_chair().person.user.username,
            'ad'
        ]

        # First, check that only the secretary can even see the edit page.
        # Each call checks that currently-logged in user is refused, then logs in as the named user.
        for username in unauthorized_usernames:
            login_testing_unauthorized(self, username, url)
        login_testing_unauthorized(self, 'secretary', url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.client.logout()

        # Try to add an author via POST - still only the secretary should be able to do this.
        orig_authors = draft.authors()
        post_data = self.make_edit_authors_post_data(
            basis='permission test',
            authors=draft.documentauthor_set.all(),
        )
        new_auth_person = PersonFactory()
        self.add_author_to_edit_authors_post_data(
            post_data,
            dict(
                person=str(new_auth_person.pk),
                email=str(new_auth_person.email()),
                affiliation='affil',
                country='USA',
            ),
        )
        for username in unauthorized_usernames:
            login_testing_unauthorized(self, username, url, method='post', request_kwargs=dict(data=post_data))
            draft = Document.objects.get(pk=draft.pk)
            self.assertEqual(draft.authors(), orig_authors)  # ensure draft author list was not modified
        login_testing_unauthorized(self, 'secretary', url, method='post', request_kwargs=dict(data=post_data))
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 302)
        draft = Document.objects.get(pk=draft.pk)
        self.assertEqual(draft.authors(), orig_authors + [new_auth_person])

    def make_edit_authors_post_data(self, basis, authors):
        """Helper to generate edit_authors POST data for a set of authors"""
        def _add_prefix(s):
            # The prefix here needs to match the formset prefix in the edit_authors() view
            return 'author-{}'.format(s)

        data = {
            'basis': basis,
            # management form
            _add_prefix('TOTAL_FORMS'): '1',  # just the empty form so far
            _add_prefix('INITIAL_FORMS'): str(len(authors)),
            _add_prefix('MIN_NUM_FORMS'): '0',
            _add_prefix('MAX_NUM_FORMS'): '1000',
            # empty form
            _add_prefix('__prefix__-person'): '',
            _add_prefix('__prefix__-email'): '',
            _add_prefix('__prefix__-affiliation'): '',
            _add_prefix('__prefix__-country'): '',
            _add_prefix('__prefix__-ORDER'): '',
        }
        
        for index, auth in enumerate(authors):
            self.add_author_to_edit_authors_post_data(
                data,
                dict(
                    person=str(auth.person.pk),
                    email=auth.email,
                    affiliation=auth.affiliation,
                    country=auth.country
                )
            )
        
        return data
    
    def add_author_to_edit_authors_post_data(self, post_data, new_author, insert_order=-1, prefix='author'):
        """Helper to insert an author in the POST data for the edit_authors view
        
        The insert_order parameter is 0-indexed (i.e., it's the Django formset ORDER field, not the
        DocumentAuthor order property, which is 1-indexed)
        """
        def _add_prefix(s):
            return '{}-{}'.format(prefix, s)

        total_forms = int(post_data[_add_prefix('TOTAL_FORMS')]) - 1  # subtract 1 for empty form 
        if insert_order < 0:
            insert_order = total_forms
        else:
            # Make a map from order to the data key that has that order value
            order_key = dict()
            for order in range(insert_order, total_forms):
                key = _add_prefix(str(order) + '-ORDER')
                order_key[int(post_data[key])] = key
            # now increment all orders at or above where new element will be inserted
            for order in range(insert_order, total_forms):
                post_data[order_key[order]] = str(order + 1)
        
        form_index = total_forms  # regardless of insert order, new data has next unused form index
        total_forms += 1  # new form

        post_data[_add_prefix('TOTAL_FORMS')] = total_forms + 1  # add 1 for empty form
        for prop in ['person', 'email', 'affiliation', 'country']:
            post_data[_add_prefix(str(form_index) + '-' + prop)] = str(new_author[prop])
        post_data[_add_prefix(str(form_index) + '-ORDER')] = str(insert_order)

    def test_edit_authors_missing_basis(self):
        draft = WgDraftFactory()
        DocumentAuthorFactory.create_batch(3, document=draft)
        url = urlreverse('ietf.doc.views_doc.edit_authors', kwargs=dict(name=draft.name))

        self.login('secretary')
        post_data = self.make_edit_authors_post_data(
            authors = draft.documentauthor_set.all(),
            basis='delete me'
        )
        post_data.pop('basis')

        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'This field is required.')

    def test_edit_authors_no_change(self):
        draft = WgDraftFactory()
        DocumentAuthorFactory.create_batch(3, document=draft)
        url = urlreverse('ietf.doc.views_doc.edit_authors', kwargs=dict(name=draft.name))
        change_reason = 'no change'

        before = list(draft.documentauthor_set.values('person', 'email', 'affiliation', 'country', 'order'))

        post_data = self.make_edit_authors_post_data(
            authors = draft.documentauthor_set.all(),
            basis=change_reason
        )

        self.login('secretary')
        r = self.client.post(url, post_data)

        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(pk=draft.pk)
        after = list(draft.documentauthor_set.values('person', 'email', 'affiliation', 'country', 'order'))
        self.assertCountEqual(after, before, 'Unexpected change to an author')
        self.assertEqual(EditedAuthorsDocEvent.objects.filter(basis=change_reason).count(), 0)

    def do_edit_authors_append_authors_test(self, new_author_count):
        """Can add author at the end of the list"""
        draft = WgDraftFactory()
        starting_author_count = 3
        DocumentAuthorFactory.create_batch(starting_author_count, document=draft)
        url = urlreverse('ietf.doc.views_doc.edit_authors', kwargs=dict(name=draft.name))
        change_reason = 'add a new author'

        compare_props = 'person', 'email', 'affiliation', 'country', 'order'
        before = list(draft.documentauthor_set.values(*compare_props))
        events_before = EditedAuthorsDocEvent.objects.count()

        post_data = self.make_edit_authors_post_data(
            authors=draft.documentauthor_set.all(),
            basis=change_reason
        )

        new_authors = PersonFactory.create_batch(new_author_count, default_emails=True)
        new_author_data = [
            dict(
                person=new_author.pk,
                email=str(new_author.email()),
                affiliation='University of Somewhere',
                country='Botswana',
            )
            for new_author in new_authors
        ]
        for index, auth_dict in enumerate(new_author_data):
            self.add_author_to_edit_authors_post_data(post_data, auth_dict)
            auth_dict['order'] = starting_author_count + index + 1 # for comparison later

        self.login('secretary')
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(pk=draft.pk)
        after = list(draft.documentauthor_set.values(*compare_props))

        self.assertEqual(len(after), len(before) + new_author_count)
        for b, a in zip(before + new_author_data, after):
            for prop in compare_props:
                self.assertEqual(a[prop], b[prop],
                                 'Unexpected change: "{}" was "{}", changed to "{}"'.format(
                                     prop, b[prop], a[prop]
                                 ))

        self.assertEqual(EditedAuthorsDocEvent.objects.count(), events_before + new_author_count)
        change_events = EditedAuthorsDocEvent.objects.filter(basis=change_reason)
        self.assertEqual(change_events.count(), new_author_count)
        # The events are most-recent first, so first author added is last event in the list.
        # Reverse the author list with [::-1]
        for evt, auth in zip(change_events, new_authors[::-1]):
            self.assertIn('added', evt.desc.lower())
            self.assertIn(auth.name, evt.desc)

    def test_edit_authors_append_author(self):
        self.do_edit_authors_append_authors_test(1)

    def test_edit_authors_append_authors(self):
        self.do_edit_authors_append_authors_test(3)

    def test_edit_authors_insert_author(self):
        """Can add author in the middle of the list"""
        draft = WgDraftFactory()
        DocumentAuthorFactory.create_batch(3, document=draft)
        url = urlreverse('ietf.doc.views_doc.edit_authors', kwargs=dict(name=draft.name))
        change_reason = 'add a new author'

        compare_props = 'person', 'email', 'affiliation', 'country', 'order'
        before = list(draft.documentauthor_set.values(*compare_props))
        events_before = EditedAuthorsDocEvent.objects.count()

        post_data = self.make_edit_authors_post_data(
            authors = draft.documentauthor_set.all(),
            basis=change_reason
        )

        new_author = PersonFactory(default_emails=True)
        new_author_data = dict(
            person=new_author.pk,
            email=str(new_author.email()),
            affiliation='University of Somewhere',
            country='Botswana',
        )
        self.add_author_to_edit_authors_post_data(post_data, new_author_data, insert_order=1)

        self.login('secretary')
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(pk=draft.pk)
        after = list(draft.documentauthor_set.values(*compare_props))

        new_author_data['order'] = 2  # corresponds to insert_order == 1
        expected = copy.deepcopy(before)
        expected.insert(1, new_author_data)
        expected[2]['order'] = 3
        expected[3]['order'] = 4
        self.assertEqual(len(after), len(expected))
        for b, a in zip(expected, after):
            for prop in compare_props:
                self.assertEqual(a[prop], b[prop],
                                 'Unexpected change: "{}" was "{}", changed to "{}"'.format(
                                     prop, b[prop], a[prop]
                                 ))

        # 3 changes: new author, plus two order changes
        self.assertEqual(EditedAuthorsDocEvent.objects.count(), events_before + 3)
        change_events = EditedAuthorsDocEvent.objects.filter(basis=change_reason)
        self.assertEqual(change_events.count(), 3)
        
        add_event = change_events.filter(desc__icontains='added').first()
        reorder_events = change_events.filter(desc__icontains='changed order')
        
        self.assertIsNotNone(add_event)
        self.assertEqual(reorder_events.count(), 2)

    def test_edit_authors_remove_author(self):
        draft = WgDraftFactory()
        DocumentAuthorFactory.create_batch(3, document=draft)
        url = urlreverse('ietf.doc.views_doc.edit_authors', kwargs=dict(name=draft.name))
        change_reason = 'remove an author'

        compare_props = 'person', 'email', 'affiliation', 'country', 'order'
        before = list(draft.documentauthor_set.values(*compare_props))
        events_before = EditedAuthorsDocEvent.objects.count()

        post_data = self.make_edit_authors_post_data(
            authors = draft.documentauthor_set.all(),
            basis=change_reason
        )

        # delete the second author (index == 1)
        deleted_author_data = before.pop(1)
        post_data['author-1-DELETE'] = 'on'  # delete box checked

        self.login('secretary')
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(pk=draft.pk)
        after = list(draft.documentauthor_set.values(*compare_props))

        before[1]['order'] = 2  # was 3, but should have been decremented
        self.assertEqual(len(after), len(before))
        for b, a in zip(before, after):
            for prop in compare_props:
                self.assertEqual(a[prop], b[prop],
                                 'Unexpected change: "{}" was "{}", changed to "{}"'.format(
                                     prop, b[prop], a[prop]
                                 ))

        # expect 2 events: one for removing author, another for reordering the later author
        self.assertEqual(EditedAuthorsDocEvent.objects.count(), events_before + 2)
        change_events = EditedAuthorsDocEvent.objects.filter(basis=change_reason)
        self.assertEqual(change_events.count(), 2)

        removed_event = change_events.filter(desc__icontains='removed').first()
        self.assertIsNotNone(removed_event)
        deleted_person = Person.objects.get(pk=deleted_author_data['person'])
        self.assertIn(deleted_person.name, removed_event.desc)

        reordered_event = change_events.filter(desc__icontains='changed order').first()
        reordered_person = Person.objects.get(pk=after[1]['person'])
        self.assertIsNotNone(reordered_event)
        self.assertIn(reordered_person.name, reordered_event.desc)

    def test_edit_authors_reorder_authors(self):
        draft = WgDraftFactory()
        DocumentAuthorFactory.create_batch(3, document=draft)
        url = urlreverse('ietf.doc.views_doc.edit_authors', kwargs=dict(name=draft.name))
        change_reason = 'reorder the authors'

        compare_props = 'person', 'email', 'affiliation', 'country', 'order'
        before = list(draft.documentauthor_set.values(*compare_props))
        events_before = EditedAuthorsDocEvent.objects.count()

        post_data = self.make_edit_authors_post_data(
            authors = draft.documentauthor_set.all(),
            basis=change_reason
        )
        
        # swap first two authors
        post_data['author-0-ORDER'] = 1
        post_data['author-1-ORDER'] = 0

        self.login('secretary')
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(pk=draft.pk)
        after = list(draft.documentauthor_set.values(*compare_props))

        # swap the 'before' record order
        tmp = before[0]
        before[0] = before[1]
        before[0]['order'] = 1
        before[1] = tmp
        before[1]['order'] = 2
        for b, a in zip(before, after):
            for prop in compare_props:
                self.assertEqual(a[prop], b[prop],
                                 'Unexpected change: "{}" was "{}", changed to "{}"'.format(
                                     prop, b[prop], a[prop]
                                 ))

        # expect 2 events: one for each changed author
        self.assertEqual(EditedAuthorsDocEvent.objects.count(), events_before + 2)
        change_events = EditedAuthorsDocEvent.objects.filter(basis=change_reason)
        self.assertEqual(change_events.count(), 2)
        self.assertEqual(change_events.filter(desc__icontains='changed order').count(), 2)

        self.assertIsNotNone(
            change_events.filter(
                desc__contains=Person.objects.get(pk=before[0]['person']).name
            ).first()
        )
        self.assertIsNotNone(
            change_events.filter(
                desc__contains=Person.objects.get(pk=before[1]['person']).name
            ).first()
        )

    def test_edit_authors_edit_fields(self):
        draft = WgDraftFactory()
        DocumentAuthorFactory.create_batch(
            3,
            document=draft,
            affiliation='Somewhere, Inc.',
            country='Bolivia',
        )
        url = urlreverse('ietf.doc.views_doc.edit_authors', kwargs=dict(name=draft.name))
        change_reason = 'reorder the authors'

        compare_props = 'person', 'email', 'affiliation', 'country', 'order'
        before = list(draft.documentauthor_set.values(*compare_props))
        events_before = EditedAuthorsDocEvent.objects.count()

        post_data = self.make_edit_authors_post_data(
            authors = draft.documentauthor_set.all(),
            basis=change_reason
        )

        old_address = draft.authors()[0].email()
        new_email = EmailFactory(person=draft.authors()[0], address=f'changed-{old_address}')
        post_data['author-0-email'] = new_email.address
        post_data['author-1-affiliation'] = 'University of Nowhere'
        post_data['author-2-country'] = 'Chile'

        self.login('secretary')
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(pk=draft.pk)
        after = list(draft.documentauthor_set.values(*compare_props))

        expected = copy.deepcopy(before)
        expected[0]['email'] = new_email.address
        expected[1]['affiliation'] = 'University of Nowhere'
        expected[2]['country'] = 'Chile'
        for b, a in zip(expected, after):
            for prop in compare_props:
                self.assertEqual(a[prop], b[prop],
                                 'Unexpected change: "{}" was "{}", changed to "{}"'.format(
                                     prop, b[prop], a[prop]
                                 ))

        # expect 3 events: one for each changed author
        self.assertEqual(EditedAuthorsDocEvent.objects.count(), events_before + 3)
        change_events = EditedAuthorsDocEvent.objects.filter(basis=change_reason)
        self.assertEqual(change_events.count(), 3)

        email_event = change_events.filter(desc__icontains='changed email').first()
        affiliation_event = change_events.filter(desc__icontains='changed affiliation').first()
        country_event = change_events.filter(desc__icontains='changed country').first()

        self.assertIsNotNone(email_event)
        self.assertIn(draft.authors()[0].name, email_event.desc)
        self.assertIn(before[0]['email'], email_event.desc)
        self.assertIn(after[0]['email'], email_event.desc)

        self.assertIsNotNone(affiliation_event)
        self.assertIn(draft.authors()[1].name, affiliation_event.desc)
        self.assertIn(before[1]['affiliation'], affiliation_event.desc)
        self.assertIn(after[1]['affiliation'], affiliation_event.desc)

        self.assertIsNotNone(country_event)
        self.assertIn(draft.authors()[2].name, country_event.desc)
        self.assertIn(before[2]['country'], country_event.desc)
        self.assertIn(after[2]['country'], country_event.desc)

    @staticmethod
    def _pyquery_select_action_holder_string(q, s):
        """Helper to use PyQuery to find an action holder in the draft HTML"""
        # selector grabs the action holders heading and finds siblings with a div containing the search string (also in any title attribute)
        return q('th:contains("Action Holder") ~ td>div:contains("%s"), th:contains("Action Holder") ~ td>div *[title*="%s"]' % (s, s))

    @mock.patch.object(Document, 'action_holders_enabled', return_value=False, new_callable=mock.PropertyMock)
    def test_document_draft_hides_action_holders(self, mock_method):
        """Draft should not show action holders when appropriate"""
        draft = WgDraftFactory()
        url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name))
        r = self.client.get(url)
        self.assertNotContains(r, 'Action Holder')  # should not show action holders...

        draft.action_holders.set([PersonFactory()])
        r = self.client.get(url)
        self.assertNotContains(r, 'Action Holder')  # ...even if they are assigned

    @mock.patch.object(Document, 'action_holders_enabled', return_value=True, new_callable=mock.PropertyMock)
    def test_document_draft_shows_action_holders(self, mock_method):
        """Draft should show action holders when appropriate"""
        draft = WgDraftFactory()
        url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name))

        # No action holders case should be shown properly
        r = self.client.get(url)
        self.assertContains(r, 'Action Holder')  # should show action holders
        q = PyQuery(r.content)
        self.assertEqual(len(self._pyquery_select_action_holder_string(q, '(None)')), 1)
        
        # Action holders should be listed when assigned
        draft.action_holders.set(PersonFactory.create_batch(3))
        
        # Make one action holder "old"
        old_action_holder = draft.documentactionholder_set.first()
        old_action_holder.time_added -= datetime.timedelta(days=30)
        old_action_holder.save()

        with self.settings(DOC_ACTION_HOLDER_AGE_LIMIT_DAYS=20):
            r = self.client.get(url)

        self.assertContains(r, 'Action Holder')  # should still be shown
        q = PyQuery(r.content)
        self.assertEqual(len(self._pyquery_select_action_holder_string(q, '(None)')), 0)
        for person in draft.action_holders.all():
            self.assertEqual(len(self._pyquery_select_action_holder_string(q, person.name)), 1)
        # check that one action holder was marked as old
        self.assertEqual(len(self._pyquery_select_action_holder_string(q, 'for 30 days')), 1)

    @mock.patch.object(Document, 'action_holders_enabled', return_value=True, new_callable=mock.PropertyMock)
    def test_document_draft_action_holders_buttons(self, mock_method):
        """Buttons for action holders should be shown when AD or secretary"""
        draft = WgDraftFactory()
        draft.action_holders.set([PersonFactory()])
        other_group = GroupFactory(type_id=draft.group.type_id)

        # create a test RoleName and put it in the docman_roles for the document group
        RoleName.objects.create(slug="wrangler", name="Wrangler", used=True)
        draft.group.features.docman_roles.append("wrangler")
        draft.group.features.save()
        wrangler = RoleFactory(group=draft.group, name_id="wrangler").person
        wrangler_of_other_group = RoleFactory(group=other_group, name_id="wrangler").person

        url = urlreverse('ietf.doc.views_doc.document_main', kwargs=dict(name=draft.name))
        edit_ah_url = urlreverse('ietf.doc.views_doc.edit_action_holders', kwargs=dict(name=draft.name))
        remind_ah_url = urlreverse('ietf.doc.views_doc.remind_action_holders', kwargs=dict(name=draft.name))

        def _run_test(username=None, expect_buttons=False):
            if username:
                self.client.login(username=username, password=username + '+password')
            r = self.client.get(url)
            q = PyQuery(r.content)

            self.assertEqual(
                len(q('th:contains("Action Holder") ~ td a[href="%s"]' % edit_ah_url)),
                1 if expect_buttons else 0,
                '%s should%s see the edit action holders button but %s' % (
                    username if username else 'unauthenticated user',
                    '' if expect_buttons else ' not',
                    'did not' if expect_buttons else 'did',
                )
            )
            self.assertEqual(
                len(q('th:contains("Action Holder") ~ td a[href="%s"]' % remind_ah_url)),
                1 if expect_buttons else 0,
                '%s should%s see the remind action holders button but %s' % (
                    username if username else 'unauthenticated user',
                    '' if expect_buttons else ' not',
                    'did not' if expect_buttons else 'did',
                )
            )

        _run_test(None, False)
        _run_test('plain', False)
        _run_test(wrangler_of_other_group.user.username, False)
        _run_test(wrangler.user.username, True)
        _run_test('ad', True)
        _run_test('secretary', True)

    def test_draft_group_link(self):
        """Link to group 'about' page should have correct format"""
        event_datetime = datetime.datetime(2010, 10, 10, tzinfo=RPC_TZINFO)

        for group_type_id in ['wg', 'rg', 'ag']:
            group = GroupFactory(type_id=group_type_id)
            draft = WgDraftFactory(name='draft-document-%s' % group_type_id, group=group)
            r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))
            self.assertEqual(r.status_code, 200)
            self.assert_correct_wg_group_link(r, group)

            rfc = WgRfcFactory(group=group)
            draft = WgDraftFactory(group=group)
            draft.relateddocument_set.create(relationship_id="became_rfc", target=rfc)
            DocEventFactory.create(doc=rfc, type='published_rfc', time=event_datetime)
            r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=rfc.name)))
            self.assertEqual(r.status_code, 200)
            self.assert_correct_wg_group_link(r, group)

        for group_type_id in ['ietf', 'team']:
            group = GroupFactory(type_id=group_type_id)
            draft = WgDraftFactory(name='draft-document-%s' % group_type_id, group=group)
            r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))
            self.assertEqual(r.status_code, 200)
            self.assert_correct_non_wg_group_link(r, group)

            rfc = WgRfcFactory(group=group)
            draft = WgDraftFactory(name='draft-rfc-document-%s'% group_type_id, group=group)
            draft.relateddocument_set.create(relationship_id="became_rfc", target=rfc)
            DocEventFactory.create(doc=rfc, type='published_rfc', time=event_datetime)
            r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=rfc.name)))
            self.assertEqual(r.status_code, 200)
            self.assert_correct_non_wg_group_link(r, group)

    def test_document_email_authors_button(self):
        # rfc not from draft
        rfc = WgRfcFactory()
        DocEventFactory.create(doc=rfc, type='published_rfc')
        url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=rfc.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('a:contains("Email authors")')), 0, 'Did not expect "Email authors" button')

        # rfc from draft
        draft = WgDraftFactory(group=rfc.group)
        draft.relateddocument_set.create(relationship_id="became_rfc", target=rfc)
        draft.set_state(State.objects.get(used=True, type="draft", slug="rfc"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('a:contains("Email authors")')), 1, 'Expected "Email authors" button')

    def test_document_primary_and_history_views(self):
        IndividualDraftFactory(name='draft-imaginary-independent-submission')
        ConflictReviewFactory(name='conflict-review-imaginary-irtf-submission')
        CharterFactory(name='charter-ietf-mars')
        DocumentFactory(type_id='agenda',name='agenda-72-mars')
        DocumentFactory(type_id='minutes',name='minutes-72-mars')
        DocumentFactory(type_id='slides',name='slides-72-mars-1-active')
        chatlog = DocumentFactory(type_id="chatlog",name='chatlog-72-mars-197001010000')
        polls = DocumentFactory(type_id="polls",name='polls-72-mars-197001010000')
        SessionPresentationFactory(document=chatlog)
        SessionPresentationFactory(document=polls)
        statchg = DocumentFactory(type_id='statchg',name='status-change-imaginary-mid-review')
        statchg.set_state(State.objects.get(type_id='statchg',slug='adrev'))

        # Ensure primary views of both current and historic versions of documents works
        for docname in ["draft-imaginary-independent-submission",
                        "conflict-review-imaginary-irtf-submission",
                        "status-change-imaginary-mid-review",
                        "charter-ietf-mars",
                        "agenda-72-mars",
                        "minutes-72-mars",
                        "slides-72-mars-1-active",
                        "chatlog-72-mars-197001010000",
                        "polls-72-mars-197001010000",
                        # TODO: add
                        #"bluesheets-72-mars-1",
                        #"recording-72-mars-1-00",
                       ]:
            doc = Document.objects.get(name=docname)
            # give it some history
            doc.save_with_history([DocEvent.objects.create(doc=doc, rev=doc.rev, type="changed_document", by=Person.objects.get(user__username="secretary"), desc="Test")])

            doc.rev = "01"
            doc.save_with_history([DocEvent.objects.create(doc=doc, rev=doc.rev, type="changed_document", by=Person.objects.get(user__username="secretary"), desc="Test")])

            # Fetch the main page resulting latest version
            r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc.name)))
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, "%s-01"%docname)

            # Fetch 01 version even when it is last version
            r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc.name,rev="01")))
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, "%s-01"%docname)

            # Fetch version number which is too large, that should redirect to main page
            r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc.name,rev="02")))
            self.assertEqual(r.status_code, 302)

            # Fetch 00 version which should result that version
            r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc.name,rev="00")))
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, "%s-00"%docname)

    def test_rfcqueue_auth48_views(self):
        """Test view handling of RFC editor queue auth48 state"""
        def _change_state(doc, state):
            event = StateDocEventFactory(doc=doc, state=state)
            doc.set_state(event.state)
            doc.save_with_history([event])

        draft = IndividualDraftFactory()

        # Put in an rfceditor state other than auth48
        for state in [('draft-iesg', 'rfcqueue'), ('draft-rfceditor', 'rfc-edit')]:
            _change_state(draft, state)
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'Auth48 status')

        # Put in auth48 state without a URL
        _change_state(draft, ('draft-rfceditor', 'auth48'))
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'Auth48 status')

        # Now add a URL
        documenturl = draft.documenturl_set.create(tag_id='auth48', 
                                                   url='http://rfceditor.example.com/auth48-url')
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Auth48 status')
        self.assertContains(r, documenturl.url)

        # Put in auth48-done state and delete auth48 DocumentURL
        draft.documenturl_set.filter(tag_id='auth48').delete()
        _change_state(draft, ('draft-rfceditor', 'auth48-done'))
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'Auth48 status')


class DocTestCase(TestCase):
    def test_status_change(self):
        statchg = StatusChangeFactory()
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=statchg.name)))
        self.assertEqual(r.status_code, 200)
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=statchg.relateddocument_set.first().target)))
        self.assertEqual(r.status_code, 200)

    def test_document_charter(self):
        CharterFactory(name='charter-ietf-mars')
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name="charter-ietf-mars")))
        self.assertEqual(r.status_code, 200)
    
    def test_incorrect_rfc_url(self):
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name="rfc8989", rev="00")))
        self.assertEqual(r.status_code, 404)

    def test_document_conflict_review(self):
        ConflictReviewFactory(name='conflict-review-imaginary-irtf-submission')

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name='conflict-review-imaginary-irtf-submission')))
        self.assertEqual(r.status_code, 200)

    def test_document_material(self):
        MeetingFactory(type_id='ietf',number='72')
        mars = GroupFactory(type_id='wg',acronym='mars')
        marschairman = PersonFactory(user__username='marschairman')
        mars.role_set.create(name_id='chair',person=marschairman,email=marschairman.email())
        doc = DocumentFactory(
            name="slides-testteam-test-slides",
            rev="00",
            title="Test Slides",
            group__acronym='testteam',
            type_id="slides"
        )
        doc.set_state(State.objects.get(type="slides", slug="active"))

        session = SessionFactory(
            name = "session-72-mars-1",
            meeting = Meeting.objects.get(number='72'),
            group = Group.objects.get(acronym='mars'),
            modified = timezone.now(),
            add_to_schedule=False,
        )
        SchedulingEvent.objects.create(
            session=session,
            status=SessionStatusName.objects.create(slug='scheduled'),
            by = Person.objects.get(user__username="marschairman"),
        )
        SessionPresentation.objects.create(session=session, document=doc, rev=doc.rev)

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "The session for this document was cancelled.")

        SchedulingEvent.objects.create(
            session=session,
            status_id='canceled',
            by = Person.objects.get(user__username="marschairman"), 
        )

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "The session for this document was cancelled.")

    def test_document_ballot(self):
        doc = IndividualDraftFactory()
        ad = Person.objects.get(user__username="ad")
        ballot = create_ballot_if_not_open(None, doc, ad, 'approve')
        assert ballot == doc.active_ballot()

        # make sure we have some history
        doc.save_with_history([DocEvent.objects.create(doc=doc, rev=doc.rev, type="changed_document",
                                                    by=Person.objects.get(user__username="secretary"), desc="Test")])

        pos = BallotPositionDocEvent.objects.create(
            doc=doc,
            rev=doc.rev,
            ballot=ballot,
            type="changed_ballot_position",
            pos_id="yes",
            comment="Looks fine to me",
            comment_time=timezone.now(),
            balloter=Person.objects.get(user__username="ad"),
            by=Person.objects.get(name="(System)"))

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, pos.comment)

        # test with ballot_id
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name, ballot_id=ballot.pk)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, pos.comment)

        # test popup too while we're at it
        r = self.client.get(urlreverse("ietf.doc.views_doc.ballot_popup", kwargs=dict(name=doc.name, ballot_id=ballot.pk)))
        self.assertEqual(r.status_code, 200)

        # Now simulate a new revision and make sure positions on older revisions are marked as such
        oldrev = doc.rev
        e = NewRevisionDocEvent.objects.create(doc=doc,rev='%02d'%(int(doc.rev)+1),type='new_revision',by=Person.objects.get(name="(System)"))
        doc.rev = e.rev
        doc.save_with_history([e])
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)
        self.assertRegex(
            r.content.decode(),
            r'\(\s*%s\s+for\s+-%s\s*\)' % (
                pos.comment_time.astimezone(ZoneInfo(settings.TIME_ZONE)).strftime('%Y-%m-%d'),
                oldrev,
            )
        )

        # Now simulate a new ballot against the new revision and make sure the "was" position is included
        pos2 = BallotPositionDocEvent.objects.create(
            doc=doc,
            rev=doc.rev,
            ballot=ballot,
            type="changed_ballot_position",
            pos_id="noobj",
            comment="Still looks okay to me",
            comment_time=timezone.now(),
            balloter=Person.objects.get(user__username="ad"),
            by=Person.objects.get(name="(System)"))

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, pos2.comment)
        self.assertContains(r,  '(was %s)' % pos.pos)

    def test_document_ballot_popup_unique_anchors_per_doc(self):
        """Ballot popup anchors should be different for each document"""
        ad = Person.objects.get(user__username="ad")
        docs = IndividualDraftFactory.create_batch(2)
        ballots = [create_ballot_if_not_open(None, doc, ad, 'approve') for doc in docs]
        for doc, ballot in zip(docs, ballots):
            BallotPositionDocEvent.objects.create(
                doc=doc,
                rev=doc.rev,
                ballot=ballot,
                type="changed_ballot_position",
                pos_id="yes",
                comment="Looks fine to me",
                comment_time=timezone.now(),
                balloter=Person.objects.get(user__username="ad"),
                by=Person.objects.get(name="(System)"))

        anchors = set()
        author_slug = slugify(ad.plain_name())
        for doc, ballot in zip(docs, ballots):
            r = self.client.get(urlreverse(
                "ietf.doc.views_doc.ballot_popup",
                kwargs=dict(name=doc.name, ballot_id=ballot.pk)
            ))
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            href = q(f'div.balloter-name a[href$="{author_slug}"]').attr('href')
            ids = [
                target.attr('id')
                for target in q(f'div.h5[id$="{author_slug}"]').items()
            ]
            self.assertEqual(len(ids), 1, 'Should be exactly one link for the balloter')
            self.assertEqual(href, f'#{ids[0]}', 'Anchor href should match ID')
            anchors.add(href)
        self.assertEqual(len(anchors), len(docs), 'Each doc should have a distinct anchor for the balloter')

    def test_document_ballot_needed_positions(self):
        # draft
        doc = IndividualDraftFactory(intended_std_level_id='ps')
        doc.set_state(State.objects.get(type_id='draft-iesg',slug='iesg-eva'))
        ad = Person.objects.get(user__username="ad")
        create_ballot_if_not_open(None, doc, ad, 'approve')

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name)))
        self.assertContains(r, 'more YES or NO')
        Document.objects.filter(pk=doc.pk).update(intended_std_level='inf')
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name)))
        self.assertNotContains(r, 'more YES or NO')

        # status change
        Document.objects.create(name='rfc9998')
        Document.objects.create(name='rfc9999')
        doc = DocumentFactory(type_id='statchg',name='status-change-imaginary-mid-review')
        iesgeval_pk = str(State.objects.get(slug='iesgeval',type__slug='statchg').pk)
        empty_outbox()
        self.client.login(username='ad', password='ad+password')
        r = self.client.post(urlreverse('ietf.doc.views_status_change.change_state',kwargs=dict(name=doc.name)),dict(new_state=iesgeval_pk))
        self.assertEqual(r.status_code, 302)
        r = self.client.get(r.headers["location"])
        self.assertContains(r, ">IESG Evaluation<")
        self.assertEqual(len(outbox), 2)
        self.assertIn('iesg-secretary',outbox[0]['To'])
        self.assertIn('drafts-eval',outbox[1]['To'])

        doc.relateddocument_set.create(target=Document.objects.get(name='rfc9998'),relationship_id='tohist')
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name)))
        self.assertNotContains(r, 'Needs a YES')
        self.assertNotContains(r, 'more YES or NO')

        doc.relateddocument_set.create(target=Document.objects.get(name='rfc9999'),relationship_id='tois')
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name)))
        self.assertContains(r, 'more YES or NO')

    def test_document_json(self):
        doc = IndividualDraftFactory()

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_json", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(doc.name, data['name'])
        self.assertEqual(doc.pages,data['pages'])

    def test_writeup(self):
        doc = IndividualDraftFactory(states = [('draft','active'),('draft-iesg','iesg-eva')],)

        appr = WriteupDocEvent.objects.create(
            doc=doc,
            rev=doc.rev,
            desc="Changed text",
            type="changed_ballot_approval_text",
            text="This is ballot approval text.",
            by=Person.objects.get(name="(System)"))

        notes = WriteupDocEvent.objects.create(
            doc=doc,
            rev=doc.rev,
            desc="Changed text",
            type="changed_ballot_writeup_text",
            text="This is ballot writeup notes.",
            by=Person.objects.get(name="(System)"))

        rfced_note = WriteupDocEvent.objects.create(
            doc=doc,
            rev=doc.rev,
            desc="Changed text",
            type="changed_rfc_editor_note_text",
            text="This is a note for the RFC Editor.",
            by=Person.objects.get(name="(System)"))

        url = urlreverse('ietf.doc.views_doc.document_writeup', kwargs=dict(name=doc.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, appr.text)
        self.assertContains(r, notes.text)
        self.assertContains(r, rfced_note.text)

    def test_history(self):
        doc = IndividualDraftFactory()

        e = DocEvent.objects.create(
            doc=doc,
            rev=doc.rev,
            desc="Something happened.",
            type="added_comment",
            by=Person.objects.get(name="(System)"))

        url = urlreverse('ietf.doc.views_doc.document_history', kwargs=dict(name=doc.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, e.desc)

    def test_history_bis_00(self):
        rfc = WgRfcFactory(rfc_number=9090)
        bis_draft = WgDraftFactory(name='draft-ietf-{}-{}bis'.format(rfc.group.acronym,rfc.name))

        url = urlreverse('ietf.doc.views_doc.document_history', kwargs=dict(name=bis_draft.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200) 
        q = PyQuery(unicontent(r))
        attr1='value="{}"'.format(rfc.name)
        self.assertEqual(len(q('option['+attr1+'][selected="selected"]')), 1)


    def test_document_feed(self):
        doc = IndividualDraftFactory()

        e = DocEvent.objects.create(
            doc=doc,
            rev=doc.rev,
            desc="Something happened.",
            type="added_comment",
            by=Person.objects.get(name="(System)"))

        r = self.client.get("/feed/document-changes/%s/" % doc.name)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, e.desc)

    def test_document_feed_with_control_character(self):
        doc = IndividualDraftFactory()

        DocEvent.objects.create(
            doc=doc,
            rev=doc.rev,
            desc="Something happened involving the \x0b character.",
            type="added_comment",
            by=Person.objects.get(name="(System)"))

        r = self.client.get("/feed/document-changes/%s/" % doc.name)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Something happened involving the')

    def test_last_call_feed(self):
        doc = IndividualDraftFactory()

        doc.set_state(State.objects.get(type="draft-iesg", slug="lc"))

        LastCallDocEvent.objects.create(
            doc=doc,
            rev=doc.rev,
            desc="Last call\x0b",  # include a control character to be sure it does not break anything
            type="sent_last_call",
            by=Person.objects.get(user__username="secretary"),
            expires=datetime_today(DEADLINE_TZINFO) + datetime.timedelta(days=7))

        r = self.client.get("/feed/last-call/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, doc.name)

    def test_rfc_feed(self):
        rfc = WgRfcFactory(rfc_number=9000)
        DocEventFactory(doc=rfc, type="published_rfc")
        r = self.client.get("/feed/rfc/")
        self.assertTrue(r.status_code, 200)
        q = PyQuery(r.content[39:]) # Strip off the xml declaration
        self.assertEqual(len(q("item")), 1)
        item = q("item")[0]
        media_content = item.findall("{http://search.yahoo.com/mrss/}content")
        self.assertEqual(len(media_content),4)
        types = set([m.attrib["type"] for m in media_content])
        self.assertEqual(types, set(["application/rfc+xml", "text/plain", "text/html", "application/pdf"]))
        rfcs_2016 = WgRfcFactory.create_batch(3) # rfc numbers will be well below v3
        for rfc in rfcs_2016:
            e = DocEventFactory(doc=rfc, type="published_rfc")
            e.time = e.time.replace(year=2016)
            e.save()
        r = self.client.get("/feed/rfc/2016")
        self.assertTrue(r.status_code, 200)
        q = PyQuery(r.content[39:])
        self.assertEqual(len(q("item")), 3)
        item = q("item")[0]
        media_content = item.findall("{http://search.yahoo.com/mrss/}content")
        self.assertEqual(len(media_content), 3)
        types = set([m.attrib["type"] for m in media_content])
        self.assertEqual(types, set(["text/plain", "text/html", "application/pdf"]))

    def test_state_help(self):
        url = urlreverse('ietf.doc.views_help.state_help', kwargs=dict(type="draft-iesg"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, State.objects.get(type="draft-iesg", slug="lc").name)

    def test_document_nonietf_pubreq_button(self):
        doc = IndividualDraftFactory()

        self.client.login(username='iab-chair', password='iab-chair+password')
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Request publication")

        Document.objects.filter(pk=doc.pk).update(stream='iab')
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Request publication")

        doc.states.add(State.objects.get(type_id='draft-stream-iab',slug='rfc-edit'))
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Request publication")

    def _parse_bibtex_response(self, response) -> dict:
        parser = bibtexparser.bparser.BibTexParser(common_strings=True)
        parser.homogenise_fields = False  # do not modify field names (e.g., turns "url" into "link" by default)
        return bibtexparser.loads(response.content.decode(), parser=parser).get_entry_dict()

    @override_settings(RFC_EDITOR_INFO_BASE_URL='https://www.rfc-editor.ietf.org/info/')
    def test_document_bibtex(self):

        for factory in [CharterFactory, BcpFactory, StatusChangeFactory, ConflictReviewFactory]: # Should be extended to all other doc types
            doc = factory()
            url = urlreverse("ietf.doc.views_doc.document_bibtex", kwargs=dict(name=doc.name))
            r = self.client.get(url)
            self.assertEqual(r.status_code, 404)          
        rfc = WgRfcFactory.create(
            time=datetime.datetime(2010, 10, 10, tzinfo=ZoneInfo(settings.TIME_ZONE))
        )
        num = rfc.rfc_number
        DocEventFactory.create(
            doc=rfc,
            type="published_rfc",
            time=datetime.datetime(2010, 10, 10, tzinfo=RPC_TZINFO),
        )
        #
        url = urlreverse("ietf.doc.views_doc.document_bibtex", kwargs=dict(name=rfc.name))
        r = self.client.get(url)
        entry = self._parse_bibtex_response(r)["rfc%s" % num]
        self.assertEqual(entry["series"], "Request for Comments")
        self.assertEqual(int(entry["number"]), num)
        self.assertEqual(entry["doi"], "10.17487/RFC%s" % num)
        self.assertEqual(entry["year"], "2010")
        self.assertEqual(entry["month"].lower()[0:3], "oct")
        self.assertEqual(entry["url"], f"https://www.rfc-editor.ietf.org/info/rfc{num}")
        #
        self.assertNotIn("day", entry)
    
        # test for incorrect case - revision for RFC
        rfc = WgRfcFactory(name="rfc0000")
        url = urlreverse(
            "ietf.doc.views_doc.document_bibtex", kwargs=dict(name=rfc.name, rev="00")
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)
    
        april1 = IndividualRfcFactory.create(
            stream_id="ise",
            std_level_id="inf",
            time=datetime.datetime(1990, 4, 1, tzinfo=ZoneInfo(settings.TIME_ZONE)),
        )
        num = april1.rfc_number
        DocEventFactory.create(
            doc=april1,
            type="published_rfc",
            time=datetime.datetime(1990, 4, 1, tzinfo=RPC_TZINFO),
        )
        #
        url = urlreverse(
            "ietf.doc.views_doc.document_bibtex", kwargs=dict(name=april1.name)
        )
        r = self.client.get(url)
        self.assertEqual(r.get("Content-Type"), "text/plain; charset=utf-8")
        entry = self._parse_bibtex_response(r)["rfc%s" % num]
        self.assertEqual(entry["series"], "Request for Comments")
        self.assertEqual(int(entry["number"]), num)
        self.assertEqual(entry["doi"], "10.17487/RFC%s" % num)
        self.assertEqual(entry["year"], "1990")
        self.assertEqual(entry["month"].lower()[0:3], "apr")
        self.assertEqual(entry["day"], "1")
        self.assertEqual(entry["url"], f"https://www.rfc-editor.ietf.org/info/rfc{num}")
    
        draft = IndividualDraftFactory.create()
        docname = "%s-%s" % (draft.name, draft.rev)
        bibname = docname[6:]  # drop the 'draft-' prefix
        url = urlreverse("ietf.doc.views_doc.document_bibtex", kwargs=dict(name=draft.name))
        r = self.client.get(url)
        entry = self._parse_bibtex_response(r)[bibname]
        self.assertEqual(entry["note"], "Work in Progress")
        self.assertEqual(entry["number"], docname)
        self.assertEqual(entry["year"], str(draft.pub_date().year))
        self.assertEqual(
            entry["month"].lower()[0:3], draft.pub_date().strftime("%b").lower()
        )
        self.assertEqual(entry["day"], str(draft.pub_date().day))
        self.assertEqual(
            entry["url"],
            settings.IDTRACKER_BASE_URL
            + urlreverse(
                "ietf.doc.views_doc.document_main",
                kwargs=dict(name=draft.name, rev=draft.rev),
            ),
        )
        #
        self.assertNotIn("doi", entry)

    def test_document_bibxml(self):
        draft = IndividualDraftFactory.create()
        docname = '%s-%s' % (draft.name, draft.rev)
        for viewname in [ 'ietf.doc.views_doc.document_bibxml', 'ietf.doc.views_doc.document_bibxml_ref' ]:
            url = urlreverse(viewname, kwargs=dict(name=draft.name))
            r = self.client.get(url)
            entry = lxml.etree.fromstring(r.content)
            self.assertEqual(entry.find('./front/title').text, draft.title)
            date = entry.find('./front/date')
            self.assertEqual(date.get('year'),     str(draft.pub_date().year))
            self.assertEqual(date.get('month'),    draft.pub_date().strftime('%B'))
            self.assertEqual(date.get('day'),      str(draft.pub_date().day))
            self.assertEqual(normalize_text(entry.find('./front/abstract/t').text), normalize_text(draft.abstract))
            self.assertEqual(entry.find('./seriesInfo').get('value'), docname)
            self.assertEqual(entry.find('./seriesInfo[@name="DOI"]'), None)

    def test_trailing_hypen_digit_name_bibxml(self):
        draft = WgDraftFactory(name='draft-ietf-mars-test-2')
        docname = '%s-%s' % (draft.name, draft.rev)
        for viewname in [ 'ietf.doc.views_doc.document_bibxml', 'ietf.doc.views_doc.document_bibxml_ref' ]:
            # This will need to be adjusted if settings.URL_REGEXPS is changed
            url = urlreverse(viewname, kwargs=dict(name=draft.name[:-2], rev=draft.name[-1:]+'-'+draft.rev))
            r = self.client.get(url)
            entry = lxml.etree.fromstring(r.content)
            self.assertEqual(entry.find('./front/title').text, draft.title)
            self.assertEqual(entry.find('./seriesInfo').get('value'), docname)

class AddCommentTestCase(TestCase):
    def test_add_comment(self):
        draft = WgDraftFactory(name='draft-ietf-mars-test',group__acronym='mars')
        url = urlreverse('ietf.doc.views_doc.add_comment', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(unicontent(r))
        self.assertEqual(len(q('form textarea[name=comment]')), 1)

        # request resurrect
        events_before = draft.docevent_set.count()
        mailbox_before = len(outbox)
        
        r = self.client.post(url, dict(comment="This is a test."))
        self.assertEqual(r.status_code, 302)

        self.assertEqual(draft.docevent_set.count(), events_before + 1)
        self.assertEqual("This is a test.", draft.latest_event().desc)
        self.assertEqual("added_comment", draft.latest_event().type)
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertIn("Comment added", outbox[-1]['Subject'])
        self.assertIn(draft.name, outbox[-1]['Subject'])
        self.assertIn('draft-ietf-mars-test@', outbox[-1]['To'])

        # Make sure we can also do it as IANA
        self.client.login(username="iana", password="iana+password")

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(unicontent(r))
        self.assertEqual(len(q('form textarea[name=comment]')), 1)


class TemplateTagTest(TestCase):
    def test_template_tags(self):
        import doctest
        from ietf.doc.templatetags import ietf_filters
        failures, tests = doctest.testmod(ietf_filters)
        self.assertEqual(failures, 0)

class ReferencesTest(TestCase):

    def test_references(self):
        doc1 = WgDraftFactory(name='draft-ietf-mars-test')
        doc2 = IndividualDraftFactory(name='draft-imaginary-independent-submission')
        RelatedDocument.objects.get_or_create(source=doc1,target=doc2,relationship=DocRelationshipName.objects.get(slug='refnorm'))
        url = urlreverse('ietf.doc.views_doc.document_references', kwargs=dict(name=doc1.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, doc2.name)
        url = urlreverse('ietf.doc.views_doc.document_referenced_by', kwargs=dict(name=doc2.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, doc1.name)

class GenerateDraftAliasesTests(TestCase):
    @override_settings(TOOLS_SERVER="tools.example.org", DRAFT_ALIAS_DOMAIN="draft.example.org")
    def test_generator_class(self):
        """The DraftAliasGenerator should generate the same lists as the old mgmt cmd"""
        a_month_ago = (timezone.now() - datetime.timedelta(30)).astimezone(RPC_TZINFO)
        a_month_ago = a_month_ago.replace(hour=0, minute=0, second=0, microsecond=0)
        ad = RoleFactory(
            name_id="ad", group__type_id="area", group__state_id="active"
        ).person
        shepherd = PersonFactory()
        author1 = PersonFactory()
        author2 = PersonFactory()
        author3 = PersonFactory()
        author4 = PersonFactory()
        author5 = PersonFactory()
        author6 = PersonFactory()
        mars = GroupFactory(type_id="wg", acronym="mars")
        marschairman = PersonFactory(user__username="marschairman")
        mars.role_set.create(
            name_id="chair", person=marschairman, email=marschairman.email()
        )
        doc1 = IndividualDraftFactory(authors=[author1], shepherd=shepherd.email(), ad=ad)
        doc2 = WgDraftFactory(
            name="draft-ietf-mars-test", group__acronym="mars", authors=[author2], ad=ad
        )
        doc2.notify = f"{doc2.name}.ad@draft.example.org"
        doc2.save()
        doc3 = WgDraftFactory.create(
            name="draft-ietf-mars-finished",
            group__acronym="mars",
            authors=[author3],
            ad=ad,
            std_level_id="ps",
            states=[("draft", "rfc"), ("draft-iesg", "pub")],
            time=a_month_ago,
        )
        rfc3 = WgRfcFactory()
        DocEventFactory.create(doc=rfc3, type="published_rfc", time=a_month_ago)
        doc3.relateddocument_set.create(relationship_id="became_rfc", target=rfc3)
        doc4 = WgDraftFactory.create(
            authors=[author4, author5],
            ad=ad,
            std_level_id="ps",
            states=[("draft", "rfc"), ("draft-iesg", "pub")],
            time=datetime.datetime(2010, 10, 10, tzinfo=ZoneInfo(settings.TIME_ZONE)),
        )
        rfc4 = WgRfcFactory()
        DocEventFactory.create(
            doc=rfc4,
            type="published_rfc",
            time=datetime.datetime(2010, 10, 10, tzinfo=RPC_TZINFO),
        )
        doc4.relateddocument_set.create(relationship_id="became_rfc", target=rfc4)
        doc5 = IndividualDraftFactory(authors=[author6])

        output = [(alias, alist) for alias, alist in DraftAliasGenerator()]
        alias_dict = dict(output)
        self.assertEqual(len(alias_dict), len(output))  # no duplicate aliases
        expected_dict = {
            doc1.name: [author1.email_address()],
            doc1.name + ".ad": [ad.email_address()],
            doc1.name + ".authors": [author1.email_address()],
            doc1.name + ".shepherd": [shepherd.email_address()],
            doc1.name
            + ".all": [
                author1.email_address(),
                ad.email_address(),
                shepherd.email_address(),
            ],
            doc2.name: [author2.email_address()],
            doc2.name + ".ad": [ad.email_address()],
            doc2.name + ".authors": [author2.email_address()],
            doc2.name + ".chairs": [marschairman.email_address()],
            doc2.name + ".notify": [ad.email_address()],
            doc2.name
            + ".all": [
                author2.email_address(),
                ad.email_address(),
                marschairman.email_address(),
            ],
            doc3.name: [author3.email_address()],
            doc3.name + ".ad": [ad.email_address()],
            doc3.name + ".authors": [author3.email_address()],
            doc3.name + ".chairs": [marschairman.email_address()],
            doc3.name
            + ".all": [
                author3.email_address(),
                ad.email_address(),
                marschairman.email_address(),
            ],
            doc5.name: [author6.email_address()],
            doc5.name + ".authors": [author6.email_address()],
            doc5.name + ".all": [author6.email_address()],
        }
        # Sort lists for comparison
        self.assertEqual(
            {k: sorted(v) for k, v in alias_dict.items()},
            {k: sorted(v) for k, v in expected_dict.items()},
        )

        # check single name
        output = [(alias, alist) for alias, alist in DraftAliasGenerator(Document.objects.filter(name=doc1.name))]
        alias_dict = dict(output)
        self.assertEqual(len(alias_dict), len(output))  # no duplicate aliases
        expected_dict = {
            doc1.name: [author1.email_address()],
            doc1.name + ".ad": [ad.email_address()],
            doc1.name + ".authors": [author1.email_address()],
            doc1.name + ".shepherd": [shepherd.email_address()],
            doc1.name
            + ".all": [
                author1.email_address(),
                ad.email_address(),
                shepherd.email_address(),
            ],
        }
        # Sort lists for comparison
        self.assertEqual(
            {k: sorted(v) for k, v in alias_dict.items()},
            {k: sorted(v) for k, v in expected_dict.items()},
        )

    @override_settings(TOOLS_SERVER="tools.example.org", DRAFT_ALIAS_DOMAIN="draft.example.org")
    def test_get_draft_notify_emails(self):
        ad = PersonFactory()
        shepherd = PersonFactory()
        author = PersonFactory()
        doc = DocumentFactory(authors=[author], shepherd=shepherd.email(), ad=ad)
        generator = DraftAliasGenerator()

        doc.notify = f"{doc.name}@draft.example.org"
        doc.save()
        self.assertCountEqual(generator.get_draft_notify_emails(doc), [author.email_address()])

        doc.notify = f"{doc.name}.ad@draft.example.org"
        doc.save()
        self.assertCountEqual(generator.get_draft_notify_emails(doc), [ad.email_address()])

        doc.notify = f"{doc.name}.shepherd@draft.example.org"
        doc.save()
        self.assertCountEqual(generator.get_draft_notify_emails(doc), [shepherd.email_address()])

        doc.notify = f"{doc.name}.all@draft.example.org"
        doc.save()
        self.assertCountEqual(
            generator.get_draft_notify_emails(doc),
            [ad.email_address(), author.email_address(), shepherd.email_address()]
        )

        doc.notify = f"{doc.name}.notify@draft.example.org"
        doc.save()
        self.assertCountEqual(generator.get_draft_notify_emails(doc), [])

        doc.notify = f"{doc.name}.ad@somewhere.example.com"
        doc.save()
        self.assertCountEqual(generator.get_draft_notify_emails(doc), [f"{doc.name}.ad@somewhere.example.com"])
        
        doc.notify = f"somebody@example.com, nobody@example.com, {doc.name}.ad@tools.example.org"
        doc.save()
        self.assertCountEqual(
            generator.get_draft_notify_emails(doc),
            ["somebody@example.com", "nobody@example.com", ad.email_address()]
        )


class EmailAliasesTests(TestCase):

    def setUp(self):
        super().setUp()
        WgDraftFactory(name='draft-ietf-mars-test',group__acronym='mars')
        WgDraftFactory(name='draft-ietf-ames-test',group__acronym='ames')
        RoleFactory(group__type_id='review', group__acronym='yangdoctors', name_id='secr')


    @mock.patch("ietf.doc.views_doc.get_doc_email_aliases")
    def testAliases(self, mock_get_aliases):
        mock_get_aliases.return_value = [
            {"doc_name": "draft-ietf-mars-test", "alias_type": "", "expansion": "mars-author@example.mars, mars-collaborator@example.mars"},
            {"doc_name": "draft-ietf-mars-test", "alias_type": ".authors", "expansion": "mars-author@example.mars, mars-collaborator@example.mars"},
            {"doc_name": "draft-ietf-mars-test", "alias_type": ".chairs", "expansion": "mars-chair@example.mars"},
            {"doc_name": "draft-ietf-mars-test", "alias_type": ".all", "expansion": "mars-author@example.mars, mars-collaborator@example.mars, mars-chair@example.mars"},
            {"doc_name": "draft-ietf-ames-test", "alias_type": "", "expansion": "ames-author@example.ames, ames-collaborator@example.ames"},
            {"doc_name": "draft-ietf-ames-test", "alias_type": ".authors", "expansion": "ames-author@example.ames, ames-collaborator@example.ames"},
            {"doc_name": "draft-ietf-ames-test", "alias_type": ".chairs", "expansion": "ames-chair@example.ames"},
            {"doc_name": "draft-ietf-ames-test", "alias_type": ".all", "expansion": "ames-author@example.ames, ames-collaborator@example.ames, ames-chair@example.ames"},
        ]
        PersonFactory(user__username='plain')
        url = urlreverse('ietf.doc.urls.redirect.document_email', kwargs=dict(name="draft-ietf-mars-test"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)

        url = urlreverse('ietf.doc.views_doc.email_aliases', kwargs=dict())
        login_testing_unauthorized(self, "plain", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(mock_get_aliases.call_args, mock.call())
        self.assertTrue(all([x in unicontent(r) for x in ['mars-test@','mars-test.authors@','mars-test.chairs@']]))
        self.assertTrue(all([x in unicontent(r) for x in ['ames-test@','ames-test.authors@','ames-test.chairs@']]))


    @mock.patch("ietf.doc.views_doc.get_doc_email_aliases")
    def testExpansions(self, mock_get_aliases):
        mock_get_aliases.return_value = [
            {"doc_name": "draft-ietf-mars-test", "alias_type": "", "expansion": "mars-author@example.mars, mars-collaborator@example.mars"},
            {"doc_name": "draft-ietf-mars-test", "alias_type": ".authors", "expansion": "mars-author@example.mars, mars-collaborator@example.mars"},
            {"doc_name": "draft-ietf-mars-test", "alias_type": ".chairs", "expansion": "mars-chair@example.mars"},
            {"doc_name": "draft-ietf-mars-test", "alias_type": ".all", "expansion": "mars-author@example.mars, mars-collaborator@example.mars, mars-chair@example.mars"},
        ]
        url = urlreverse('ietf.doc.views_doc.document_email', kwargs=dict(name="draft-ietf-mars-test"))
        r = self.client.get(url)
        self.assertEqual(mock_get_aliases.call_args, mock.call("draft-ietf-mars-test"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'draft-ietf-mars-test.all@ietf.org')
        self.assertContains(r, 'iesg_ballot_saved')
    
    @mock.patch("ietf.doc.utils.DraftAliasGenerator")
    def test_get_doc_email_aliases(self, mock_alias_gen_cls):
        mock_alias_gen_cls.return_value = [
            ("draft-something-or-other.some-type", ["somebody@example.com"]),
            ("draft-something-or-other", ["somebody@example.com"]),
            ("draft-nothing-at-all", ["nobody@example.com"]),
            ("draft-nothing-at-all.some-type", ["nobody@example.com"]),
        ]
        # order is important in the response - should be sorted by doc name and otherwise left
        # in order
        self.assertEqual(
            get_doc_email_aliases(),
            [
                {
                    "doc_name": "draft-nothing-at-all",
                    "alias_type": "",
                    "expansion": "nobody@example.com",
                },
                {
                    "doc_name": "draft-nothing-at-all",
                    "alias_type": ".some-type",
                    "expansion": "nobody@example.com",
                },
                {
                    "doc_name": "draft-something-or-other",
                    "alias_type": ".some-type",
                    "expansion": "somebody@example.com",
                },
                {
                    "doc_name": "draft-something-or-other",
                    "alias_type": "",
                    "expansion": "somebody@example.com",
                },
            ],
        )
        self.assertEqual(mock_alias_gen_cls.call_args, mock.call(None))

        # Repeat with a name, no need to re-test that the alias list is actually passed through, just
        # check that the DraftAliasGenerator is called correctly
        draft = WgDraftFactory()
        get_doc_email_aliases(draft.name)
        self.assertQuerySetEqual(mock_alias_gen_cls.call_args[0][0], Document.objects.filter(pk=draft.pk))
        
        
class DocumentMeetingTests(TestCase):

    def setUp(self):
        super().setUp()
        self.group = GroupFactory(type_id='wg',state_id='active')
        self.group_chair = PersonFactory()
        self.group.role_set.create(name_id='chair',person=self.group_chair,email=self.group_chair.email())

        self.other_group = GroupFactory(type_id='wg',state_id='active')
        self.other_chair = PersonFactory()
        self.other_group.role_set.create(name_id='chair',person=self.other_chair,email=self.other_chair.email())

        today = date_today()
        cut_days = settings.MEETING_MATERIALS_DEFAULT_SUBMISSION_CORRECTION_DAYS
        self.past_cutoff = SessionFactory.create(meeting__type_id='ietf',group=self.group,meeting__date=today-datetime.timedelta(days=1+cut_days))
        self.past = SessionFactory.create(meeting__type_id='ietf',group=self.group,meeting__date=today-datetime.timedelta(days=cut_days/2))
        self.inprog = SessionFactory.create(meeting__type_id='ietf',group=self.group,meeting__date=today-datetime.timedelta(days=1))
        self.future = SessionFactory.create(meeting__type_id='ietf',group=self.group,meeting__date=today+datetime.timedelta(days=90))
        self.interim = SessionFactory.create(meeting__type_id='interim',group=self.group,meeting__date=today+datetime.timedelta(days=45))

    def test_view_document_meetings(self):
        doc = IndividualDraftFactory.create()
        doc.presentations.create(session=self.inprog,rev=None)
        doc.presentations.create(session=self.interim,rev=None)

        url = urlreverse('ietf.doc.views_doc.all_presentations', kwargs=dict(name=doc.name))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertTrue(all([q(id) for id in ['#inprogressmeets','#futuremeets']]))
        self.assertFalse(any([q(id) for id in ['#pastmeets',]]))
        self.assertFalse(q('#addsessionsbutton'))
        self.assertFalse(q("a.btn:contains('Remove document')"))

        doc.presentations.create(session=self.past_cutoff,rev=None)
        doc.presentations.create(session=self.past,rev=None)

        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertTrue(q('#addsessionsbutton'))
        self.assertEqual(1,len(q("#inprogressmeets a.btn-primary:contains('Remove document')")))
        self.assertEqual(1,len(q("#futuremeets a.btn-primary:contains('Remove document')")))
        self.assertEqual(1,len(q("#pastmeets a.btn-primary:contains('Remove document')")))
        self.assertEqual(1,len(q("#pastmeets a.btn-warning:contains('Remove document')")))

        self.client.login(username=self.group_chair.user.username,password='%s+password'%self.group_chair.user.username)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertTrue(q('#addsessionsbutton'))
        self.assertEqual(1,len(q("#inprogressmeets a.btn-primary:contains('Remove document')")))
        self.assertEqual(1,len(q("#futuremeets a.btn-primary:contains('Remove document')")))
        self.assertEqual(1,len(q("#pastmeets a.btn-primary:contains('Remove document')")))
        self.assertTrue(q('#pastmeets'))
        self.assertFalse(q("#pastmeets a.btn-warning:contains('Remove document')"))

        self.client.login(username=self.other_chair.user.username,password='%s+password'%self.other_chair.user.username)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertTrue(q('#addsessionsbutton'))
        self.assertTrue(all([q(id) for id in ['#futuremeets','#pastmeets','#inprogressmeets']]))
        self.assertFalse(q("#inprogressmeets a.btn:contains('Remove document')"))
        self.assertFalse(q("#futuremeets a.btn:contains('Remove document')"))
        self.assertFalse(q("#pastmeets a.btn:contains('Remove document')"))

    @override_settings(MEETECHO_API_CONFIG="fake settings")
    @mock.patch("ietf.doc.views_doc.SlidesManager")
    def test_edit_document_session(self, mock_slides_manager_cls):
        doc = IndividualDraftFactory.create()
        sp = doc.presentations.create(session=self.future,rev=None)

        url = urlreverse('ietf.doc.views_doc.edit_sessionpresentation',kwargs=dict(name='no-such-doc',session_id=sp.session_id))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(mock_slides_manager_cls.called)

        url = urlreverse('ietf.doc.views_doc.edit_sessionpresentation',kwargs=dict(name=doc.name,session_id=0))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(mock_slides_manager_cls.called)

        url = urlreverse('ietf.doc.views_doc.edit_sessionpresentation',kwargs=dict(name=doc.name,session_id=sp.session_id))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(mock_slides_manager_cls.called)

        self.client.login(username=self.other_chair.user.username,password='%s+password'%self.other_chair.user.username)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(mock_slides_manager_cls.called)

        self.client.login(username=self.group_chair.user.username,password='%s+password'%self.group_chair.user.username)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(2,len(q('select#id_version option')))
        self.assertFalse(mock_slides_manager_cls.called)

        # edit draft
        self.assertEqual(1,doc.docevent_set.count())
        response = self.client.post(url,{'version':'00','save':''})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(doc.presentations.get(pk=sp.pk).rev,'00')
        self.assertEqual(2,doc.docevent_set.count())
        self.assertFalse(mock_slides_manager_cls.called)

        # editing slides should call Meetecho API
        slides = SessionPresentationFactory(
            session=self.future,
            document__type_id="slides",
            document__rev="00",
            rev=None,
            order=1,
        ).document
        url = urlreverse(
            "ietf.doc.views_doc.edit_sessionpresentation",
            kwargs={"name": slides.name, "session_id": self.future.pk},
        )
        response = self.client.post(url, {"version": "00", "save": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(mock_slides_manager_cls.call_count, 1)
        self.assertEqual(mock_slides_manager_cls.call_args, mock.call(api_config="fake settings"))
        self.assertEqual(mock_slides_manager_cls.return_value.send_update.call_count, 1)
        self.assertEqual(
            mock_slides_manager_cls.return_value.send_update.call_args,
            mock.call(self.future),
        )

    def test_edit_document_session_after_proceedings_closed(self):
        doc = IndividualDraftFactory.create()
        sp = doc.presentations.create(session=self.past_cutoff,rev=None)

        url = urlreverse('ietf.doc.views_doc.edit_sessionpresentation',kwargs=dict(name=doc.name,session_id=sp.session_id))
        self.client.login(username=self.group_chair.user.username,password='%s+password'%self.group_chair.user.username)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        
        self.client.login(username='secretary',password='secretary+password')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q=PyQuery(response.content)
        self.assertEqual(1,len(q(".alert-warning:contains('may affect published proceedings')")))

    @override_settings(MEETECHO_API_CONFIG="fake settings")
    @mock.patch("ietf.doc.views_doc.SlidesManager")
    def test_remove_document_session(self, mock_slides_manager_cls):
        doc = IndividualDraftFactory.create()
        sp = doc.presentations.create(session=self.future,rev=None)

        url = urlreverse('ietf.doc.views_doc.remove_sessionpresentation',kwargs=dict(name='no-such-doc',session_id=sp.session_id))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(mock_slides_manager_cls.called)

        url = urlreverse('ietf.doc.views_doc.remove_sessionpresentation',kwargs=dict(name=doc.name,session_id=0))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(mock_slides_manager_cls.called)

        url = urlreverse('ietf.doc.views_doc.remove_sessionpresentation',kwargs=dict(name=doc.name,session_id=sp.session_id))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(mock_slides_manager_cls.called)

        self.client.login(username=self.other_chair.user.username,password='%s+password'%self.other_chair.user.username)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(mock_slides_manager_cls.called)

        self.client.login(username=self.group_chair.user.username,password='%s+password'%self.group_chair.user.username)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(mock_slides_manager_cls.called)

        # removing a draft
        self.assertEqual(1,doc.docevent_set.count())
        response = self.client.post(url,{'remove_session':''})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(doc.presentations.filter(pk=sp.pk).exists())
        self.assertEqual(2,doc.docevent_set.count())
        self.assertFalse(mock_slides_manager_cls.called)

        # removing slides should call Meetecho API
        slides = SessionPresentationFactory(session=self.future, document__type_id="slides", order=1).document
        url = urlreverse(
            "ietf.doc.views_doc.remove_sessionpresentation",
            kwargs={"name": slides.name, "session_id": self.future.pk},
        )
        response = self.client.post(url, {"remove_session": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(mock_slides_manager_cls.call_count, 1)
        self.assertEqual(mock_slides_manager_cls.call_args, mock.call(api_config="fake settings"))
        self.assertEqual(mock_slides_manager_cls.return_value.delete.call_count, 1)
        self.assertEqual(
            mock_slides_manager_cls.return_value.delete.call_args,
            mock.call(self.future, slides),
        )

    def test_remove_document_session_after_proceedings_closed(self):
        doc = IndividualDraftFactory.create()
        sp = doc.presentations.create(session=self.past_cutoff,rev=None)

        url = urlreverse('ietf.doc.views_doc.remove_sessionpresentation',kwargs=dict(name=doc.name,session_id=sp.session_id))
        self.client.login(username=self.group_chair.user.username,password='%s+password'%self.group_chair.user.username)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        
        self.client.login(username='secretary',password='secretary+password')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q=PyQuery(response.content)
        self.assertEqual(1,len(q(".alert-warning:contains('may affect published proceedings')")))

    @override_settings(MEETECHO_API_CONFIG="fake settings")
    @mock.patch("ietf.doc.views_doc.SlidesManager")
    def test_add_document_session(self, mock_slides_manager_cls):
        doc = IndividualDraftFactory.create()

        url = urlreverse('ietf.doc.views_doc.add_sessionpresentation',kwargs=dict(name=doc.name))
        login_testing_unauthorized(self,self.group_chair.user.username,url)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        self.assertFalse(mock_slides_manager_cls.called)

        response = self.client.post(url,{'session':0,'version':'current'})
        self.assertEqual(response.status_code,200)
        q=PyQuery(response.content)
        self.assertTrue(q('.form-select.is-invalid'))
        self.assertFalse(mock_slides_manager_cls.called)

        response = self.client.post(url,{'session':self.future.pk,'version':'bogus version'})
        self.assertEqual(response.status_code,200)
        q=PyQuery(response.content)
        self.assertTrue(q('.form-select.is-invalid'))
        self.assertFalse(mock_slides_manager_cls.called)

        # adding a draft
        self.assertEqual(1,doc.docevent_set.count())
        response = self.client.post(url,{'session':self.future.pk,'version':'current'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(2,doc.docevent_set.count())
        self.assertEqual(doc.presentations.get(session__pk=self.future.pk).order, 0)
        self.assertFalse(mock_slides_manager_cls.called)

        # adding slides should set order / call Meetecho API
        slides = DocumentFactory(type_id="slides")
        url = urlreverse("ietf.doc.views_doc.add_sessionpresentation", kwargs=dict(name=slides.name))
        response = self.client.post(url, {"session": self.future.pk, "version": "current"})
        self.assertEqual(response.status_code,302)
        self.assertEqual(slides.presentations.get(session__pk=self.future.pk).order, 1)
        self.assertEqual(mock_slides_manager_cls.call_args, mock.call(api_config="fake settings"))
        self.assertEqual(mock_slides_manager_cls.return_value.add.call_count, 1)
        self.assertEqual(
            mock_slides_manager_cls.return_value.add.call_args,
            mock.call(self.future, slides, order=1),
        )

    def test_get_related_meeting(self):
        """Should be able to retrieve related meeting"""
        meeting = MeetingFactory(type_id='ietf')
        session = SessionFactory(meeting=meeting)
        procmat = ProceedingsMaterialFactory(meeting=meeting)
        for doctype in DocTypeName.objects.filter(used=True):
            doc = DocumentFactory(type=doctype)
            self.assertIsNone(doc.get_related_meeting(), 'Doc does not yet have a connection to the meeting')
            # test through a session
            doc.session_set.add(session)
            doc = Document.objects.get(pk=doc.pk)
            if doc.meeting_related():
                self.assertEqual(doc.get_related_meeting(), meeting, f'{doc.type.slug} should be related to meeting')
            else:
                self.assertIsNone(doc.get_related_meeting(), f'{doc.type.slug} should not be related to meeting')
            # test with both session and procmat
            doc.proceedingsmaterial_set.add(procmat)
            doc = Document.objects.get(pk=doc.pk)
            if doc.meeting_related():
                self.assertEqual(doc.get_related_meeting(), meeting, f'{doc.type.slug} should be related to meeting')
            else:
                self.assertIsNone(doc.get_related_meeting(), f'{doc.type.slug} should not be related to meeting')
            # and test with only procmat
            doc.session_set.remove(session)
            doc = Document.objects.get(pk=doc.pk)
            if doc.meeting_related():
                self.assertEqual(doc.get_related_meeting(), meeting, f'{doc.type.slug} should be related to meeting')
            else:
                self.assertIsNone(doc.get_related_meeting(), f'{doc.type.slug} should not be related to meeting')

class ChartTests(ResourceTestCaseMixin, TestCase):
    def test_search_chart_conf(self):
        doc = IndividualDraftFactory()

        conf_url = urlreverse('ietf.doc.views_stats.chart_conf_newrevisiondocevent')

        # No qurey arguments; expect an empty json object
        r = self.client.get(conf_url)
        self.assertValidJSONResponse(r)
        self.assertEqual(unicontent(r), '{}')

        # No match
        r = self.client.get(conf_url + '?activedrafts=on&name=thisisnotadocumentname')
        self.assertValidJSONResponse(r)
        d = r.json()
        self.assertEqual(d['chart']['type'], settings.CHART_TYPE_COLUMN_OPTIONS['chart']['type'])

        r = self.client.get(conf_url + '?activedrafts=on&name=%s'%doc.name[6:12])
        self.assertValidJSONResponse(r)
        d = r.json()
        self.assertEqual(d['chart']['type'], settings.CHART_TYPE_COLUMN_OPTIONS['chart']['type'])
        self.assertEqual(len(d['series'][0]['data']), 0)

    def test_search_chart_data(self):
        doc = IndividualDraftFactory()

        data_url = urlreverse('ietf.doc.views_stats.chart_data_newrevisiondocevent')

        # No qurey arguments; expect an empty json list
        r = self.client.get(data_url)
        self.assertValidJSONResponse(r)
        self.assertEqual(unicontent(r), '[]')

        # No match
        r = self.client.get(data_url + '?activedrafts=on&name=thisisnotadocumentname')
        self.assertValidJSONResponse(r)
        d = r.json()
        self.assertEqual(unicontent(r), '[]')

        r = self.client.get(data_url + '?activedrafts=on&name=%s'%doc.name[6:12])
        self.assertValidJSONResponse(r)
        d = r.json()
        self.assertEqual(len(d), 1)
        self.assertEqual(len(d[0]), 2)

    def test_search_chart(self):
        doc = IndividualDraftFactory()

        chart_url = urlreverse('ietf.doc.views_stats.chart_newrevisiondocevent')
        r = self.client.get(chart_url)
        self.assertEqual(r.status_code, 200)

        r = self.client.get(chart_url + '?activedrafts=on&name=%s'%doc.name[6:12])
        self.assertEqual(r.status_code, 200)
        
    def test_personal_chart(self):
        person = PersonFactory.create()
        IndividualDraftFactory.create(
            authors=[person, ],
        )

        conf_url = urlreverse('ietf.doc.views_stats.chart_conf_person_drafts', kwargs=dict(id=person.id))

        r = self.client.get(conf_url)
        self.assertValidJSONResponse(r)
        d = r.json()
        self.assertEqual(d['chart']['type'], settings.CHART_TYPE_COLUMN_OPTIONS['chart']['type'])
        self.assertEqual("New Internet-Draft revisions over time for %s" % person.name, d['title']['text'])

        data_url = urlreverse('ietf.doc.views_stats.chart_data_person_drafts', kwargs=dict(id=person.id))

        r = self.client.get(data_url)
        self.assertValidJSONResponse(r)
        d = r.json()
        self.assertEqual(len(d), 1)
        self.assertEqual(len(d[0]), 2)
        self.assertEqual(d[0][1], 1) 

        page_url = urlreverse('ietf.person.views.profile', kwargs=dict(email_or_name=person.name))
        r = self.client.get(page_url)
        self.assertEqual(r.status_code, 200)
        

class FieldTests(TestCase):
    def test_searchabledocumentsfield_pre(self):
        # so far, just tests that the format expected by select2 set up
        docs = IndividualDraftFactory.create_batch(3)

        class _TestForm(Form):
            test_field = SearchableDocumentsField()
        
        form = _TestForm(initial=dict(test_field=docs))
        html = str(form)
        q = PyQuery(html)
        json_data = q('.select2-field').attr('data-pre')
        try:
            decoded = json.loads(json_data)
        except json.JSONDecodeError as e:
            self.fail('data-pre contained invalid JSON data: %s' % str(e))
        decoded_ids = [item['id'] for item in decoded]
        self.assertEqual(decoded_ids, [doc.id for doc in docs])
        for doc in docs:
            self.assertEqual(
                dict(id=doc.pk, selected=True, url=doc.get_absolute_url(), text=escape(uppercase_std_abbreviated_name(doc.name))),
                decoded[decoded_ids.index(doc.pk)],
            )

class MaterialsTests(TestCase):
    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + ['AGENDA_PATH']
    def setUp(self):
        super().setUp()

        meeting_number='111'
        meeting_dir = Path(settings.AGENDA_PATH) / meeting_number
        meeting_dir.mkdir()
        agenda_dir = meeting_dir / 'agenda'
        agenda_dir.mkdir()

        group_acronym='bogons'

        # This is too much work - the factory should 
        # * build the DocumentHistory correctly 
        # * maybe do something by default with uploaded_filename
        # and there should be a more usable unit to save bits to disk (handle_file_upload isn't quite right) that tests can leverage
        uploaded_filename_00 = f'agenda-{meeting_number}-{group_acronym}-00.txt'
        uploaded_filename_01 = f'agenda-{meeting_number}-{group_acronym}-01.md'
        f = io.open(os.path.join(agenda_dir, uploaded_filename_00), 'w')
        f.write('This is some unremarkable text')
        f.close()
        f = io.open(os.path.join(agenda_dir, uploaded_filename_01), 'w')
        f.write('This links to [an unusual place](https://unusual.example).')
        f.close()

        self.doc = DocumentFactory(type_id='agenda',rev='00',group__acronym=group_acronym, newrevisiondocevent=None, name=f'agenda-{meeting_number}-{group_acronym}', uploaded_filename=uploaded_filename_00)
        e = NewRevisionDocEventFactory(doc=self.doc,rev='00')
        self.doc.save_with_history([e])
        self.doc.rev = '01'
        self.doc.uploaded_filename = uploaded_filename_01
        e = NewRevisionDocEventFactory(doc=self.doc, rev='01')
        self.doc.save_with_history([e])

        # This is necessary for the view to be able to find the document
        # which hints that the view has an issue : if a materials document is taken out of all SessionPresentations, it is no longer accessible by this view
        SessionPresentationFactory(session__meeting__number=meeting_number, session__group=self.doc.group, document=self.doc)

    def test_markdown_and_text(self):
        url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=self.doc.name,rev='00'))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertTrue(q('#materials-content pre'))

        url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=self.doc.name,rev='01'))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(q('#materials-content .card-body a').attr['href'],'https://unusual.example')

class Idnits2SupportTests(TestCase):
    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + ['DERIVED_DIR']

    def test_generate_idnits2_rfcs_obsoleted(self):
        rfc = WgRfcFactory(rfc_number=1001)
        WgRfcFactory(rfc_number=1003,relations=[('obs',rfc)])
        rfc = WgRfcFactory(rfc_number=1005)
        WgRfcFactory(rfc_number=1007,relations=[('obs',rfc)])
        blob = generate_idnits2_rfcs_obsoleted()
        self.assertEqual(blob, b'1001 1003\n1005 1007\n'.decode("utf8"))

    def test_obsoleted(self):
        url = urlreverse('ietf.doc.views_doc.idnits2_rfcs_obsoleted')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)
        # value written is arbitrary, expect it to be passed through
        (Path(settings.DERIVED_DIR) / "idnits2-rfcs-obsoleted").write_bytes(b'1001 1003\n1005 1007\n')
        url = urlreverse('ietf.doc.views_doc.idnits2_rfcs_obsoleted')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b'1001 1003\n1005 1007\n')

    def test_generate_idnits2_rfc_status(self):
        for slug in ('bcp', 'ds', 'exp', 'hist', 'inf', 'std', 'ps', 'unkn'):
            WgRfcFactory(std_level_id=slug)
        blob = generate_idnits2_rfc_status().replace("\n", "")
        self.assertEqual(blob[6312-1], "O")

    def test_rfc_status(self):
        url = urlreverse('ietf.doc.views_doc.idnits2_rfc_status')
        r = self.client.get(url)
        self.assertEqual(r.status_code,404)
        # value written is arbitrary, expect it to be passed through
        (Path(settings.DERIVED_DIR) / "idnits2-rfc-status").write_bytes(b'1001 1003\n1005 1007\n')
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.content, b'1001 1003\n1005 1007\n')

    def test_idnits2_state(self):
        rfc = WgRfcFactory()
        draft = WgDraftFactory()
        draft.relateddocument_set.create(relationship_id="became_rfc", target=rfc)
        url = urlreverse('ietf.doc.views_doc.idnits2_state', kwargs=dict(name=rfc.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r,'rfcnum')

        draft = WgDraftFactory()
        url = urlreverse('ietf.doc.views_doc.idnits2_state', kwargs=dict(name=draft.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r,'rfcnum')
        self.assertContains(r,'Unknown')

        draft = WgDraftFactory(intended_std_level_id='ps')
        url = urlreverse('ietf.doc.views_doc.idnits2_state', kwargs=dict(name=draft.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r,'Proposed')


class RawIdTests(TestCase):

    def __init__(self, *args, **kwargs):
        self.view = "ietf.doc.views_doc.document_raw_id"
        self.mimetypes = {'txt':'text/plain','html':'text/html','xml':'application/xml'}
        super(self.__class__, self).__init__(*args, **kwargs)

    def should_succeed(self, argdict):
        url = urlreverse(self.view, kwargs=argdict)
        r = self.client.get(url, skip_verify=True)  # do not verify HTML, they're faked anyway
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.get('Content-Type'),f"{self.mimetypes[argdict.get('ext','txt')]};charset=utf-8")

    def should_404(self, argdict):
        url = urlreverse(self.view, kwargs=argdict)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    def test_raw_id(self):
        draft = WgDraftFactory(create_revisions=range(0,2))

        dir = settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR
        for r in range(0,2):
            rev = f'{r:02d}'
            (Path(dir) / f'{draft.name}-{rev}.txt').touch()
            if r == 1:
                (Path(dir) / f'{draft.name}-{rev}.html').touch()
                (Path(dir) / f'{draft.name}-{rev}.xml').touch()

        self.should_succeed(dict(name=draft.name))
        for ext in ('txt', 'html', 'xml'):
            self.should_succeed(dict(name=draft.name, ext=ext))
            self.should_succeed(dict(name=draft.name, rev='01', ext=ext))
        self.should_404(dict(name=draft.name, ext='pdf'))

        self.should_succeed(dict(name=draft.name, rev='00'))
        self.should_succeed(dict(name=draft.name, rev='00',ext='txt'))
        self.should_404(dict(name=draft.name, rev='00',ext='html'))

    # test_raw_id_rfc intentionally removed
    # an rfc is no longer a pseudo-version of a draft.

    def test_non_draft(self):
        for doc in [CharterFactory(), WgRfcFactory()]:
            self.should_404(dict(name=doc.name))

class PdfizedTests(TestCase):

    def __init__(self, *args, **kwargs):
        self.view = "ietf.doc.views_doc.document_pdfized"
        super(self.__class__, self).__init__(*args, **kwargs)

    def should_succeed(self, argdict):
        url = urlreverse(self.view, kwargs=argdict)
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.get('Content-Type'),'application/pdf')

    def should_404(self, argdict):
        url = urlreverse(self.view, kwargs=argdict)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    # This takes a _long_ time (32s on a 2022 m1 macbook pro) - is it worth what it covers?
    def test_pdfized(self):
        rfc = WgRfcFactory()
        draft = WgDraftFactory(create_revisions=range(0,2))
        draft.relateddocument_set.create(relationship_id="became_rfc", target=rfc)

        dir = settings.RFC_PATH
        with (Path(dir) / f'{rfc.name}.txt').open('w') as f:
            f.write('text content')
        dir = settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR
        for r in range(0,2):
            with (Path(dir) / f'{draft.name}-{r:02d}.txt').open('w') as f:
                f.write('text content')

        self.assertTrue(
            login_testing_unauthorized(
                self,
                PersonFactory().user.username,
                urlreverse(self.view, kwargs={"name": draft.name}),
            )
        )
        self.should_succeed(dict(name=rfc.name))
        self.should_succeed(dict(name=draft.name))
        for r in range(0,2):
            self.should_succeed(dict(name=draft.name,rev=f'{r:02d}'))
            for ext in ('pdf','txt','html','anythingatall'):
                self.should_succeed(dict(name=draft.name,rev=f'{r:02d}',ext=ext))
        self.should_404(dict(name=draft.name,rev='02'))

        with mock.patch('ietf.doc.models.DocumentInfo.pdfized', side_effect=URLFetchingError):
            url = urlreverse(self.view, kwargs=dict(name=rfc.name))
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, "Error while rendering PDF")

class NotifyValidationTests(TestCase):
    def test_notify_validation(self):
        valid_values = [
            "foo@example.com, bar@example.com",
            "Foo Bar <foobar@example.com>, baz@example.com",
            "foo@example.com, ,bar@example.com,", # We're ignoring extra commas
            "foo@example.com\nbar@example.com", # Yes, we're quietly accepting a newline as a comma
        ]
        bad_nameaddr_values = [
            "@example.com",
            "foo",
            "foo@",
            "foo bar foobar@example.com",
        ]
        duplicate_values = [
            "foo@bar.com, bar@baz.com, foo@bar.com",
            "Foo <foo@bar.com>, foobar <foo@bar.com>",
        ]
        both_duplicate_and_bad_values = [
            "foo@example.com, bar@, Foo <foo@example.com>",
            "Foo <@example.com>, Bar <@example.com>",
        ]
        for v in valid_values:
            self.assertTrue(NotifyForm({"notify": v}).is_valid())
        for v in bad_nameaddr_values:
            f = NotifyForm({"notify": v})
            self.assertFalse(f.is_valid())
            self.assertTrue("Invalid addresses" in f.errors["notify"][0])
            self.assertFalse("Duplicate addresses" in f.errors["notify"][0])
        for v in duplicate_values:
            f = NotifyForm({"notify": v})
            self.assertFalse(f.is_valid())
            self.assertFalse("Invalid addresses" in f.errors["notify"][0])
            self.assertTrue("Duplicate addresses" in f.errors["notify"][0])
        for v in both_duplicate_and_bad_values:
            f = NotifyForm({"notify": v})
            self.assertFalse(f.is_valid())
            self.assertTrue("Invalid addresses" in f.errors["notify"][0])
            self.assertTrue("Duplicate addresses" in f.errors["notify"][0])

class CanRequestConflictReviewTests(TestCase):
    def test_gets_request_conflict_review_action_button(self):
        ise_draft = IndividualDraftFactory(stream_id="ise")
        irtf_draft = RgDraftFactory()

        # This is blunt, trading off precision for time. A more thorough test would ensure
        # that the text is in a button and that the correct link is absent/present as well.

        target_string = "Begin IETF conflict review"

        url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=irtf_draft.name))
        r = self.client.get(url)
        self.assertNotContains(r, target_string)
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertContains(r, target_string)
        self.client.logout()
        self.client.login(username="irtf-chair", password="irtf-chair+password")
        r = self.client.get(url)
        self.assertContains(r, target_string)
        self.client.logout()
        self.client.login(username="ise-chair", password="ise-chair+password")
        r = self.client.get(url)
        self.assertNotContains(r, target_string)
        self.client.logout()

        url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=ise_draft.name))
        r = self.client.get(url)
        self.assertNotContains(r, target_string)
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertContains(r, target_string)
        self.client.logout()
        self.client.login(username="irtf-chair", password="irtf-chair+password")
        r = self.client.get(url)
        self.assertNotContains(r, target_string)
        self.client.logout()
        self.client.login(username="ise-chair", password="ise-chair+password")
        r = self.client.get(url)
        self.assertContains(r, target_string)

class DocInfoMethodsTests(TestCase):

    def test_became_rfc(self):
        draft = WgDraftFactory()
        rfc = WgRfcFactory()
        draft.relateddocument_set.create(relationship_id="became_rfc",target=rfc)
        self.assertEqual(draft.became_rfc(), rfc)
        self.assertEqual(rfc.came_from_draft(), draft)

        charter = CharterFactory()
        self.assertIsNone(charter.became_rfc())
        self.assertIsNone(charter.came_from_draft())

    def test_revisions(self):
        draft = WgDraftFactory(rev="09",create_revisions=range(0,10))
        self.assertEqual(draft.revisions_by_dochistory(),[f"{i:02d}" for i in range(0,10)])
        self.assertEqual(draft.revisions_by_newrevisionevent(),[f"{i:02d}" for i in range(0,10)])
        rfc = WgRfcFactory()
        self.assertEqual(rfc.revisions_by_newrevisionevent(),[])
        self.assertEqual(rfc.revisions_by_dochistory(),[])

        draft.history_set.filter(rev__lt="08").delete()
        draft.docevent_set.filter(newrevisiondocevent__rev="05").delete()
        self.assertEqual(draft.revisions_by_dochistory(),[f"{i:02d}" for i in range(8,10)])
        self.assertEqual(draft.revisions_by_newrevisionevent(),[f"{i:02d}" for i in [*range(0,5), *range(6,10)]])      

    def test_referenced_by_rfcs(self):
        # n.b., no significance to the ref* values in this test
        referring_draft = WgDraftFactory()
        (rfc, referring_rfc) = WgRfcFactory.create_batch(2)
        rfc.targets_related.create(relationship_id="refnorm", source=referring_draft)
        rfc.targets_related.create(relationship_id="refnorm", source=referring_rfc)
        self.assertCountEqual(
            rfc.referenced_by_rfcs(),
            rfc.targets_related.filter(source=referring_rfc),
        )

    def test_referenced_by_rfcs_as_rfc_or_draft(self):
        # n.b., no significance to the ref* values in this test
        draft = WgDraftFactory()
        rfc = WgRfcFactory()
        draft.relateddocument_set.create(relationship_id="became_rfc", target=rfc)
        
        # Draft referring to the rfc and the draft - should not be reported at all
        draft_referring_to_both = WgDraftFactory()
        draft_referring_to_both.relateddocument_set.create(relationship_id="refnorm", target=draft)
        draft_referring_to_both.relateddocument_set.create(relationship_id="refnorm", target=rfc)
        
        # RFC referring only to the draft - should be reported for either the draft or the rfc
        rfc_referring_to_draft = WgRfcFactory()
        rfc_referring_to_draft.relateddocument_set.create(relationship_id="refinfo", target=draft)

        # RFC referring only to the rfc - should be reported only for the rfc
        rfc_referring_to_rfc = WgRfcFactory()
        rfc_referring_to_rfc.relateddocument_set.create(relationship_id="refinfo", target=rfc)

        # RFC referring only to the rfc - should be reported only for the rfc
        rfc_referring_to_rfc = WgRfcFactory()
        rfc_referring_to_rfc.relateddocument_set.create(relationship_id="refinfo", target=rfc)

        # RFC referring to the rfc and the draft - should be reported for both
        rfc_referring_to_both = WgRfcFactory()
        rfc_referring_to_both.relateddocument_set.create(relationship_id="refnorm", target=draft)
        rfc_referring_to_both.relateddocument_set.create(relationship_id="refnorm", target=rfc)

        self.assertCountEqual(
            draft.referenced_by_rfcs_as_rfc_or_draft(),
            draft.targets_related.filter(source__type="rfc"),
        )

        self.assertCountEqual(
            rfc.referenced_by_rfcs_as_rfc_or_draft(),
            draft.targets_related.filter(source__type="rfc") | rfc.targets_related.filter(source__type="rfc"),
        )

class StateIndexTests(TestCase):

    def test_state_index(self):
        url = urlreverse('ietf.doc.views_help.state_index')
        r = self.client.get(url)
        q = PyQuery(r.content)
        content = [ e.text for e in q('#content table td a ') ]
        names = StateType.objects.values_list('slug', flat=True)
        # The following doesn't cover all doc types, only a selection
        for name in names:
            if not '-' in name:
                self.assertIn(name, content)

class InvestigateTests(TestCase):
    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + [
        "AGENDA_PATH",
        # "INTERNET_DRAFT_PATH",
        # "INTERNET_DRAFT_ARCHIVE_DIR",
        # "INTERNET_ALL_DRAFTS_ARCHIVE_DIR",
    ]

    def setUp(self):
        super().setUp()
        # Contort the draft archive dir temporary replacement
        # to match the "collections" concept
        archive_tmp_dir = Path(settings.INTERNET_DRAFT_ARCHIVE_DIR)
        new_archive_dir = archive_tmp_dir / "draft-archive"
        new_archive_dir.mkdir()
        settings.INTERNET_DRAFT_ARCHIVE_DIR = str(new_archive_dir)
        donated_personal_copy_dir = archive_tmp_dir / "donated-personal-copy"
        donated_personal_copy_dir.mkdir()
        meeting_dir = Path(settings.AGENDA_PATH) / "666"
        meeting_dir.mkdir()
        all_archive_dir = Path(settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR)
        repository_dir = Path(settings.INTERNET_DRAFT_PATH)

        for path in [repository_dir, all_archive_dir]:
            (path / "draft-this-is-active-00.txt").touch()
        for path in [new_archive_dir, all_archive_dir]:
            (path / "draft-old-but-can-authenticate-00.txt").touch()
            (path / "draft-has-mixed-provenance-01.txt").touch()
        for path in [donated_personal_copy_dir, all_archive_dir]:
            (path / "draft-donated-from-a-personal-collection-00.txt").touch()
            (path / "draft-has-mixed-provenance-00.txt").touch()
            (path / "draft-has-mixed-provenance-00.txt.Z").touch()
        (all_archive_dir / "draft-this-should-not-be-possible-00.txt").touch()
        (meeting_dir / "draft-this-predates-the-archive-00.txt").touch()

    def test_investigate_fragment(self):

        result = investigate_fragment("this-is-active")
        self.assertEqual(len(result["can_verify"]), 1)
        self.assertEqual(len(result["unverifiable_collections"]), 0)
        self.assertEqual(len(result["unexpected"]), 0)
        self.assertEqual(
            list(result["can_verify"])[0].name, "draft-this-is-active-00.txt"
        )

        result = investigate_fragment("old-but-can")
        self.assertEqual(len(result["can_verify"]), 1)
        self.assertEqual(len(result["unverifiable_collections"]), 0)
        self.assertEqual(len(result["unexpected"]), 0)
        self.assertEqual(
            list(result["can_verify"])[0].name, "draft-old-but-can-authenticate-00.txt"
        )

        result = investigate_fragment("predates")
        self.assertEqual(len(result["can_verify"]), 1)
        self.assertEqual(len(result["unverifiable_collections"]), 0)
        self.assertEqual(len(result["unexpected"]), 0)
        self.assertEqual(
            list(result["can_verify"])[0].name, "draft-this-predates-the-archive-00.txt"
        )

        result = investigate_fragment("personal-collection")
        self.assertEqual(len(result["can_verify"]), 0)
        self.assertEqual(len(result["unverifiable_collections"]), 1)
        self.assertEqual(len(result["unexpected"]), 0)
        self.assertEqual(
            list(result["unverifiable_collections"])[0].name,
            "draft-donated-from-a-personal-collection-00.txt",
        )

        result = investigate_fragment("mixed-provenance")
        self.assertEqual(len(result["can_verify"]), 1)
        self.assertEqual(len(result["unverifiable_collections"]), 2)
        self.assertEqual(len(result["unexpected"]), 0)
        self.assertEqual(
            list(result["can_verify"])[0].name, "draft-has-mixed-provenance-01.txt"
        )
        self.assertEqual(
            set([p.name for p in result["unverifiable_collections"]]),
            set(
                [
                    "draft-has-mixed-provenance-00.txt",
                    "draft-has-mixed-provenance-00.txt.Z",
                ]
            ),
        )

        result = investigate_fragment("not-be-possible")
        self.assertEqual(len(result["can_verify"]), 0)
        self.assertEqual(len(result["unverifiable_collections"]), 0)
        self.assertEqual(len(result["unexpected"]), 1)
        self.assertEqual(
            list(result["unexpected"])[0].name,
            "draft-this-should-not-be-possible-00.txt",
        )

    def test_investigate(self):
        url = urlreverse("ietf.doc.views_doc.investigate")
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("form#investigate")), 1)
        self.assertEqual(len(q("div#results")), 0)
        r = self.client.post(url, dict(name_fragment="this-is-not-found"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("div#results")), 1)
        self.assertEqual(len(q("table#authenticated")), 0)
        self.assertEqual(len(q("table#unverifiable")), 0)
        self.assertEqual(len(q("table#unexpected")), 0)
        r = self.client.post(url, dict(name_fragment="mixed-provenance"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("div#results")), 1)
        self.assertEqual(len(q("table#authenticated")), 1)
        self.assertEqual(len(q("table#unverifiable")), 1)
        self.assertEqual(len(q("table#unexpected")), 0)
        r = self.client.post(url, dict(name_fragment="not-be-possible"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("div#results")), 1)
        self.assertEqual(len(q("table#authenticated")), 0)
        self.assertEqual(len(q("table#unverifiable")), 0)
        self.assertEqual(len(q("table#unexpected")), 1)
        r = self.client.post(url, dict(name_fragment="short"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("#id_name_fragment.is-invalid")), 1)
        for char in ["*", "%", "/", "\\"]:
            r = self.client.post(url, dict(name_fragment=f"bad{char}character"))
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertEqual(len(q("#id_name_fragment.is-invalid")), 1)
