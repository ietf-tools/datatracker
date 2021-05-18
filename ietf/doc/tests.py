# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import os
import shutil
import datetime
import io
import lxml
import bibtexparser
import mock
import json
import copy

from http.cookies import SimpleCookie
from pyquery import PyQuery
from urllib.parse import urlparse, parse_qs
from tempfile import NamedTemporaryFile

from django.core.management import call_command
from django.urls import reverse as urlreverse
from django.conf import settings
from django.forms import Form
from django.utils.html import escape

from tastypie.test import ResourceTestCaseMixin

import debug                            # pyflakes:ignore

from ietf.doc.models import ( Document, DocAlias, DocRelationshipName, RelatedDocument, State,
    DocEvent, BallotPositionDocEvent, LastCallDocEvent, WriteupDocEvent, NewRevisionDocEvent, BallotType,
    EditedAuthorsDocEvent )
from ietf.doc.factories import ( DocumentFactory, DocEventFactory, CharterFactory, 
    ConflictReviewFactory, WgDraftFactory, IndividualDraftFactory, WgRfcFactory, 
    IndividualRfcFactory, StateDocEventFactory, BallotPositionDocEventFactory, 
    BallotDocEventFactory, DocumentAuthorFactory )
from ietf.doc.fields import SearchableDocumentsField
from ietf.doc.utils import create_ballot_if_not_open, uppercase_std_abbreviated_name
from ietf.group.models import Group
from ietf.group.factories import GroupFactory, RoleFactory
from ietf.ipr.factories import HolderIprDisclosureFactory
from ietf.meeting.models import Meeting, Session, SessionPresentation, SchedulingEvent
from ietf.meeting.factories import MeetingFactory, SessionFactory
from ietf.name.models import SessionStatusName, BallotPositionName
from ietf.person.models import Person
from ietf.person.factories import PersonFactory, EmailFactory
from ietf.utils.mail import outbox
from ietf.utils.test_utils import login_testing_unauthorized, unicontent
from ietf.utils.test_utils import TestCase
from ietf.utils.text import normalize_text

class SearchTests(TestCase):
    def test_search(self):

        draft = WgDraftFactory(name='draft-ietf-mars-test',group=GroupFactory(acronym='mars',parent=Group.objects.get(acronym='farfut')),authors=[PersonFactory()],ad=PersonFactory())
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

        # find by rfc/active/inactive
        draft.set_state(State.objects.get(type="draft", slug="rfc"))
        r = self.client.get(base_url + "?rfcs=on&name=%s" % draft.name)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.title)

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

        # prefix match
        r = self.client.get(urlreverse('ietf.doc.views_search.search_for_name', kwargs=dict(name="-".join(draft.name.split("-")[:-1]))))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse(r["Location"]).path, urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))

        # non-prefix match
        r = self.client.get(urlreverse('ietf.doc.views_search.search_for_name', kwargs=dict(name="-".join(draft.name.split("-")[1:]))))
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

    def test_frontpage(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Document Search")

    def test_docs_for_ad(self):
        ad = RoleFactory(name_id='ad',group__type_id='area',group__state_id='active').person
        draft = IndividualDraftFactory(ad=ad)
        draft.action_holders.set([PersonFactory()])
        draft.set_state(State.objects.get(type='draft-iesg', slug='lc'))
        rfc = IndividualDraftFactory(ad=ad)
        rfc.set_state(State.objects.get(type='draft', slug='rfc'))
        DocAlias.objects.create(name='rfc6666').docs.add(rfc)
        conflrev = DocumentFactory(type_id='conflrev',ad=ad)
        conflrev.set_state(State.objects.get(type='conflrev', slug='iesgeval'))
        statchg = DocumentFactory(type_id='statchg',ad=ad)
        statchg.set_state(State.objects.get(type='statchg', slug='iesgeval'))
        charter = CharterFactory(ad=ad)
        charter.set_state(State.objects.get(type='charter', slug='iesgrev'))

        ballot_type = BallotType.objects.get(doc_type_id='draft',slug='approve')
        ballot = BallotDocEventFactory(ballot_type=ballot_type, doc__states=[('draft-iesg','iesg-eva')])
        discuss_pos = BallotPositionName.objects.get(slug='discuss')
        discuss_other = BallotPositionDocEventFactory(ballot=ballot, doc=ballot.doc, balloter=ad, pos=discuss_pos)

        r = self.client.get(urlreverse('ietf.doc.views_search.docs_for_ad', kwargs=dict(name=ad.full_name_as_key())))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.name)
        self.assertContains(r, draft.action_holders.first().plain_name())
        self.assertContains(r, rfc.canonical_name())
        self.assertContains(r, conflrev.name)
        self.assertContains(r, statchg.name)
        self.assertContains(r, charter.name)

        self.assertContains(r, discuss_other.doc.name)

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
        self.assertContains(r, draft.action_holders.first().plain_name())

    def test_in_iesg_process(self):
        doc_in_process = IndividualDraftFactory()
        doc_in_process.action_holders.set([PersonFactory()])
        doc_in_process.set_state(State.objects.get(type='draft-iesg', slug='lc'))
        doc_not_in_process = IndividualDraftFactory()
        r = self.client.get(urlreverse('ietf.doc.views_search.drafts_in_iesg_process'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, doc_in_process.title)
        self.assertContains(r, doc_in_process.action_holders.first().plain_name())
        self.assertNotContains(r, doc_not_in_process.title)
        
    def test_indexes(self):
        draft = IndividualDraftFactory()
        rfc = WgRfcFactory()

        r = self.client.get(urlreverse('ietf.doc.views_search.index_all_drafts'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.name)
        self.assertContains(r, rfc.canonical_name().upper())

        r = self.client.get(urlreverse('ietf.doc.views_search.index_active_drafts'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.title)

    def test_ajax_search_docs(self):
        draft = IndividualDraftFactory()

        # Document
        url = urlreverse('ietf.doc.views_search.ajax_select2_search_docs', kwargs={
            "model_name": "document",
            "doc_type": "draft",
        })
        r = self.client.get(url, dict(q=draft.name))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data[0]["id"], draft.pk)

        # DocAlias
        doc_alias = draft.docalias.first()

        url = urlreverse('ietf.doc.views_search.ajax_select2_search_docs', kwargs={
            "model_name": "docalias",
            "doc_type": "draft",
        })

        r = self.client.get(url, dict(q=doc_alias.name))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data[0]["id"], doc_alias.pk)

    def test_recent_drafts(self):
        # Three drafts to show with various warnings
        drafts = WgDraftFactory.create_batch(3,states=[('draft','active'),('draft-iesg','ad-eval')])
        for index, draft in enumerate(drafts):
            StateDocEventFactory(doc=draft, state=('draft-iesg','ad-eval'), time=datetime.datetime.now()-datetime.timedelta(days=[1,15,29][index]))
            draft.action_holders.set([PersonFactory()])

        # And one draft that should not show (with the default of 7 days to view)
        old = WgDraftFactory()
        old.docevent_set.filter(newrevisiondocevent__isnull=False).update(time=datetime.datetime.now()-datetime.timedelta(days=8))
        StateDocEventFactory(doc=old, time=datetime.datetime.now()-datetime.timedelta(days=8))

        url = urlreverse('ietf.doc.views_search.recent_drafts')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('td.doc')),3)
        self.assertEqual(q('td.status span.label-warning').text(),"for 15 days")
        self.assertEqual(q('td.status span.label-danger').text(),"for 29 days")
        for ah in [draft.action_holders.first() for draft in drafts]:
            self.assertContains(r, ah.plain_name())

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
   methods used in Earth do not directly translate to the efficent
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
        self.id_dir = self.tempdir('id')
        self.saved_internet_draft_path = settings.INTERNET_DRAFT_PATH
        settings.INTERNET_DRAFT_PATH = self.id_dir
        self.saved_internet_all_drafts_archive_dir = settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR
        settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR = self.id_dir
        f = io.open(os.path.join(self.id_dir, 'draft-ietf-mars-test-01.txt'), 'w')
        f.write(self.draft_text)
        f.close()

    def tearDown(self):
        settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR = self.saved_internet_all_drafts_archive_dir
        settings.INTERNET_DRAFT_PATH = self.saved_internet_draft_path
        shutil.rmtree(self.id_dir)

    def test_document_draft(self):
        draft = WgDraftFactory(name='draft-ietf-mars-test',rev='01')
        HolderIprDisclosureFactory(docs=[draft])
        
        # Docs for testing relationships. Does not test 'possibly-replaces'. The 'replaced_by' direction
        # is tested separately below.
        replaced = IndividualDraftFactory()
        draft.relateddocument_set.create(relationship_id='replaces',source=draft,target=replaced.docalias.first())
        obsoleted = IndividualDraftFactory()
        draft.relateddocument_set.create(relationship_id='obs',source=draft,target=obsoleted.docalias.first())
        obsoleted_by = IndividualDraftFactory()
        obsoleted_by.relateddocument_set.create(relationship_id='obs',source=obsoleted_by,target=draft.docalias.first())
        updated = IndividualDraftFactory()
        draft.relateddocument_set.create(relationship_id='updates',source=draft,target=updated.docalias.first())
        updated_by = IndividualDraftFactory()
        updated_by.relateddocument_set.create(relationship_id='updates',source=obsoleted_by,target=draft.docalias.first())

        # these tests aren't testing all attributes yet, feel free to
        # expand them

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Active Internet-Draft")
        if settings.USER_PREFERENCE_DEFAULTS['full_draft'] == 'off':
            self.assertContains(r, "Show full document text")
            self.assertNotContains(r, "Deimos street")
        self.assertContains(r, replaced.canonical_name())
        self.assertContains(r, replaced.title)
        # obs/updates not included until draft is RFC
        self.assertNotContains(r, obsoleted.canonical_name())
        self.assertNotContains(r, obsoleted.title)
        self.assertNotContains(r, obsoleted_by.canonical_name())
        self.assertNotContains(r, obsoleted_by.title)
        self.assertNotContains(r, updated.canonical_name())
        self.assertNotContains(r, updated.title)
        self.assertNotContains(r, updated_by.canonical_name())
        self.assertNotContains(r, updated_by.title)

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)) + "?include_text=0")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Active Internet-Draft")
        self.assertContains(r, "Show full document text")
        self.assertNotContains(r, "Deimos street")
        self.assertContains(r, replaced.canonical_name())
        self.assertContains(r, replaced.title)
        # obs/updates not included until draft is RFC
        self.assertNotContains(r, obsoleted.canonical_name())
        self.assertNotContains(r, obsoleted.title)
        self.assertNotContains(r, obsoleted_by.canonical_name())
        self.assertNotContains(r, obsoleted_by.title)
        self.assertNotContains(r, updated.canonical_name())
        self.assertNotContains(r, updated.title)
        self.assertNotContains(r, updated_by.canonical_name())
        self.assertNotContains(r, updated_by.title)

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)) + "?include_text=foo")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Active Internet-Draft")
        self.assertNotContains(r, "Show full document text")
        self.assertContains(r, "Deimos street")
        self.assertContains(r, replaced.canonical_name())
        self.assertContains(r, replaced.title)
        # obs/updates not included until draft is RFC
        self.assertNotContains(r, obsoleted.canonical_name())
        self.assertNotContains(r, obsoleted.title)
        self.assertNotContains(r, obsoleted_by.canonical_name())
        self.assertNotContains(r, obsoleted_by.title)
        self.assertNotContains(r, updated.canonical_name())
        self.assertNotContains(r, updated.title)
        self.assertNotContains(r, updated_by.canonical_name())
        self.assertNotContains(r, updated_by.title)

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)) + "?include_text=1")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Active Internet-Draft")
        self.assertNotContains(r, "Show full document text")
        self.assertContains(r, "Deimos street")
        self.assertContains(r, replaced.canonical_name())
        self.assertContains(r, replaced.title)
        # obs/updates not included until draft is RFC
        self.assertNotContains(r, obsoleted.canonical_name())
        self.assertNotContains(r, obsoleted.title)
        self.assertNotContains(r, obsoleted_by.canonical_name())
        self.assertNotContains(r, obsoleted_by.title)
        self.assertNotContains(r, updated.canonical_name())
        self.assertNotContains(r, updated.title)
        self.assertNotContains(r, updated_by.canonical_name())
        self.assertNotContains(r, updated_by.title)

        self.client.cookies = SimpleCookie({str('full_draft'): str('on')})
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Active Internet-Draft")
        self.assertNotContains(r, "Show full document text")
        self.assertContains(r, "Deimos street")
        self.assertContains(r, replaced.canonical_name())
        self.assertContains(r, replaced.title)
        # obs/updates not included until draft is RFC
        self.assertNotContains(r, obsoleted.canonical_name())
        self.assertNotContains(r, obsoleted.title)
        self.assertNotContains(r, obsoleted_by.canonical_name())
        self.assertNotContains(r, obsoleted_by.title)
        self.assertNotContains(r, updated.canonical_name())
        self.assertNotContains(r, updated.title)
        self.assertNotContains(r, updated_by.canonical_name())
        self.assertNotContains(r, updated_by.title)

        self.client.cookies = SimpleCookie({str('full_draft'): str('off')})
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Active Internet-Draft")
        self.assertContains(r, "Show full document text")
        self.assertNotContains(r, "Deimos street")
        self.assertContains(r, replaced.canonical_name())
        self.assertContains(r, replaced.title)
        # obs/updates not included until draft is RFC
        self.assertNotContains(r, obsoleted.canonical_name())
        self.assertNotContains(r, obsoleted.title)
        self.assertNotContains(r, obsoleted_by.canonical_name())
        self.assertNotContains(r, obsoleted_by.title)
        self.assertNotContains(r, updated.canonical_name())
        self.assertNotContains(r, updated.title)
        self.assertNotContains(r, updated_by.canonical_name())
        self.assertNotContains(r, updated_by.title)

        self.client.cookies = SimpleCookie({str('full_draft'): str('foo')})
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Active Internet-Draft")
        if settings.USER_PREFERENCE_DEFAULTS['full_draft'] == 'off':
            self.assertContains(r, "Show full document text")
            self.assertNotContains(r, "Deimos street")
        self.assertContains(r, replaced.canonical_name())
        self.assertContains(r, replaced.title)
        # obs/updates not included until draft is RFC
        self.assertNotContains(r, obsoleted.canonical_name())
        self.assertNotContains(r, obsoleted.title)
        self.assertNotContains(r, obsoleted_by.canonical_name())
        self.assertNotContains(r, obsoleted_by.title)
        self.assertNotContains(r, updated.canonical_name())
        self.assertNotContains(r, updated.title)
        self.assertNotContains(r, updated_by.canonical_name())
        self.assertNotContains(r, updated_by.title)

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_html", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Versions:")
        self.assertContains(r, "Deimos street")
        q = PyQuery(r.content)
        self.assertEqual(len(q('.rfcmarkup pre')), 4)
        self.assertEqual(len(q('.rfcmarkup span.h1')), 2)
        self.assertEqual(len(q('.rfcmarkup a[href]')), 41)

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_html", kwargs=dict(name=draft.name, rev=draft.rev)))
        self.assertEqual(r.status_code, 200)

        # expired draft
        draft.set_state(State.objects.get(type="draft", slug="expired"))

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Expired Internet-Draft")

        # replaced draft
        draft.set_state(State.objects.get(type="draft", slug="repl"))

        replacement = WgDraftFactory(
            name="draft-ietf-replacement",
            time=datetime.datetime.now(),
            title="Replacement Draft",
            stream_id=draft.stream_id, group_id=draft.group_id, abstract=draft.abstract,stream=draft.stream, rev=draft.rev,
            pages=draft.pages, intended_std_level_id=draft.intended_std_level_id,
            shepherd_id=draft.shepherd_id, ad_id=draft.ad_id, expires=draft.expires,
            notify=draft.notify, note=draft.note)
        rel = RelatedDocument.objects.create(source=replacement,
                                             target=draft.docalias.get(name__startswith="draft"),
                                             relationship_id="replaces")

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Replaced Internet-Draft")
        self.assertContains(r, replacement.canonical_name())
        self.assertContains(r, replacement.title)
        rel.delete()

        # draft published as RFC
        draft.set_state(State.objects.get(type="draft", slug="rfc"))
        draft.std_level_id = "bcp"
        draft.save_with_history([DocEvent.objects.create(doc=draft, rev=draft.rev, type="published_rfc", by=Person.objects.get(name="(System)"))])


        rfc_alias = DocAlias.objects.create(name="rfc123456")
        rfc_alias.docs.add(draft)
        bcp_alias = DocAlias.objects.create(name="bcp123456")
        bcp_alias.docs.add(draft)

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 302)
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=bcp_alias.name)))
        self.assertEqual(r.status_code, 302)

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=rfc_alias.name)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "RFC 123456")
        self.assertContains(r, draft.name)
        self.assertContains(r, replaced.canonical_name())
        self.assertContains(r, replaced.title)
        # obs/updates included with RFC
        self.assertContains(r, obsoleted.canonical_name())
        self.assertContains(r, obsoleted.title)
        self.assertContains(r, obsoleted_by.canonical_name())
        self.assertContains(r, obsoleted_by.title)
        self.assertContains(r, updated.canonical_name())
        self.assertContains(r, updated.title)
        self.assertContains(r, updated_by.canonical_name())
        self.assertContains(r, updated_by.title)

        # naked RFC - also wierd that we test a PS from the ISE
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
        
        new_email = EmailFactory(person=draft.authors()[0])
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
        # selector grabs the action holders heading and finds siblings with a div containing the search string
        return q('th:contains("Action Holders") ~ td>div:contains("%s")' % s)

    @mock.patch.object(Document, 'action_holders_enabled', return_value=False, new_callable=mock.PropertyMock)
    def test_document_draft_hides_action_holders(self, mock_method):
        """Draft should not show action holders when appropriate"""
        draft = WgDraftFactory()
        url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name))
        r = self.client.get(url)
        self.assertNotContains(r, 'Action Holders')  # should not show action holders...

        draft.action_holders.set([PersonFactory()])
        r = self.client.get(url)
        self.assertNotContains(r, 'Action Holders')  # ...even if they are assigned

    @mock.patch.object(Document, 'action_holders_enabled', return_value=True, new_callable=mock.PropertyMock)
    def test_document_draft_shows_action_holders(self, mock_method):
        """Draft should show action holders when appropriate"""
        draft = WgDraftFactory()
        url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name))

        # No action holders case should be shown properly
        r = self.client.get(url)
        self.assertContains(r, 'Action Holders')  # should show action holders
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

        self.assertContains(r, 'Action Holders')  # should still be shown
        q = PyQuery(r.content)
        self.assertEqual(len(self._pyquery_select_action_holder_string(q, '(None)')), 0)
        for person in draft.action_holders.all():
            self.assertEqual(len(self._pyquery_select_action_holder_string(q, person.plain_name())), 1)
        # check that one action holder was marked as old
        self.assertEqual(len(self._pyquery_select_action_holder_string(q, 'for 30 days')), 1)

    @mock.patch.object(Document, 'action_holders_enabled', return_value=True, new_callable=mock.PropertyMock)
    def test_document_draft_action_holders_buttons(self, mock_method):
        """Buttons for action holders should be shown when AD or secretary"""
        draft = WgDraftFactory()
        draft.action_holders.set([PersonFactory()])

        url = urlreverse('ietf.doc.views_doc.document_main', kwargs=dict(name=draft.name))
        edit_ah_url = urlreverse('ietf.doc.views_doc.edit_action_holders', kwargs=dict(name=draft.name))
        remind_ah_url = urlreverse('ietf.doc.views_doc.remind_action_holders', kwargs=dict(name=draft.name))

        def _run_test(username=None, expect_buttons=False):
            if username:
                self.client.login(username=username, password=username + '+password')
            r = self.client.get(url)
            q = PyQuery(r.content)

            self.assertEqual(
                len(q('th:contains("Action Holders") ~ td a[href="%s"]' % edit_ah_url)),
                1 if expect_buttons else 0,
                '%s should%s see the edit action holders button but %s' % (
                    username if username else 'unauthenticated user',
                    '' if expect_buttons else ' not',
                    'did not' if expect_buttons else 'did',
                )
            )
            self.assertEqual(
                len(q('th:contains("Action Holders") ~ td a[href="%s"]' % remind_ah_url)),
                1 if expect_buttons else 0,
                '%s should%s see the remind action holders button but %s' % (
                    username if username else 'unauthenticated user',
                    '' if expect_buttons else ' not',
                    'did not' if expect_buttons else 'did',
                )
            )

        _run_test(None, False)
        _run_test('plain', False)
        _run_test('ad', True)
        _run_test('secretary', True)

    def test_draft_group_link(self):
        """Link to group 'about' page should have correct format"""
        for group_type_id in ['wg', 'rg', 'ag']:
            group = GroupFactory(type_id=group_type_id)
            draft = WgDraftFactory(name='draft-document-%s' % group_type_id, group=group)
            r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))
            self.assertEqual(r.status_code, 200)
            self.assert_correct_wg_group_link(r, group)

            rfc = WgRfcFactory(name='draft-rfc-document-%s' % group_type_id, group=group)
            DocEventFactory.create(doc=rfc, type='published_rfc', time = '2010-10-10')
            # get the rfc name to avoid a redirect
            rfc_name = rfc.docalias.filter(name__startswith='rfc').first().name
            r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=rfc_name)))
            self.assertEqual(r.status_code, 200)
            self.assert_correct_wg_group_link(r, group)

        for group_type_id in ['ietf', 'team']:
            group = GroupFactory(type_id=group_type_id)
            draft = WgDraftFactory(name='draft-document-%s' % group_type_id, group=group)
            r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)))
            self.assertEqual(r.status_code, 200)
            self.assert_correct_non_wg_group_link(r, group)

            rfc = WgRfcFactory(name='draft-rfc-document-%s' % group_type_id, group=group)
            DocEventFactory.create(doc=rfc, type='published_rfc', time = '2010-10-10')
            # get the rfc name to avoid a redirect
            rfc_name = rfc.docalias.filter(name__startswith='rfc').first().name
            r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=rfc_name)))
            self.assertEqual(r.status_code, 200)
            self.assert_correct_non_wg_group_link(r, group)

    def test_document_primary_and_history_views(self):
        IndividualDraftFactory(name='draft-imaginary-independent-submission')
        ConflictReviewFactory(name='conflict-review-imaginary-irtf-submission')
        CharterFactory(name='charter-ietf-mars')
        DocumentFactory(type_id='agenda',name='agenda-72-mars')
        DocumentFactory(type_id='minutes',name='minutes-72-mars')
        DocumentFactory(type_id='slides',name='slides-72-mars-1-active')
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
    def test_document_charter(self):
        CharterFactory(name='charter-ietf-mars')
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name="charter-ietf-mars")))
        self.assertEqual(r.status_code, 200)

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

        session = Session.objects.create(
            name = "session-72-mars-1",
            meeting = Meeting.objects.get(number='72'),
            group = Group.objects.get(acronym='mars'),
            modified = datetime.datetime.now(),
            type_id = 'regular',
        )
        SchedulingEvent.objects.create(
            session=session,
            status=SessionStatusName.objects.create(slug='scheduled'),
            by = Person.objects.get(user__username="marschairman"),
        )
        SessionPresentation.objects.create(session=session, document=doc, rev=doc.rev)

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)

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
            comment_time=datetime.datetime.now(),
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
        self.assertContains(r,  '(%s for -%s)' % (pos.comment_time.strftime('%Y-%m-%d'), oldrev))
        
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
        DocAlias.objects.create(name='rfc9998').docs.add(IndividualDraftFactory())
        DocAlias.objects.create(name='rfc9999').docs.add(IndividualDraftFactory())
        doc = DocumentFactory(type_id='statchg',name='status-change-imaginary-mid-review')
        iesgeval_pk = str(State.objects.get(slug='iesgeval',type__slug='statchg').pk)
        self.client.login(username='ad', password='ad+password')
        r = self.client.post(urlreverse('ietf.doc.views_status_change.change_state',kwargs=dict(name=doc.name)),dict(new_state=iesgeval_pk))
        self.assertEqual(r.status_code, 302)
        r = self.client.get(r._headers["location"][1])
        self.assertContains(r, ">IESG Evaluation<")

        doc.relateddocument_set.create(target=DocAlias.objects.get(name='rfc9998'),relationship_id='tohist')
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name)))
        self.assertNotContains(r, 'Needs a YES')
        self.assertNotContains(r, 'more YES or NO')

        doc.relateddocument_set.create(target=DocAlias.objects.get(name='rfc9999'),relationship_id='tois')
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
        rfcname='rfc9090'
        rfc = WgRfcFactory(alias2=rfcname)
        bis_draft = WgDraftFactory(name='draft-ietf-{}-{}bis'.format(rfc.group.acronym,rfcname))

        url = urlreverse('ietf.doc.views_doc.document_history', kwargs=dict(name=bis_draft.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200) 
        q = PyQuery(unicontent(r))
        attr1='value="{}"'.format(rfcname)
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

    def test_last_call_feed(self):
        doc = IndividualDraftFactory()

        doc.set_state(State.objects.get(type="draft-iesg", slug="lc"))

        LastCallDocEvent.objects.create(
            doc=doc,
            rev=doc.rev,
            desc="Last call",
            type="sent_last_call",
            by=Person.objects.get(user__username="secretary"),
            expires=datetime.date.today() + datetime.timedelta(days=7))

        r = self.client.get("/feed/last-call/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, doc.name)

    def test_rfc_feed(self):
        WgRfcFactory()
        r = self.client.get("/feed/rfc/")
        self.assertTrue(r.status_code, 200)
        r = self.client.get("/feed/rfc/2016")
        self.assertTrue(r.status_code, 200)

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

    def test_document_bibtex(self):
        rfc = WgRfcFactory.create(
                  #other_aliases = ['rfc6020',],
                  states = [('draft','rfc'),('draft-iesg','pub')],
                  std_level_id = 'ps',
                  time = datetime.datetime(2010,10,10),
              )
        num = rfc.rfc_number()
        DocEventFactory.create(doc=rfc, type='published_rfc', time = '2010-10-10')
        #
        url = urlreverse('ietf.doc.views_doc.document_bibtex', kwargs=dict(name=rfc.name))
        r = self.client.get(url)
        entry = bibtexparser.loads(unicontent(r)).get_entry_dict()["rfc%s"%num]
        self.assertEqual(entry['series'],   'Request for Comments')
        self.assertEqual(entry['number'],   num)
        self.assertEqual(entry['doi'],      '10.17487/RFC%s'%num)
        self.assertEqual(entry['year'],     '2010')
        self.assertEqual(entry['month'],    'oct')
        #
        self.assertNotIn('day', entry)

        april1 = IndividualRfcFactory.create(
                  stream_id =       'ise',
                  states =          [('draft','rfc'),('draft-iesg','pub')],
                  std_level_id =    'inf',
                  time =            datetime.datetime(1990,0o4,0o1),
              )
        num = april1.rfc_number()
        DocEventFactory.create(doc=april1, type='published_rfc', time = '1990-04-01')
        #
        url = urlreverse('ietf.doc.views_doc.document_bibtex', kwargs=dict(name=april1.name))
        r = self.client.get(url)
        self.assertEqual(r.get('Content-Type'), 'text/plain; charset=utf-8')
        entry = bibtexparser.loads(unicontent(r)).get_entry_dict()['rfc%s'%num]
        self.assertEqual(entry['series'],   'Request for Comments')
        self.assertEqual(entry['number'],   num)
        self.assertEqual(entry['doi'],      '10.17487/RFC%s'%num)
        self.assertEqual(entry['year'],     '1990')
        self.assertEqual(entry['month'],    'apr')
        self.assertEqual(entry['day'],      '1')

        draft = IndividualDraftFactory.create()
        docname = '%s-%s' % (draft.name, draft.rev)
        bibname = docname[6:]           # drop the 'draft-' prefix
        url = urlreverse('ietf.doc.views_doc.document_bibtex', kwargs=dict(name=draft.name))
        r = self.client.get(url)
        entry = bibtexparser.loads(unicontent(r)).get_entry_dict()[bibname]
        self.assertEqual(entry['note'],     'Work in Progress')
        self.assertEqual(entry['number'],   docname)
        self.assertEqual(entry['year'],     str(draft.pub_date().year))
        self.assertEqual(entry['month'],    draft.pub_date().strftime('%b').lower())
        self.assertEqual(entry['day'],      str(draft.pub_date().day))
        #
        self.assertNotIn('doi', entry)

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
        doc2 = IndividualDraftFactory(name='draft-imaginary-independent-submission').docalias.first()
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
   def setUp(self):
       self.doc_aliases_file = NamedTemporaryFile(delete=False, mode='w+')
       self.doc_aliases_file.close()
       self.doc_virtual_file = NamedTemporaryFile(delete=False, mode='w+')
       self.doc_virtual_file.close()
       self.saved_draft_aliases_path = settings.DRAFT_ALIASES_PATH
       self.saved_draft_virtual_path = settings.DRAFT_VIRTUAL_PATH
       settings.DRAFT_ALIASES_PATH = self.doc_aliases_file.name
       settings.DRAFT_VIRTUAL_PATH = self.doc_virtual_file.name

   def tearDown(self):
       settings.DRAFT_ALIASES_PATH = self.saved_draft_aliases_path
       settings.DRAFT_VIRTUAL_PATH = self.saved_draft_virtual_path
       os.unlink(self.doc_aliases_file.name)
       os.unlink(self.doc_virtual_file.name)

   def testManagementCommand(self):
       a_month_ago = datetime.datetime.now() - datetime.timedelta(30)
       ad = RoleFactory(name_id='ad', group__type_id='area', group__state_id='active').person
       shepherd = PersonFactory()
       author1 = PersonFactory()
       author2 = PersonFactory()
       author3 = PersonFactory()
       author4 = PersonFactory()
       author5 = PersonFactory()
       author6 = PersonFactory()
       mars = GroupFactory(type_id='wg', acronym='mars')
       marschairman = PersonFactory(user__username='marschairman')
       mars.role_set.create(name_id='chair', person=marschairman, email=marschairman.email())
       doc1 = IndividualDraftFactory(authors=[author1], shepherd=shepherd.email(), ad=ad)
       doc2 = WgDraftFactory(name='draft-ietf-mars-test', group__acronym='mars', authors=[author2], ad=ad)
       doc3 = WgRfcFactory.create(name='draft-ietf-mars-finished', group__acronym='mars', authors=[author3], ad=ad, std_level_id='ps', states=[('draft','rfc'),('draft-iesg','pub')], time=a_month_ago)
       DocEventFactory.create(doc=doc3, type='published_rfc', time=a_month_ago.strftime("%Y-%m-%d"))
       doc4 = WgRfcFactory.create(authors=[author4,author5], ad=ad, std_level_id='ps', states=[('draft','rfc'),('draft-iesg','pub')], time=datetime.datetime(2010,10,10))
       DocEventFactory.create(doc=doc4, type='published_rfc', time = '2010-10-10')
       doc5 = IndividualDraftFactory(authors=[author6])

       args = [ ]
       kwargs = { }
       out = io.StringIO()
       call_command("generate_draft_aliases", *args, **kwargs, stdout=out, stderr=out)
       self.assertFalse(out.getvalue())

       with open(settings.DRAFT_ALIASES_PATH) as afile:
           acontent = afile.read()
           self.assertTrue(all([x in acontent for x in [
               'xfilter-' + doc1.name,
               'xfilter-' + doc1.name + '.ad',
               'xfilter-' + doc1.name + '.authors',
               'xfilter-' + doc1.name + '.shepherd',
               'xfilter-' + doc1.name + '.all',
               'xfilter-' + doc2.name,
               'xfilter-' + doc2.name + '.ad',
               'xfilter-' + doc2.name + '.authors',
               'xfilter-' + doc2.name + '.chairs',
               'xfilter-' + doc2.name + '.all',
               'xfilter-' + doc3.name,
               'xfilter-' + doc3.name + '.ad',
               'xfilter-' + doc3.name + '.authors',
               'xfilter-' + doc3.name + '.chairs',
               'xfilter-' + doc5.name,
               'xfilter-' + doc5.name + '.authors',
               'xfilter-' + doc5.name + '.all',
           ]]))
           self.assertFalse(all([x in acontent for x in [
               'xfilter-' + doc1.name + '.chairs',
               'xfilter-' + doc2.name + '.shepherd',
               'xfilter-' + doc3.name + '.shepherd',
               'xfilter-' + doc4.name,
               'xfilter-' + doc5.name + '.shepherd',
               'xfilter-' + doc5.name + '.ad',
           ]]))

       with open(settings.DRAFT_VIRTUAL_PATH) as vfile:
           vcontent = vfile.read()
           self.assertTrue(all([x in vcontent for x in [
               ad.email_address(),
               shepherd.email_address(),
               marschairman.email_address(),
               author1.email_address(),
               author2.email_address(),
               author3.email_address(),
               author6.email_address(),
           ]]))
           self.assertFalse(all([x in vcontent for x in [
               author4.email_address(),
               author5.email_address(),
           ]]))
           self.assertTrue(all([x in vcontent for x in [
               'xfilter-' + doc1.name,
               'xfilter-' + doc1.name + '.ad',
               'xfilter-' + doc1.name + '.authors',
               'xfilter-' + doc1.name + '.shepherd',
               'xfilter-' + doc1.name + '.all',
               'xfilter-' + doc2.name,
               'xfilter-' + doc2.name + '.ad',
               'xfilter-' + doc2.name + '.authors',
               'xfilter-' + doc2.name + '.chairs',
               'xfilter-' + doc2.name + '.all',
               'xfilter-' + doc3.name,
               'xfilter-' + doc3.name + '.ad',
               'xfilter-' + doc3.name + '.authors',
               'xfilter-' + doc3.name + '.chairs',
               'xfilter-' + doc5.name,
               'xfilter-' + doc5.name + '.authors',
               'xfilter-' + doc5.name + '.all',
           ]]))
           self.assertFalse(all([x in vcontent for x in [
               'xfilter-' + doc1.name + '.chairs',
               'xfilter-' + doc2.name + '.shepherd',
               'xfilter-' + doc3.name + '.shepherd',
               'xfilter-' + doc4.name,
               'xfilter-' + doc5.name + '.shepherd',
               'xfilter-' + doc5.name + '.ad',
           ]]))

class EmailAliasesTests(TestCase):

    def setUp(self):
        WgDraftFactory(name='draft-ietf-mars-test',group__acronym='mars')
        WgDraftFactory(name='draft-ietf-ames-test',group__acronym='ames')
        RoleFactory(group__type_id='review', group__acronym='yangdoctors', name_id='secr')
        self.doc_alias_file = NamedTemporaryFile(delete=False, mode='w+')
        self.doc_alias_file.write("""# Generated by hand at 2015-02-12_16:26:45
virtual.ietf.org anything
draft-ietf-mars-test@ietf.org              xfilter-draft-ietf-mars-test
expand-draft-ietf-mars-test@virtual.ietf.org  mars-author@example.com, mars-collaborator@example.com
draft-ietf-mars-test.authors@ietf.org      xfilter-draft-ietf-mars-test.authors
expand-draft-ietf-mars-test.authors@virtual.ietf.org  mars-author@example.mars, mars-collaborator@example.mars
draft-ietf-mars-test.chairs@ietf.org      xfilter-draft-ietf-mars-test.chairs
expand-draft-ietf-mars-test.chairs@virtual.ietf.org  mars-chair@example.mars
draft-ietf-mars-test.all@ietf.org      xfilter-draft-ietf-mars-test.all
expand-draft-ietf-mars-test.all@virtual.ietf.org  mars-author@example.mars, mars-collaborator@example.mars, mars-chair@example.mars
draft-ietf-ames-test@ietf.org              xfilter-draft-ietf-ames-test
expand-draft-ietf-ames-test@virtual.ietf.org  ames-author@example.com, ames-collaborator@example.com
draft-ietf-ames-test.authors@ietf.org      xfilter-draft-ietf-ames-test.authors
expand-draft-ietf-ames-test.authors@virtual.ietf.org  ames-author@example.ames, ames-collaborator@example.ames
draft-ietf-ames-test.chairs@ietf.org      xfilter-draft-ietf-ames-test.chairs
expand-draft-ietf-ames-test.chairs@virtual.ietf.org  ames-chair@example.ames
draft-ietf-ames-test.all@ietf.org      xfilter-draft-ietf-ames-test.all
expand-draft-ietf-ames-test.all@virtual.ietf.org  ames-author@example.ames, ames-collaborator@example.ames, ames-chair@example.ames

""")
        self.doc_alias_file.close()
        self.saved_draft_virtual_path = settings.DRAFT_VIRTUAL_PATH
        settings.DRAFT_VIRTUAL_PATH = self.doc_alias_file.name

    def tearDown(self):
        settings.DRAFT_VIRTUAL_PATH = self.saved_draft_virtual_path
        os.unlink(self.doc_alias_file.name)

    def testAliases(self):
        PersonFactory(user__username='plain')
        url = urlreverse('ietf.doc.urls.redirect.document_email', kwargs=dict(name="draft-ietf-mars-test"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)

        url = urlreverse('ietf.doc.views_doc.email_aliases', kwargs=dict())
        login_testing_unauthorized(self, "plain", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(all([x in unicontent(r) for x in ['mars-test@','mars-test.authors@','mars-test.chairs@']]))
        self.assertTrue(all([x in unicontent(r) for x in ['ames-test@','ames-test.authors@','ames-test.chairs@']]))

    def testExpansions(self):
        url = urlreverse('ietf.doc.views_doc.document_email', kwargs=dict(name="draft-ietf-mars-test"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'draft-ietf-mars-test.all@ietf.org')
        self.assertContains(r, 'iesg_ballot_saved')

class DocumentMeetingTests(TestCase):

    def setUp(self):
        self.group = GroupFactory(type_id='wg',state_id='active')
        self.group_chair = PersonFactory()
        self.group.role_set.create(name_id='chair',person=self.group_chair,email=self.group_chair.email())

        self.other_group = GroupFactory(type_id='wg',state_id='active')
        self.other_chair = PersonFactory()
        self.other_group.role_set.create(name_id='chair',person=self.other_chair,email=self.other_chair.email())

        today = datetime.date.today()
        cut_days = settings.MEETING_MATERIALS_DEFAULT_SUBMISSION_CORRECTION_DAYS
        self.past_cutoff = SessionFactory.create(meeting__type_id='ietf',group=self.group,meeting__date=today-datetime.timedelta(days=1+cut_days))
        self.past = SessionFactory.create(meeting__type_id='ietf',group=self.group,meeting__date=today-datetime.timedelta(days=cut_days/2))
        self.inprog = SessionFactory.create(meeting__type_id='ietf',group=self.group,meeting__date=today-datetime.timedelta(days=1))
        self.future = SessionFactory.create(meeting__type_id='ietf',group=self.group,meeting__date=today+datetime.timedelta(days=90))
        self.interim = SessionFactory.create(meeting__type_id='interim',group=self.group,meeting__date=today+datetime.timedelta(days=45))

    def test_view_document_meetings(self):
        doc = IndividualDraftFactory.create()
        doc.sessionpresentation_set.create(session=self.inprog,rev=None)
        doc.sessionpresentation_set.create(session=self.interim,rev=None)

        url = urlreverse('ietf.doc.views_doc.all_presentations', kwargs=dict(name=doc.name))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertTrue(all([q(id) for id in ['#inprogressmeets','#futuremeets']]))
        self.assertFalse(any([q(id) for id in ['#pastmeets',]]))
        self.assertFalse(q('#addsessionsbutton'))
        self.assertFalse(q("a.btn:contains('Remove document')"))

        doc.sessionpresentation_set.create(session=self.past_cutoff,rev=None)
        doc.sessionpresentation_set.create(session=self.past,rev=None)

        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertTrue(q('#addsessionsbutton'))
        self.assertEqual(1,len(q("#inprogressmeets a.btn-default:contains('Remove document')")))
        self.assertEqual(1,len(q("#futuremeets a.btn-default:contains('Remove document')")))
        self.assertEqual(1,len(q("#pastmeets a.btn-default:contains('Remove document')")))
        self.assertEqual(1,len(q("#pastmeets a.btn-warning:contains('Remove document')")))

        self.client.login(username=self.group_chair.user.username,password='%s+password'%self.group_chair.user.username)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertTrue(q('#addsessionsbutton'))
        self.assertEqual(1,len(q("#inprogressmeets a.btn-default:contains('Remove document')")))
        self.assertEqual(1,len(q("#futuremeets a.btn-default:contains('Remove document')")))
        self.assertEqual(1,len(q("#pastmeets a.btn-default:contains('Remove document')")))
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

    def test_edit_document_session(self):
        doc = IndividualDraftFactory.create()
        sp = doc.sessionpresentation_set.create(session=self.future,rev=None)

        url = urlreverse('ietf.doc.views_doc.edit_sessionpresentation',kwargs=dict(name='no-such-doc',session_id=sp.session_id))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

        url = urlreverse('ietf.doc.views_doc.edit_sessionpresentation',kwargs=dict(name=doc.name,session_id=0))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

        url = urlreverse('ietf.doc.views_doc.edit_sessionpresentation',kwargs=dict(name=doc.name,session_id=sp.session_id))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

        self.client.login(username=self.other_chair.user.username,password='%s+password'%self.other_chair.user.username)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        
        self.client.login(username=self.group_chair.user.username,password='%s+password'%self.group_chair.user.username)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(2,len(q('select#id_version option')))

        self.assertEqual(1,doc.docevent_set.count())
        response = self.client.post(url,{'version':'00','save':''})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(doc.sessionpresentation_set.get(pk=sp.pk).rev,'00')
        self.assertEqual(2,doc.docevent_set.count())

    def test_edit_document_session_after_proceedings_closed(self):
        doc = IndividualDraftFactory.create()
        sp = doc.sessionpresentation_set.create(session=self.past_cutoff,rev=None)

        url = urlreverse('ietf.doc.views_doc.edit_sessionpresentation',kwargs=dict(name=doc.name,session_id=sp.session_id))
        self.client.login(username=self.group_chair.user.username,password='%s+password'%self.group_chair.user.username)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        
        self.client.login(username='secretary',password='secretary+password')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q=PyQuery(response.content)
        self.assertEqual(1,len(q(".alert-warning:contains('may affect published proceedings')")))

    def test_remove_document_session(self):
        doc = IndividualDraftFactory.create()
        sp = doc.sessionpresentation_set.create(session=self.future,rev=None)

        url = urlreverse('ietf.doc.views_doc.remove_sessionpresentation',kwargs=dict(name='no-such-doc',session_id=sp.session_id))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

        url = urlreverse('ietf.doc.views_doc.remove_sessionpresentation',kwargs=dict(name=doc.name,session_id=0))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

        url = urlreverse('ietf.doc.views_doc.remove_sessionpresentation',kwargs=dict(name=doc.name,session_id=sp.session_id))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

        self.client.login(username=self.other_chair.user.username,password='%s+password'%self.other_chair.user.username)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        
        self.client.login(username=self.group_chair.user.username,password='%s+password'%self.group_chair.user.username)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(1,doc.docevent_set.count())
        response = self.client.post(url,{'remove_session':''})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(doc.sessionpresentation_set.filter(pk=sp.pk).exists())
        self.assertEqual(2,doc.docevent_set.count())

    def test_remove_document_session_after_proceedings_closed(self):
        doc = IndividualDraftFactory.create()
        sp = doc.sessionpresentation_set.create(session=self.past_cutoff,rev=None)

        url = urlreverse('ietf.doc.views_doc.remove_sessionpresentation',kwargs=dict(name=doc.name,session_id=sp.session_id))
        self.client.login(username=self.group_chair.user.username,password='%s+password'%self.group_chair.user.username)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        
        self.client.login(username='secretary',password='secretary+password')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q=PyQuery(response.content)
        self.assertEqual(1,len(q(".alert-warning:contains('may affect published proceedings')")))

    def test_add_document_session(self):
        doc = IndividualDraftFactory.create()

        url = urlreverse('ietf.doc.views_doc.add_sessionpresentation',kwargs=dict(name=doc.name))
        login_testing_unauthorized(self,self.group_chair.user.username,url)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
    
        response = self.client.post(url,{'session':0,'version':'current'})
        self.assertEqual(response.status_code,200)
        q=PyQuery(response.content)
        self.assertTrue(q('.form-group.has-error'))
     
        response = self.client.post(url,{'session':self.future.pk,'version':'bogus version'})
        self.assertEqual(response.status_code,200)
        q=PyQuery(response.content)
        self.assertTrue(q('.form-group.has-error'))

        self.assertEqual(1,doc.docevent_set.count())
        response = self.client.post(url,{'session':self.future.pk,'version':'current'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(2,doc.docevent_set.count())


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
        self.assertEqual("New draft revisions over time for %s" % person.name, d['title']['text'])

        data_url = urlreverse('ietf.doc.views_stats.chart_data_person_drafts', kwargs=dict(id=person.id))

        r = self.client.get(data_url)
        self.assertValidJSONResponse(r)
        d = r.json()
        self.assertEqual(len(d), 1)
        self.assertEqual(len(d[0]), 2)

        page_url = urlreverse('ietf.person.views.profile', kwargs=dict(email_or_name=person.name))
        r = self.client.get(page_url)
        self.assertEqual(r.status_code, 200)
        

class FieldTests(TestCase):
    def test_searchabledocumentsfield_pre(self):
        # so far, just tests that the format expected by select2-field.js is set up
        docs = IndividualDraftFactory.create_batch(3)
        
        class _TestForm(Form):
            test_field = SearchableDocumentsField()
        
        form = _TestForm(initial=dict(test_field=docs))
        html = str(form)
        q = PyQuery(html)
        json_data = q('input.select2-field').attr('data-pre')
        try:
            decoded = json.loads(json_data)
        except json.JSONDecodeError as e:
            self.fail('data-pre contained invalid JSON data: %s' % str(e))
        decoded_ids = list(decoded.keys())
        self.assertCountEqual(decoded_ids, [str(doc.id) for doc in docs])
        for doc in docs:
            self.assertEqual(
                dict(id=doc.pk, text=escape(uppercase_std_abbreviated_name(doc.name))),
                decoded[str(doc.pk)],
            )
