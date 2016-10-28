import os
import shutil
import datetime
import json
import sys
import urlparse
import bibtexparser
if sys.version_info[0] == 2 and sys.version_info[1] < 7:
    import unittest2 as unittest
else:
    import unittest
from pyquery import PyQuery
from tempfile import NamedTemporaryFile
from Cookie import SimpleCookie

from django.core.urlresolvers import reverse as urlreverse
from django.conf import settings

from tastypie.test import ResourceTestCaseMixin

import debug                            # pyflakes:ignore

from ietf.doc.models import ( Document, DocAlias, DocRelationshipName, RelatedDocument, State,
    DocEvent, BallotPositionDocEvent, LastCallDocEvent, WriteupDocEvent, NewRevisionDocEvent )
from ietf.doc.factories import DocumentFactory, DocEventFactory
from ietf.group.models import Group
from ietf.group.factories import GroupFactory
from ietf.meeting.models import Meeting, Session, SessionPresentation
from ietf.meeting.factories import SessionFactory
from ietf.meeting.test_data import make_meeting_test_data
from ietf.name.models import SessionStatusName
from ietf.person.models import Person
from ietf.person.factories import PersonFactory
from ietf.utils.mail import outbox
from ietf.utils.test_data import make_test_data
from ietf.utils.test_utils import login_testing_unauthorized, unicontent
from ietf.utils.test_utils import TestCase

class SearchTests(TestCase):
    def test_search(self):
        draft = make_test_data()

        base_url = urlreverse("doc_search")

        # only show form, no search yet
        r = self.client.get(base_url)
        self.assertEqual(r.status_code, 200)

        # no match
        r = self.client.get(base_url + "?activedrafts=on&name=thisisnotadocumentname")
        self.assertEqual(r.status_code, 200)
        self.assertTrue("no documents match" in str(r.content).lower())

        r = self.client.get(base_url + "?rfcs=on&name=xyzzy")
        self.assertEqual(r.status_code, 200)
        self.assertTrue("no documents match" in unicontent(r).lower())

        r = self.client.get(base_url + "?olddrafts=on&name=bar")
        self.assertEqual(r.status_code, 200)
        self.assertTrue("no documents match" in unicontent(r).lower())

        r = self.client.get(base_url + "?olddrafts=on&name=foo")
        self.assertEqual(r.status_code, 200)
        self.assertTrue("draft-foo-mars-test" in unicontent(r).lower())

        # find by rfc/active/inactive
        draft.set_state(State.objects.get(type="draft", slug="rfc"))
        r = self.client.get(base_url + "?rfcs=on&name=%s" % draft.name)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in unicontent(r))

        draft.set_state(State.objects.get(type="draft", slug="active"))
        r = self.client.get(base_url + "?activedrafts=on&name=%s" % draft.name)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in unicontent(r))

        draft.set_state(State.objects.get(type="draft", slug="expired"))
        r = self.client.get(base_url + "?olddrafts=on&name=%s" % draft.name)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in unicontent(r))
        
        draft.set_state(State.objects.get(type="draft", slug="active"))

        # find by title
        r = self.client.get(base_url + "?activedrafts=on&name=%s" % draft.title.split()[0])
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in unicontent(r))

        # find by author
        r = self.client.get(base_url + "?activedrafts=on&by=author&author=%s" % draft.authors.all()[0].person.name_parts()[1])
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in unicontent(r))

        # find by group
        r = self.client.get(base_url + "?activedrafts=on&by=group&group=%s" % draft.group.acronym)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in unicontent(r))

        # find by area
        r = self.client.get(base_url + "?activedrafts=on&by=area&area=%s" % draft.group.parent_id)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in unicontent(r))

        # find by area
        r = self.client.get(base_url + "?activedrafts=on&by=area&area=%s" % draft.group.parent_id)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in unicontent(r))

        # find by AD
        r = self.client.get(base_url + "?activedrafts=on&by=ad&ad=%s" % draft.ad_id)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in unicontent(r))

        # find by IESG state
        r = self.client.get(base_url + "?activedrafts=on&by=state&state=%s&substate=" % draft.get_state("draft-iesg").pk)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in unicontent(r))

    def test_search_for_name(self):
        draft = make_test_data()
        make_meeting_test_data()
        draft.save_with_history([DocEvent.objects.create(doc=draft, type="changed_document", by=Person.objects.get(user__username="secretary"), desc="Test")])

        prev_rev = draft.rev
        draft.rev = "%02d" % (int(prev_rev) + 1)
        draft.save_with_history([DocEvent.objects.create(doc=draft, type="changed_document", by=Person.objects.get(user__username="secretary"), desc="Test")])

        # exact match
        r = self.client.get(urlreverse("doc_search_for_name", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse.urlparse(r["Location"]).path, urlreverse("doc_view", kwargs=dict(name=draft.name)))

        # prefix match
        r = self.client.get(urlreverse("doc_search_for_name", kwargs=dict(name="-".join(draft.name.split("-")[:-1]))))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse.urlparse(r["Location"]).path, urlreverse("doc_view", kwargs=dict(name=draft.name)))

        # non-prefix match
        r = self.client.get(urlreverse("doc_search_for_name", kwargs=dict(name="-".join(draft.name.split("-")[1:]))))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse.urlparse(r["Location"]).path, urlreverse("doc_view", kwargs=dict(name=draft.name)))

        # other doctypes than drafts
        doc = Document.objects.get(name='charter-ietf-mars')
        r = self.client.get(urlreverse("doc_search_for_name", kwargs=dict(name='charter-ietf-ma')))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse.urlparse(r["Location"]).path, urlreverse("doc_view", kwargs=dict(name=doc.name)))

        doc = Document.objects.filter(name__startswith='conflict-review-').first()
        r = self.client.get(urlreverse("doc_search_for_name", kwargs=dict(name="-".join(doc.name.split("-")[:-1]))))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse.urlparse(r["Location"]).path, urlreverse("doc_view", kwargs=dict(name=doc.name)))

        doc = Document.objects.filter(name__startswith='status-change-').first()
        r = self.client.get(urlreverse("doc_search_for_name", kwargs=dict(name="-".join(doc.name.split("-")[:-1]))))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse.urlparse(r["Location"]).path, urlreverse("doc_view", kwargs=dict(name=doc.name)))

        doc = Document.objects.filter(name__startswith='agenda-').first()
        r = self.client.get(urlreverse("doc_search_for_name", kwargs=dict(name="-".join(doc.name.split("-")[:-1]))))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse.urlparse(r["Location"]).path, urlreverse("doc_view", kwargs=dict(name=doc.name)))

        doc = Document.objects.filter(name__startswith='minutes-').first()
        r = self.client.get(urlreverse("doc_search_for_name", kwargs=dict(name="-".join(doc.name.split("-")[:-1]))))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse.urlparse(r["Location"]).path, urlreverse("doc_view", kwargs=dict(name=doc.name)))

        doc = Document.objects.filter(name__startswith='slides-').first()
        r = self.client.get(urlreverse("doc_search_for_name", kwargs=dict(name="-".join(doc.name.split("-")[:-1]))))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse.urlparse(r["Location"]).path, urlreverse("doc_view", kwargs=dict(name=doc.name)))

        # match with revision
        r = self.client.get(urlreverse("doc_search_for_name", kwargs=dict(name=draft.name + "-" + prev_rev)))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse.urlparse(r["Location"]).path, urlreverse("doc_view", kwargs=dict(name=draft.name, rev=prev_rev)))

        # match with non-existing revision
        r = self.client.get(urlreverse("doc_search_for_name", kwargs=dict(name=draft.name + "-09")))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse.urlparse(r["Location"]).path, urlreverse("doc_view", kwargs=dict(name=draft.name)))

        # match with revision and extension
        r = self.client.get(urlreverse("doc_search_for_name", kwargs=dict(name=draft.name + "-" + prev_rev + ".txt")))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse.urlparse(r["Location"]).path, urlreverse("doc_view", kwargs=dict(name=draft.name, rev=prev_rev)))
        
        # no match
        r = self.client.get(urlreverse("doc_search_for_name", kwargs=dict(name="draft-ietf-doesnotexist-42")))
        self.assertEqual(r.status_code, 302)

        parsed = urlparse.urlparse(r["Location"])
        self.assertEqual(parsed.path, urlreverse("doc_search"))
        self.assertEqual(urlparse.parse_qs(parsed.query)["name"][0], "draft-ietf-doesnotexist-42")

    def test_frontpage(self):
        make_test_data()
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Document Search" in unicontent(r))

    def test_drafts_pages(self):
        draft = make_test_data()

        r = self.client.get(urlreverse("docs_for_ad", kwargs=dict(name=draft.ad.full_name_as_key())))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in unicontent(r))

        draft.set_state(State.objects.get(type="draft-iesg", slug="lc"))
        r = self.client.get(urlreverse("drafts_in_last_call"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in unicontent(r))
        
    def test_indexes(self):
        draft = make_test_data()

        r = self.client.get(urlreverse("index_all_drafts"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.name in unicontent(r))

        r = self.client.get(urlreverse("index_active_drafts"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in unicontent(r))

    def test_ajax_search_docs(self):
        draft = make_test_data()

        # Document
        url = urlreverse("ajax_select2_search_docs", kwargs={
            "model_name": "document",
            "doc_type": "draft",
        })
        r = self.client.get(url, dict(q=draft.name))
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertEqual(data[0]["id"], draft.pk)

        # DocAlias
        doc_alias = draft.docalias_set.get()

        url = urlreverse("ajax_select2_search_docs", kwargs={
            "model_name": "docalias",
            "doc_type": "draft",
        })

        r = self.client.get(url, dict(q=doc_alias.name))
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertEqual(data[0]["id"], doc_alias.pk)
        

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
        self.id_dir = os.path.abspath("tmp-id-dir")
        if not os.path.exists(self.id_dir):
            os.mkdir(self.id_dir)
        self.saved_internet_draft_path = settings.INTERNET_DRAFT_PATH
        settings.INTERNET_DRAFT_PATH = self.id_dir
        self.saved_internet_all_drafts_archive_dir = settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR
        settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR = self.id_dir
        f = open(os.path.join(self.id_dir, 'draft-ietf-mars-test-01.txt'), 'w')
        f.write(self.draft_text)
        f.close()

    def tearDown(self):
        settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR = self.saved_internet_all_drafts_archive_dir
        settings.INTERNET_DRAFT_PATH = self.saved_internet_draft_path
        shutil.rmtree(self.id_dir)

    def test_document_draft(self):
        draft = make_test_data()

        # these tests aren't testing all attributes yet, feel free to
        # expand them


        # active draft
        draft.set_state(State.objects.get(type="draft", slug="active"))

        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Active Internet-Draft" in unicontent(r))
        self.assertTrue("Show full document text" in unicontent(r))
        self.assertFalse("Deimos street" in unicontent(r))

        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=draft.name)) + "?include_text=0")
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Active Internet-Draft" in unicontent(r))
        self.assertFalse("Show full document text" in unicontent(r))
        self.assertTrue("Deimos street" in unicontent(r))

        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=draft.name)) + "?include_text=foo")
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Active Internet-Draft" in unicontent(r))
        self.assertFalse("Show full document text" in unicontent(r))
        self.assertTrue("Deimos street" in unicontent(r))

        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=draft.name)) + "?include_text=1")
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Active Internet-Draft" in unicontent(r))
        self.assertFalse("Show full document text" in unicontent(r))
        self.assertTrue("Deimos street" in unicontent(r))

        self.client.cookies = SimpleCookie({'full_draft': 'on'})
        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Active Internet-Draft" in unicontent(r))
        self.assertFalse("Show full document text" in unicontent(r))
        self.assertTrue("Deimos street" in unicontent(r))

        self.client.cookies = SimpleCookie({'full_draft': 'off'})
        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Active Internet-Draft" in unicontent(r))
        self.assertTrue("Show full document text" in unicontent(r))
        self.assertFalse("Deimos street" in unicontent(r))

        self.client.cookies = SimpleCookie({'full_draft': 'foo'})
        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Active Internet-Draft" in unicontent(r))
        self.assertTrue("Show full document text" in unicontent(r))
        self.assertFalse("Deimos street" in unicontent(r))

        # expired draft
        draft.set_state(State.objects.get(type="draft", slug="expired"))

        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Expired Internet-Draft" in unicontent(r))

        # replaced draft
        draft.set_state(State.objects.get(type="draft", slug="repl"))

        replacement = Document.objects.create(
            name="draft-ietf-replacement",
            time=datetime.datetime.now(),
            type_id="draft",
            title="Replacement Draft",
            stream_id=draft.stream_id, group_id=draft.group_id, abstract=draft.stream, rev=draft.rev,
            pages=draft.pages, intended_std_level_id=draft.intended_std_level_id,
            shepherd_id=draft.shepherd_id, ad_id=draft.ad_id, expires=draft.expires,
            notify=draft.notify, note=draft.note)
        DocAlias.objects.create(name=replacement.name, document=replacement)
        rel = RelatedDocument.objects.create(source=replacement,
                                             target=draft.docalias_set.get(name__startswith="draft"),
                                             relationship_id="replaces")

        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Replaced Internet-Draft" in unicontent(r))
        self.assertTrue(replacement.name in unicontent(r))
        rel.delete()

        # draft published as RFC
        draft.set_state(State.objects.get(type="draft", slug="rfc"))
        draft.std_level_id = "bcp"
        draft.save_with_history([DocEvent.objects.create(doc=draft, type="published_rfc", by=Person.objects.get(name="(System)"))])


        rfc_alias = DocAlias.objects.create(name="rfc123456", document=draft)
        bcp_alias = DocAlias.objects.create(name="bcp123456", document=draft)

        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 302)
        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=bcp_alias.name)))
        self.assertEqual(r.status_code, 302)

        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=rfc_alias.name)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("RFC 123456" in unicontent(r))
        self.assertTrue(draft.name in unicontent(r))

        # naked RFC
        rfc = Document.objects.create(
            name="rfc1234567",
            type_id="draft",
            title="RFC without a Draft",
            stream_id="ise",
            group=Group.objects.get(type="individ"),
            std_level_id="ps")
        DocAlias.objects.create(name=rfc.name, document=rfc)
        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=rfc.name)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("RFC 1234567" in unicontent(r))

        # unknown draft
        r = self.client.get(urlreverse("doc_view", kwargs=dict(name="draft-xyz123")))
        self.assertEqual(r.status_code, 404)

    def test_document_primary_and_history_views(self):
        make_test_data()
        make_meeting_test_data()

        # Ensure primary views of both current and historic versions of documents works
        for docname in ["draft-imaginary-independent-submission",
                        "conflict-review-imaginary-irtf-submission",
                        "status-change-imaginary-mid-review",
                        "charter-ietf-mars",
                        "agenda-42-mars",
                        "minutes-42-mars",
                        "slides-42-mars-1-active",
                        # TODO: add
                        #"bluesheets-42-mars-1",
                        #"recording-42-mars-1-00",
                       ]:
            doc = Document.objects.get(name=docname)
            # give it some history
            doc.save_with_history([DocEvent.objects.create(doc=doc, type="changed_document", by=Person.objects.get(user__username="secretary"), desc="Test")])

            doc.rev = "01"
            doc.save_with_history([DocEvent.objects.create(doc=doc, type="changed_document", by=Person.objects.get(user__username="secretary"), desc="Test")])

            r = self.client.get(urlreverse("doc_view", kwargs=dict(name=doc.name)))
            self.assertEqual(r.status_code, 200)
            self.assertTrue("%s-01"%docname in unicontent(r))
    
            r = self.client.get(urlreverse("doc_view", kwargs=dict(name=doc.name,rev="01")))
            self.assertEqual(r.status_code, 302)
     
            r = self.client.get(urlreverse("doc_view", kwargs=dict(name=doc.name,rev="00")))
            self.assertEqual(r.status_code, 200)
            self.assertTrue("%s-00"%docname in unicontent(r))

class DocTestCase(TestCase):
    def test_document_charter(self):
        make_test_data()

        r = self.client.get(urlreverse("doc_view", kwargs=dict(name="charter-ietf-mars")))
        self.assertEqual(r.status_code, 200)

    def test_document_conflict_review(self):
        make_test_data()

        r = self.client.get(urlreverse("doc_view", kwargs=dict(name='conflict-review-imaginary-irtf-submission')))
        self.assertEqual(r.status_code, 200)

    def test_document_material(self):
        draft = make_test_data()

        doc = Document.objects.create(
            name="slides-testteam-test-slides",
            rev="00",
            title="Test Slides",
            group=draft.group,
            type_id="slides"
        )
        doc.set_state(State.objects.get(type="slides", slug="active"))
        DocAlias.objects.create(name=doc.name, document=doc)

        session = Session.objects.create(
            name = "session-42-mars-1",
            meeting = Meeting.objects.get(number='42'),
            group = Group.objects.get(acronym='mars'),
            status = SessionStatusName.objects.create(slug='scheduled', name='Scheduled'),
            modified = datetime.datetime.now(),
            requested_by = Person.objects.get(user__username="marschairman"),
            type_id = "session",
            )
        SessionPresentation.objects.create(session=session, document=doc, rev=doc.rev)

        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)

    def test_document_ballot(self):
        doc = make_test_data()
        ballot = doc.active_ballot()

        # make sure we have some history
        doc.save_with_history([DocEvent.objects.create(doc=doc, type="changed_document", by=Person.objects.get(user__username="secretary"), desc="Test")])

        pos = BallotPositionDocEvent.objects.create(
            doc=doc,
            ballot=ballot,
            type="changed_ballot_position",
            pos_id="yes",
            comment="Looks fine to me",
            comment_time=datetime.datetime.now(),
            ad=Person.objects.get(user__username="ad"),
            by=Person.objects.get(name="(System)"))

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(pos.comment in unicontent(r))

        # test with ballot_id
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name, ballot_id=ballot.pk)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(pos.comment in unicontent(r))

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
        self.assertTrue( '(%s for -%s)' % (pos.comment_time.strftime('%Y-%m-%d'), oldrev) in unicontent(r))
        
    def test_document_ballot_needed_positions(self):
        make_test_data()

        # draft
        doc = Document.objects.get(name='draft-ietf-mars-test')
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name)))
        self.assertTrue('more YES or NO' in unicontent(r))
        Document.objects.filter(pk=doc.pk).update(intended_std_level='inf')
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name)))
        self.assertFalse('more YES or NO' in unicontent(r))

        # status change
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        iesgeval_pk = str(State.objects.get(slug='iesgeval',type__slug='statchg').pk)
        self.client.login(username='ad', password='ad+password')
        r = self.client.post(urlreverse('ietf.doc.views_status_change.change_state',kwargs=dict(name=doc.name)),dict(new_state=iesgeval_pk))
        self.assertEqual(r.status_code, 302)
        r = self.client.get(r._headers["location"][1])
        self.assertTrue(">IESG Evaluation<" in unicontent(r))

        doc.relateddocument_set.create(target=DocAlias.objects.get(name='rfc9998'),relationship_id='tohist')
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name)))
        self.assertFalse('Needs a YES' in unicontent(r))
        self.assertFalse('more YES or NO' in unicontent(r))

        doc.relateddocument_set.create(target=DocAlias.objects.get(name='rfc9999'),relationship_id='tois')
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name)))
        self.assertTrue('more YES or NO' in unicontent(r))

    def test_document_json(self):
        doc = make_test_data()

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_json", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertEqual(doc.name, data['name'])
        self.assertEqual(doc.pages,data['pages'])

    def test_writeup(self):
        doc = make_test_data()

        appr = WriteupDocEvent.objects.create(
            doc=doc,
            desc="Changed text",
            type="changed_ballot_approval_text",
            text="This is ballot approval text.",
            by=Person.objects.get(name="(System)"))

        notes = WriteupDocEvent.objects.create(
            doc=doc,
            desc="Changed text",
            type="changed_ballot_writeup_text",
            text="This is ballot writeup notes.",
            by=Person.objects.get(name="(System)"))

        rfced_note = WriteupDocEvent.objects.create(
            doc=doc,
            desc="Changed text",
            type="changed_rfc_editor_note_text",
            text="This is a note for the RFC Editor.",
            by=Person.objects.get(name="(System)"))

        url = urlreverse('doc_writeup', kwargs=dict(name=doc.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(appr.text in unicontent(r))
        self.assertTrue(notes.text in unicontent(r))
        self.assertTrue(rfced_note.text in r.content)

    def test_history(self):
        doc = make_test_data()

        e = DocEvent.objects.create(
            doc=doc,
            desc="Something happened.",
            type="added_comment",
            by=Person.objects.get(name="(System)"))

        url = urlreverse('doc_history', kwargs=dict(name=doc.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(e.desc in unicontent(r))
        
    def test_document_feed(self):
        doc = make_test_data()

        e = DocEvent.objects.create(
            doc=doc,
            desc="Something happened.",
            type="added_comment",
            by=Person.objects.get(name="(System)"))

        r = self.client.get("/feed/document-changes/%s/" % doc.name)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(e.desc in unicontent(r))

    def test_last_call_feed(self):
        doc = make_test_data()

        doc.set_state(State.objects.get(type="draft-iesg", slug="lc"))

        LastCallDocEvent.objects.create(
            doc=doc,
            desc="Last call",
            type="sent_last_call",
            by=Person.objects.get(user__username="secretary"),
            expires=datetime.date.today() + datetime.timedelta(days=7))

        r = self.client.get("/feed/last-call/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(doc.name in unicontent(r))

    def test_rfc_feed(self):
        make_test_data()
        r = self.client.get("/feed/rfc/")
        self.assertTrue(r.status_code, 200)

    def test_state_help(self):
        url = urlreverse('state_help', kwargs=dict(type="draft-iesg"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(State.objects.get(type="draft-iesg", slug="lc").name in unicontent(r))

    def test_document_nonietf_pubreq_button(self):
        doc = make_test_data()

        self.client.login(username='iab-chair', password='iab-chair+password')
        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Request publication" not in unicontent(r))

        Document.objects.filter(pk=doc.pk).update(stream='iab')
        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Request publication" in unicontent(r))

        doc.states.add(State.objects.get(type_id='draft-stream-iab',slug='rfc-edit'))
        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Request publication" not in unicontent(r))


    def test_document_bibtex(self):

        rfc = DocumentFactory.create(
                  other_aliases = ['rfc6020',],
                  states = [('draft','rfc'),('draft-iesg','pub')],
                  std_level_id = 'ps',
                  time = '2010-10-10',
              )
        DocEventFactory.create(doc=rfc, type='published_rfc', time = '2010-10-10')
        #
        url = urlreverse('ietf.doc.views_doc.document_bibtex', kwargs=dict(name=rfc.name))
        r = self.client.get(url)
        entry = bibtexparser.loads(r.content).get_entry_dict()["rfc6020"]
        self.assertEqual(entry['series'],   u'Request for Comments')
        self.assertEqual(entry['number'],   u'6020')
        self.assertEqual(entry['doi'],      u'10.17487/rfc6020')
        self.assertEqual(entry['year'],     u'2010')
        self.assertEqual(entry['month'],    u'oct')
        #
        self.assertNotIn('day', entry)

        april1 = DocumentFactory.create(
                  other_aliases =   ['rfc1149',],
                  stream_id =       'rse',
                  states =          [('draft','rfc'),('draft-iesg','pub')],
                  std_level_id =    'ind',
                  time =            '1990-04-01',
              )
        DocEventFactory.create(doc=april1, type='published_rfc', time = '1990-04-01')
        #
        url = urlreverse('ietf.doc.views_doc.document_bibtex', kwargs=dict(name=april1.name))
        r = self.client.get(url)
        entry = bibtexparser.loads(r.content).get_entry_dict()['rfc1149']
        self.assertEqual(entry['series'],   u'Request for Comments')
        self.assertEqual(entry['number'],   u'1149')
        self.assertEqual(entry['doi'],      u'10.17487/rfc1149')
        self.assertEqual(entry['year'],     u'1990')
        self.assertEqual(entry['month'],    u'apr')
        self.assertEqual(entry['day'],      u'1')

        draft = DocumentFactory.create()
        docname = u'%s-%s' % (draft.name, draft.rev)
        bibname = docname[6:]           # drop the 'draft-' prefix
        url = urlreverse('ietf.doc.views_doc.document_bibtex', kwargs=dict(name=draft.name))
        r = self.client.get(url)
        entry = bibtexparser.loads(r.content).get_entry_dict()[bibname]
        self.assertEqual(entry['note'],     u'Work in Progress')
        self.assertEqual(entry['number'],   docname)
        self.assertEqual(entry['year'],     str(draft.pub_date().year))
        self.assertEqual(entry['month'],    draft.pub_date().strftime('%b').lower())
        self.assertEqual(entry['day'],      str(draft.pub_date().day))
        #
        self.assertNotIn('doi', entry)

class AddCommentTestCase(TestCase):
    def test_add_comment(self):
        draft = make_test_data()
        url = urlreverse('doc_add_comment', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
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
        self.assertTrue("Comment added" in outbox[-1]['Subject'])
        self.assertTrue(draft.name in outbox[-1]['Subject'])
        self.assertTrue('draft-ietf-mars-test@' in outbox[-1]['To'])

        # Make sure we can also do it as IANA
        self.client.login(username="iana", password="iana+password")

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form textarea[name=comment]')), 1)


class TemplateTagTest(unittest.TestCase):
    def test_template_tags(self):
        import doctest
        from ietf.doc.templatetags import ietf_filters
        failures, tests = doctest.testmod(ietf_filters)
        self.assertEqual(failures, 0)

class ReferencesTest(TestCase):

    def test_references(self):
        make_test_data()
        doc1 = Document.objects.get(name='draft-ietf-mars-test')
        doc2 = DocAlias.objects.get(name='draft-imaginary-independent-submission')
        RelatedDocument.objects.get_or_create(source=doc1,target=doc2,relationship=DocRelationshipName.objects.get(slug='refnorm'))
        url = urlreverse('doc_references', kwargs=dict(name=doc1.name))
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        self.assertTrue(doc2.name in unicontent(r))
        url = urlreverse('doc_referenced_by', kwargs=dict(name=doc2.name))
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        self.assertTrue(doc1.name in unicontent(r))
       

class EmailAliasesTests(TestCase):

    def setUp(self):
        make_test_data()
        self.doc_alias_file = NamedTemporaryFile(delete=False)
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
        url = urlreverse('doc_specific_email_aliases', kwargs=dict(name="draft-ietf-mars-test"))
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
        self.assertTrue('draft-ietf-mars-test.all@ietf.org' in unicontent(r))
        self.assertTrue('ballot_saved' in unicontent(r))

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
        doc = DocumentFactory.create()
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
        doc = DocumentFactory.create()
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
        doc = DocumentFactory.create()
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
        doc = DocumentFactory.create()
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
        doc = DocumentFactory.create()
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
        doc = DocumentFactory.create()

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
        doc = DocumentFactory.create(states=[('draft','active')])

        conf_url = urlreverse('ietf.doc.views_stats.chart_conf_newrevisiondocevent')

        # No qurey arguments; expect an empty json object
        r = self.client.get(conf_url)
        self.assertValidJSONResponse(r)
        self.assertEqual(r.content, '{}')

        # No match
        r = self.client.get(conf_url + '?activedrafts=on&name=thisisnotadocumentname')
        self.assertValidJSONResponse(r)
        d = json.loads(r.content)
        self.assertEqual(d['chart']['type'], settings.CHART_TYPE_COLUMN_OPTIONS['chart']['type'])

        r = self.client.get(conf_url + '?activedrafts=on&name=%s'%doc.name[6:12])
        self.assertValidJSONResponse(r)
        d = json.loads(r.content)
        self.assertEqual(d['chart']['type'], settings.CHART_TYPE_COLUMN_OPTIONS['chart']['type'])
        self.assertEqual(len(d['series'][0]['data']), 0)

    def test_search_chart_data(self):
        doc = DocumentFactory.create(states=[('draft','active')])

        data_url = urlreverse('ietf.doc.views_stats.chart_data_newrevisiondocevent')

        # No qurey arguments; expect an empty json list
        r = self.client.get(data_url)
        self.assertValidJSONResponse(r)
        self.assertEqual(r.content, '[]')

        # No match
        r = self.client.get(data_url + '?activedrafts=on&name=thisisnotadocumentname')
        self.assertValidJSONResponse(r)
        d = json.loads(r.content)
        self.assertEqual(r.content, '[]')

        r = self.client.get(data_url + '?activedrafts=on&name=%s'%doc.name[6:12])
        self.assertValidJSONResponse(r)
        d = json.loads(r.content)
        self.assertEqual(len(d), 1)
        self.assertEqual(len(d[0]), 2)

    def test_search_chart(self):
        doc = DocumentFactory.create(states=[('draft','active')])

        chart_url = urlreverse('ietf.doc.views_stats.chart_newrevisiondocevent')
        r = self.client.get(chart_url)
        self.assertEqual(r.status_code, 200)

        r = self.client.get(chart_url + '?activedrafts=on&name=%s'%doc.name[6:12])
        self.assertEqual(r.status_code, 200)
        
    def test_personal_chart(self):
        person = PersonFactory.create()
        DocumentFactory.create(
            states=[('draft','active')],
            authors=[person.email(), ],
        )

        conf_url = urlreverse('ietf.doc.views_stats.chart_conf_person_drafts', kwargs=dict(id=person.id))

        r = self.client.get(conf_url)
        self.assertValidJSONResponse(r)
        d = json.loads(r.content)
        self.assertEqual(d['chart']['type'], settings.CHART_TYPE_COLUMN_OPTIONS['chart']['type'])
        self.assertEqual("New draft revisions over time for %s" % person.name, d['title']['text'])

        data_url = urlreverse('ietf.doc.views_stats.chart_data_person_drafts', kwargs=dict(id=person.id))

        r = self.client.get(data_url)
        self.assertValidJSONResponse(r)
        d = json.loads(r.content)
        self.assertEqual(len(d), 1)
        self.assertEqual(len(d[0]), 2)

        page_url = urlreverse('ietf.person.views.profile', kwargs=dict(email_or_name=person.name))
        r = self.client.get(page_url)
        self.assertEqual(r.status_code, 200)
        
