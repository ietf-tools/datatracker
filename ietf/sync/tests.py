# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import os
import io
import json
import datetime
import mock
import quopri
import requests

from dataclasses import dataclass

from django.conf import settings
from django.urls import reverse as urlreverse
from django.utils import timezone
from django.test.utils import override_settings

import debug                            # pyflakes:ignore

from ietf.api.views import EmailIngestionError
from ietf.doc.factories import (
    WgDraftFactory,
    RfcFactory,
    DocumentAuthorFactory,
    DocEventFactory,
    BcpFactory,
)
from ietf.doc.models import Document, DocEvent, DeletedEvent, DocTagName, RelatedDocument, State, StateDocEvent
from ietf.doc.utils import add_state_change_event
from ietf.group.factories import GroupFactory
from ietf.person.factories import PersonFactory
from ietf.person.models import Person
from ietf.sync import iana, rfceditor, tasks
from ietf.utils.mail import outbox, empty_outbox
from ietf.utils.test_utils import login_testing_unauthorized
from ietf.utils.test_utils import TestCase
from ietf.utils.timezone import date_today, RPC_TZINFO


class IANASyncTests(TestCase):
    def test_protocol_page_sync(self):
        draft = WgDraftFactory()
        rfc = RfcFactory(rfc_number=1234)
        draft.relateddocument_set.create(relationship_id="became_rfc", target = rfc)
        DocEvent.objects.create(doc=rfc, rev="", type="published_rfc", by=Person.objects.get(name="(System)"))

        rfc_names = iana.parse_protocol_page('<html><a href="/go/rfc1234/">RFC 1234</a></html>')
        self.assertEqual(len(rfc_names), 1)
        self.assertEqual(rfc_names[0], "rfc1234")

        iana.update_rfc_log_from_protocol_page(rfc_names, timezone.now() - datetime.timedelta(days=1))
        self.assertEqual(DocEvent.objects.filter(doc=rfc, type="rfc_in_iana_registry").count(), 1)

        # make sure it doesn't create duplicates
        iana.update_rfc_log_from_protocol_page(rfc_names, timezone.now() - datetime.timedelta(days=1))
        self.assertEqual(DocEvent.objects.filter(doc=rfc, type="rfc_in_iana_registry").count(), 1)

    def test_changes_sync(self):
        draft = WgDraftFactory(ad=Person.objects.get(user__username='ad'))

        data = json.dumps({
            "changes": [
                    {
                        "time": "2011-10-09 12:00:01",
                        "doc": draft.name,
                        "state": "IANA Not OK",
                        "type": "iana_review",
                    },
                    {
                        "time": "2011-10-09 12:00:02",
                        "doc": draft.name,
                        "state": "IANA - Review Needed", # this should be skipped
                        "type": "iana_review",
                    },
                    {
                        "time": "2011-10-09 12:00:00",
                        "doc": draft.name,
                        "state": "Waiting on RFC-Editor",
                        "type": "iana_state",
                    },
                    {
                        "time": "2011-10-09 11:00:00",
                        "doc": draft.name,
                        "state": "In Progress",
                        "type": "iana_state",
                    }
                ]
            })

        changes = iana.parse_changes_json(data)
        # check sorting
        self.assertEqual(changes[0]["time"], "2011-10-09 11:00:00")

        empty_outbox()
        added_events, warnings = iana.update_history_with_changes(changes)

        self.assertEqual(len(added_events), 3)
        self.assertEqual(len(warnings), 0)
        self.assertEqual(draft.get_state_slug("draft-iana-review"), "not-ok")
        self.assertEqual(draft.get_state_slug("draft-iana-action"), "waitrfc")
        e = draft.latest_event(StateDocEvent, type="changed_state", state_type="draft-iana-action")
        self.assertEqual(e.desc, "IANA Action state changed to <b>Waiting on RFC Editor</b> from In Progress")
#        self.assertEqual(e.time, datetime.datetime(2011, 10, 9, 5, 0)) # check timezone handling
        self.assertEqual(len(outbox), 3 )
        for m in outbox:
            self.assertTrue('aread@' in m['To']) 

        # make sure it doesn't create duplicates
        added_events, warnings = iana.update_history_with_changes(changes)
        self.assertEqual(len(added_events), 0)
        self.assertEqual(len(warnings), 0)

    def test_changes_sync_errors(self):
        draft = WgDraftFactory()

        # missing "type"
        data = json.dumps({
                "changes": [
                        {
                            "time": "2011-10-09 12:00:01",
                            "doc": draft.name,
                            "state": "IANA Not OK",
                        },
                    ]
            })

        self.assertRaises(Exception, iana.parse_changes_json, data)

        # error response
        data = json.dumps({
                "error": "I am in error."
            })

        self.assertRaises(Exception, iana.parse_changes_json, data)
        
        # missing document from database
        data = json.dumps({
                "changes": [
                        {
                            "time": "2011-10-09 12:00:01",
                            "doc": "draft-this-does-not-exist",
                            "state": "IANA Not OK",
                            "type": "iana_review",
                        },
                    ]
            })

        changes = iana.parse_changes_json(data)
        added_events, warnings = iana.update_history_with_changes(changes)
        self.assertEqual(len(added_events), 0)
        self.assertEqual(len(warnings), 1)

    def test_iana_review_mail(self):
        draft = WgDraftFactory()

        subject_template = 'Subject: [IANA #12345] Last Call: <%(draft)s-%(rev)s.txt> (Long text) to Informational RFC'
        msg_template = """From: %(fromaddr)s
Date: Thu, 10 May 2012 12:00:0%(rtime)d +0000
Content-Transfer-Encoding: quoted-printable
Content-Type: text/plain; charset=utf-8
%(subject)s

(BEGIN IANA %(tag)s%(embedded_name)s)

IESG:

IANA has reviewed %(draft)s-%(rev)s, which is=20
currently in Last Call, and has the following comments:

IANA understands that, upon approval of this document, there are no=20
IANA Actions that need completion.

Thanks,

%(person)s
IANA “Fake Test” Person
ICANN

(END IANA %(tag)s)
"""

        subjects =  ( subject_template % dict(draft=draft.name,rev=draft.rev) , 'Subject: Vacuous Subject' )

        tags = ('LAST CALL COMMENTS', 'COMMENTS')

        embedded_names = (': %s-%s.txt'%(draft.name,draft.rev), '')

        for subject in subjects:
            for tag in tags:
                for embedded_name in embedded_names:
                    if embedded_name or not 'Vacuous' in subject: 
                    
                        rtime = 7*subjects.index(subject) + 5*tags.index(tag) + embedded_names.index(embedded_name)
                        person=Person.objects.get(user__username="iana")
                        fromaddr = person.email().formatted_email()
                        msg = msg_template % dict(person=quopri.encodestring(person.name.encode('utf-8')),
                                                  fromaddr=fromaddr,
                                                  draft=draft.name,
                                                  rev=draft.rev,
                                                  tag=tag,
                                                  rtime=rtime,
                                                  subject=subject,
                                                  embedded_name=embedded_name,)
                        doc_name, review_time, by, comment = iana.parse_review_email(msg.encode('utf-8'))
    
                        self.assertEqual(doc_name, draft.name)
                        self.assertEqual(review_time, datetime.datetime(2012, 5, 10, 12, 0, rtime, tzinfo=datetime.timezone.utc))
                        self.assertEqual(by, Person.objects.get(user__username="iana"))
                        self.assertIn("there are no IANA Actions", comment.replace("\n", ""))
    
                        events_before = DocEvent.objects.filter(doc=draft, type="iana_review").count()
                        iana.add_review_comment(doc_name, review_time, by, comment)
    
                        e = draft.latest_event(type="iana_review")
                        self.assertTrue(e)
                        self.assertEqual(e.desc, comment)
                        self.assertEqual(e.by, by)
    
                        # make sure it doesn't create duplicates
                        iana.add_review_comment(doc_name, review_time, by, comment)
                        self.assertEqual(DocEvent.objects.filter(doc=draft, type="iana_review").count(), events_before+1)

    @mock.patch("ietf.sync.iana.add_review_comment")
    @mock.patch("ietf.sync.iana.parse_review_email")
    def test_ingest_review_email(self, mock_parse_review_email, mock_add_review_comment):
        mock_parse_review_email.side_effect = ValueError("ouch!")
        message = b"message"
        
        # Error parsing mail
        with self.assertRaises(EmailIngestionError) as context:
            iana.ingest_review_email(message)
        self.assertIsNone(context.exception.as_emailmessage())  # no email
        self.assertEqual("Unable to parse message as IANA review email", str(context.exception))
        self.assertTrue(mock_parse_review_email.called)
        self.assertEqual(mock_parse_review_email.call_args, mock.call(message))
        self.assertFalse(mock_add_review_comment.called)
        mock_parse_review_email.reset_mock()

        args = (
            "doc-name",
            datetime.datetime.now(tz=datetime.timezone.utc),
            PersonFactory(),
            "yadda yadda yadda",
        )
        mock_parse_review_email.side_effect = None
        mock_parse_review_email.return_value = args
        mock_add_review_comment.side_effect = Document.DoesNotExist
        with self.assertRaises(EmailIngestionError) as context:
            iana.ingest_review_email(message)
        self.assertIsNone(context.exception.as_emailmessage())  # no email
        self.assertEqual(str(context.exception), "Unknown document doc-name")
        self.assertTrue(mock_parse_review_email.called)
        self.assertEqual(mock_parse_review_email.call_args, mock.call(message))
        self.assertTrue(mock_add_review_comment.called)
        self.assertEqual(mock_add_review_comment.call_args, mock.call(*args))
        mock_parse_review_email.reset_mock()
        mock_add_review_comment.reset_mock()

        mock_add_review_comment.side_effect = ValueError("ouch!")
        with self.assertRaises(EmailIngestionError) as context:
            iana.ingest_review_email(message)
        self.assertIsNone(context.exception.as_emailmessage())  # no email
        self.assertEqual("Error ingesting IANA review email", str(context.exception))
        self.assertTrue(mock_parse_review_email.called)
        self.assertEqual(mock_parse_review_email.call_args, mock.call(message))
        self.assertTrue(mock_add_review_comment.called)
        self.assertEqual(mock_add_review_comment.call_args, mock.call(*args))
        mock_parse_review_email.reset_mock()
        mock_add_review_comment.reset_mock()

        mock_add_review_comment.side_effect = None
        iana.ingest_review_email(message)
        self.assertTrue(mock_parse_review_email.called)
        self.assertEqual(mock_parse_review_email.call_args, mock.call(message))
        self.assertTrue(mock_add_review_comment.called)
        self.assertEqual(mock_add_review_comment.call_args, mock.call(*args))

    def test_notify_page(self):
        # check that we can get the notify page
        url = urlreverse("ietf.sync.views.notify", kwargs=dict(org="iana", notification="changes"))
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "new changes at")

        # we don't actually try posting as that would trigger a real run
        

class RFCSyncTests(TestCase):
    def write_draft_file(self, name, size):
        with io.open(os.path.join(settings.INTERNET_DRAFT_PATH, name), 'w') as f:
            f.write("a" * size)

    def test_rfc_index(self):
        area = GroupFactory(type_id='area')
        draft_doc = WgDraftFactory(
            group__parent=area,
            states=[('draft-iesg','rfcqueue')],
            ad=Person.objects.get(user__username='ad'),
            external_url="http://my-external-url.example.com",
            note="this is a note",
        )
        DocumentAuthorFactory.create_batch(2, document=draft_doc)
        draft_doc.action_holders.add(draft_doc.ad)  # not normally set, but add to be sure it's cleared

        RfcFactory(rfc_number=123)

        today = date_today()

        t = '''<?xml version="1.0" encoding="UTF-8"?>
<rfc-index xmlns="http://www.rfc-editor.org/rfc-index"
           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
           xsi:schemaLocation="http://www.rfc-editor.org/rfc-index 
                               http://www.rfc-editor.org/rfc-index.xsd">
    <bcp-entry>
        <doc-id>BCP0001</doc-id>
        <is-also>
            <doc-id>RFC1234</doc-id>
            <doc-id>RFC2345</doc-id>
        </is-also>
    </bcp-entry>
    <fyi-entry>
        <doc-id>FYI0001</doc-id>
        <is-also>
            <doc-id>RFC1234</doc-id>
        </is-also>
    </fyi-entry>
    <std-entry>
        <doc-id>STD0002</doc-id>
        <title>Test</title>
        <is-also>
            <doc-id>RFC1234</doc-id>
        </is-also>
    </std-entry>
    <rfc-entry>
        <doc-id>RFC1234</doc-id>
        <title>A Testing RFC</title>
        <author>
            <name>A. Irector</name>
        </author>
        <date>
            <month>%(month)s</month>
            <year>%(year)s</year>
        </date>
        <format>
            <file-format>ASCII</file-format>
        </format>
        <page-count>42</page-count>
        <keywords>
            <kw>test</kw>
        </keywords>
        <abstract><p>This is some interesting text.</p></abstract>
        <draft>%(name)s-%(rev)s</draft>
        <updates>
            <doc-id>RFC123</doc-id>
        </updates>
        <is-also>
            <doc-id>BCP0001</doc-id>
        </is-also>
        <current-status>PROPOSED STANDARD</current-status>
        <publication-status>PROPOSED STANDARD</publication-status>
        <stream>IETF</stream>
        <area>%(area)s</area>
        <wg_acronym>%(group)s</wg_acronym>
        <errata-url>http://www.rfc-editor.org/errata_search.php?rfc=1234</errata-url>
    </rfc-entry>
</rfc-index>''' % dict(year=today.strftime("%Y"),
                       month=today.strftime("%B"),
                       name=draft_doc.name,
                       rev=draft_doc.rev,
                       area=draft_doc.group.parent.acronym,
                       group=draft_doc.group.acronym)

        errata = [{
                "errata_id":1,
                "doc-id":"RFC123",  # n.b. this is not the same RFC as in the above index XML!
                "errata_status_code":"Verified",
                "errata_type_code":"Editorial",
                "section": "4.1",
                "orig_text":"   S: 220-smtp.example.com ESMTP Server",
                "correct_text":"   S: 220 smtp.example.com ESMTP Server",
                "notes":"There are 3 instances of this (one on p. 7 and two on p. 8). \n",
                "submit_date":"2007-07-19",
                "submitter_name":"Rob Siemborski",
                "verifier_id":99,
                "verifier_name":None,
                "update_date":"2019-09-10 09:09:03"},
        ]

        data = rfceditor.parse_index(io.StringIO(t))
        self.assertEqual(len(data), 1)
        rfc_number, title, authors, rfc_published_date, current_status, updates, updated_by, obsoletes, obsoleted_by, also, draft, has_errata, stream, wg, file_formats, pages, abstract = data[0]

        # currently, we only check what we actually use
        self.assertEqual(rfc_number, 1234)
        self.assertEqual(title, "A Testing RFC")
        self.assertEqual(rfc_published_date.year, today.year)
        self.assertEqual(rfc_published_date.month, today.month)
        self.assertEqual(current_status, "Proposed Standard")
        self.assertEqual(updates, ["RFC123"])
        self.assertEqual(set(also), set(["BCP1", "FYI1", "STD2"]))
        self.assertEqual(draft, draft_doc.name)
        self.assertEqual(wg, draft_doc.group.acronym)
        self.assertEqual(has_errata, True)
        self.assertEqual(stream, "IETF")
        self.assertEqual(pages, "42")
        self.assertEqual(abstract, "This is some interesting text.")

        draft_filename = "%s-%s.txt" % (draft_doc.name, draft_doc.rev)
        self.write_draft_file(draft_filename, 5000)

        event_count_before = draft_doc.docevent_set.count()
        draft_title_before = draft_doc.title
        draft_abstract_before = draft_doc.abstract
        draft_pages_before = draft_doc.pages

        changes = []
        with mock.patch("ietf.sync.rfceditor.log") as mock_log:
            for rfc_number, _, d, rfc_published in rfceditor.update_docs_from_rfc_index(data, errata, today - datetime.timedelta(days=30)):
                changes.append({"doc_pk": d.pk, "rfc_published": rfc_published})  # we ignore the actual change list
                self.assertEqual(rfc_number, 1234)
                if rfc_published:
                    self.assertEqual(d.type_id, "rfc")
                    self.assertEqual(d.rfc_number, rfc_number)
                else:
                    self.assertEqual(d.type_id, "draft")
                    self.assertIsNone(d.rfc_number)
                    
        self.assertFalse(mock_log.called, "No log messages expected")

        draft_doc = Document.objects.get(name=draft_doc.name)
        draft_events = draft_doc.docevent_set.all()
        self.assertEqual(len(draft_events) - event_count_before, 2)
        self.assertEqual(draft_events[0].type, "sync_from_rfc_editor")
        self.assertEqual(draft_events[1].type, "changed_action_holders")
        self.assertEqual(draft_doc.get_state_slug(), "rfc")
        self.assertEqual(draft_doc.get_state_slug("draft-iesg"), "pub")
        self.assertCountEqual(draft_doc.action_holders.all(), [])
        self.assertEqual(draft_doc.title, draft_title_before)
        self.assertEqual(draft_doc.abstract, draft_abstract_before)
        self.assertEqual(draft_doc.pages, draft_pages_before)
        self.assertTrue(not os.path.exists(os.path.join(settings.INTERNET_DRAFT_PATH, draft_filename)))
        self.assertTrue(os.path.exists(os.path.join(settings.INTERNET_DRAFT_ARCHIVE_DIR, draft_filename)))

        rfc_doc = Document.objects.filter(rfc_number=1234, type_id="rfc").first()
        self.assertIsNotNone(rfc_doc, "RFC document should have been created")
        self.assertEqual(rfc_doc.authors(), draft_doc.authors())
        rfc_events = rfc_doc.docevent_set.all()
        self.assertEqual(len(rfc_events), 8)
        expected_events = [
            ["sync_from_rfc_editor", ""], # Not looking for exact desc match here - see detailed tests below
            ["sync_from_rfc_editor", "Imported membership of rfc1234 in std2 via sync to the rfc-index"],
            ["std_history_marker", "No history of STD2 is currently available in the datatracker before this point"],
            ["sync_from_rfc_editor", "Imported membership of rfc1234 in fyi1 via sync to the rfc-index"],
            ["fyi_history_marker", "No history of FYI1 is currently available in the datatracker before this point"],
            ["sync_from_rfc_editor", "Imported membership of rfc1234 in bcp1 via sync to the rfc-index"],
            ["bcp_history_marker", "No history of BCP1 is currently available in the datatracker before this point"],
            ["published_rfc", "RFC published"]
        ]
        for index, [event_type, desc] in enumerate(expected_events):
            self.assertEqual(rfc_events[index].type, event_type)
            if index == 0:
                self.assertIn("Received changes through RFC Editor sync (created document RFC 1234,", rfc_events[0].desc)
                self.assertIn(f"created became rfc relationship between {rfc_doc.came_from_draft().name} and RFC 1234", rfc_events[0].desc)
                self.assertIn("set title to 'A Testing RFC'", rfc_events[0].desc)
                self.assertIn("set abstract to 'This is some interesting text.'", rfc_events[0].desc)
                self.assertIn("set pages to 42", rfc_events[0].desc)
                self.assertIn("set standardization level to Proposed Standard", rfc_events[0].desc)
                self.assertIn(f"added RFC published event at {rfc_events[0].time.astimezone(RPC_TZINFO):%Y-%m-%d}", rfc_events[0].desc)
                self.assertIn("created updates relation between RFC 1234 and RFC 123", rfc_events[0].desc)
                self.assertIn("added Errata tag", rfc_events[0].desc)
            else:
                self.assertEqual(rfc_events[index].desc, desc)
        self.assertEqual(rfc_events[7].time.astimezone(RPC_TZINFO).date(), today)
        for subseries_name in ["bcp1", "fyi1", "std2"]:
            sub = Document.objects.filter(type_id=subseries_name[:3],name=subseries_name).first()
            self.assertIsNotNone(sub, f"{subseries_name} not created")
            self.assertTrue(rfc_doc in sub.contains())
            self.assertTrue(sub in rfc_doc.part_of())
        self.assertEqual(rfc_doc.get_state_slug(), "published")
        # Should have an "errata" tag because there is an errata-url in the index XML, but no "verified-errata" tag
        # because there is no verified item in the errata JSON with doc-id matching the RFC document.
        tag_slugs = rfc_doc.tags.values_list("slug", flat=True)
        self.assertTrue("errata" in tag_slugs)
        self.assertFalse("verified-errata" in tag_slugs)
        # TODO: adjust these when we have subseries document types
        # self.assertTrue(DocAlias.objects.filter(name="rfc1234", docs=rfc_doc))
        # self.assertTrue(DocAlias.objects.filter(name="bcp1", docs=rfc_doc))
        # self.assertTrue(DocAlias.objects.filter(name="fyi1", docs=rfc_doc))
        # self.assertTrue(DocAlias.objects.filter(name="std1", docs=rfc_doc))
        self.assertTrue(RelatedDocument.objects.filter(source=rfc_doc, target__name="rfc123", relationship="updates").exists())
        self.assertTrue(RelatedDocument.objects.filter(source=draft_doc, target=rfc_doc, relationship="became_rfc").exists())
        self.assertEqual(rfc_doc.title, "A Testing RFC")
        self.assertEqual(rfc_doc.abstract, "This is some interesting text.")
        self.assertEqual(rfc_doc.std_level_id, "ps")
        self.assertEqual(rfc_doc.pages, 42)
        self.assertEqual(rfc_doc.stream, draft_doc.stream)
        self.assertEqual(rfc_doc.group, draft_doc.group)
        self.assertEqual(rfc_doc.words, draft_doc.words)
        self.assertEqual(rfc_doc.ad, draft_doc.ad)
        self.assertEqual(rfc_doc.external_url, draft_doc.external_url)
        self.assertEqual(rfc_doc.note, draft_doc.note)

        # check that we got the expected changes
        self.assertEqual(len(changes), 2)
        self.assertEqual(changes[0]["doc_pk"], draft_doc.pk)
        self.assertEqual(changes[0]["rfc_published"], False)
        self.assertEqual(changes[1]["doc_pk"], rfc_doc.pk)
        self.assertEqual(changes[1]["rfc_published"], True)

        # make sure we can apply it again with no changes
        changed = list(rfceditor.update_docs_from_rfc_index(data, errata, today - datetime.timedelta(days=30)))
        self.assertEqual(len(changed), 0)

    def test_rfc_index_subseries_replacement(self):
        today = date_today()
        author = PersonFactory(name="Some Bozo")

        # Start with two BCPs, each containing an rfc
        rfc1, rfc2, rfc3 = RfcFactory.create_batch(3, authors=[author])
        bcp1 = BcpFactory(contains=[rfc1])
        bcp2 = BcpFactory(contains=[rfc2])
        
        def _nameify(doc):
            """Convert a name like 'rfc1' to 'RFC0001"""
            return f"{doc.name[:3].upper()}{int(doc.name[3:]):04d}"

        # RFC index that replaces rfc2 with rfc3 in bcp2
        index_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rfc-index xmlns="http://www.rfc-editor.org/rfc-index"
           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
           xsi:schemaLocation="http://www.rfc-editor.org/rfc-index 
                               http://www.rfc-editor.org/rfc-index.xsd">
    <bcp-entry>
        <doc-id>{_nameify(bcp1)}</doc-id>
        <is-also>
            <doc-id>{_nameify(rfc1)}</doc-id>
        </is-also>
    </bcp-entry>
    <bcp-entry>
        <doc-id>{_nameify(bcp2)}</doc-id>
        <is-also>
            <doc-id>{_nameify(rfc3)}</doc-id>
        </is-also>
    </bcp-entry>
    <rfc-entry>
        <doc-id>{_nameify(rfc1)}</doc-id>
        <title>{rfc1.title}</title>
        <author>
            <name>Some Bozo</name>
        </author>
        <date>
            <month>{today.strftime('%B')}</month>
            <year>{today.strftime('%Y')}</year>
        </date>
        <format>
            <file-format>ASCII</file-format>
        </format>
        <page-count>42</page-count>
        <keywords>
            <kw>test</kw>
        </keywords>
        <abstract><p>This is some interesting text.</p></abstract>
        <is-also>
            <doc-id>{_nameify(bcp1)}</doc-id>
        </is-also>
        <current-status>PROPOSED STANDARD</current-status>
        <publication-status>PROPOSED STANDARD</publication-status>
        <stream>IETF</stream>
    </rfc-entry>
    <rfc-entry>
        <doc-id>{_nameify(rfc2)}</doc-id>
        <title>{rfc2.title}</title>
        <author>
            <name>Some Bozo</name>
        </author>
        <date>
            <month>{today.strftime('%B')}</month>
            <year>{today.strftime('%Y')}</year>
        </date>
        <format>
            <file-format>ASCII</file-format>
        </format>
        <page-count>42</page-count>
        <keywords>
            <kw>test</kw>
        </keywords>
        <abstract><p>This is some interesting text.</p></abstract>
        <current-status>PROPOSED STANDARD</current-status>
        <publication-status>PROPOSED STANDARD</publication-status>
        <stream>IETF</stream>
    </rfc-entry>
    <rfc-entry>
        <doc-id>{_nameify(rfc3)}</doc-id>
        <title>{rfc3.title}</title>
        <author>
            <name>Some Bozo</name>
        </author>
        <date>
            <month>{today.strftime('%B')}</month>
            <year>{today.strftime('%Y')}</year>
        </date>
        <format>
            <file-format>ASCII</file-format>
        </format>
        <page-count>42</page-count>
        <keywords>
            <kw>test</kw>
        </keywords>
        <abstract><p>This is some interesting text.</p></abstract>
        <is-also>
            <doc-id>{_nameify(bcp2)}</doc-id>
        </is-also>
        <current-status>PROPOSED STANDARD</current-status>
        <publication-status>PROPOSED STANDARD</publication-status>
        <stream>IETF</stream>
    </rfc-entry>
</rfc-index>"""
        data = rfceditor.parse_index(io.StringIO(index_xml))  # parse index
        self.assertEqual(len(data), 3)  # check that we parsed 3 RFCs
        # Process the data by consuming the generator
        for _ in rfceditor.update_docs_from_rfc_index(data, []):
            pass
        # Confirm that the expected changes were made
        self.assertCountEqual(rfc1.related_that("contains"), [bcp1])
        self.assertCountEqual(rfc2.related_that("contains"), [])
        self.assertCountEqual(rfc3.related_that("contains"), [bcp2])

    def _generate_rfc_queue_xml(self, draft, state, auth48_url=None):
        """Generate an RFC queue xml string for a draft"""
        t = '''<rfc-editor-queue xmlns="http://www.rfc-editor.org/rfc-editor-queue">
<section name="IETF STREAM: WORKING GROUP STANDARDS TRACK">
<entry xml:id="%(name)s">
<draft>%(name)s-%(rev)s.txt</draft>
<date-received>2010-09-08</date-received>
<state>%(state)s</state>
<auth48-url>%(auth48_url)s</auth48-url>
<normRef>
<ref-name>%(ref)s</ref-name>
<ref-state>IN-QUEUE</ref-state>
</normRef>
<authors>A. Author</authors>
<title>
%(title)s
</title>
<bytes>10000000</bytes>
<source>%(group)s</source>
</entry>
</section>
</rfc-editor-queue>''' % dict(name=draft.name,
                              rev=draft.rev,
                              title=draft.title,
                              group=draft.group.name,
                              ref="draft-ietf-test",
                              state=state,
                              auth48_url=(auth48_url or ''))
        t = t.replace('<auth48-url></auth48-url>\n', '')  # strip empty auth48-url tags
        return t

    def test_rfc_queue(self):
        draft = WgDraftFactory(states=[('draft-iesg','ann')], ad=Person.objects.get(user__username='ad'))
        draft.action_holders.add(draft.ad)  # add an action holder so we can test that it's removed later

        expected_auth48_url = "http://www.rfc-editor.org/auth48/rfc1234"
        t = self._generate_rfc_queue_xml(draft,
                                         state='EDIT*R*A(1G)',
                                         auth48_url=expected_auth48_url)

        drafts, warnings = rfceditor.parse_queue(io.StringIO(t))
        # rfceditor.parse_queue() is tested independently; just sanity check here
        self.assertEqual(len(drafts), 1)
        self.assertEqual(len(warnings), 0)

        mailbox_before = len(outbox)

        changed, warnings = rfceditor.update_drafts_from_queue(drafts)
        self.assertEqual(len(changed), 1)
        self.assertEqual(len(warnings), 0)

        draft = Document.objects.get(pk=draft.pk)
        self.assertEqual(draft.get_state_slug("draft-rfceditor"), "edit")
        self.assertEqual(draft.get_state_slug("draft-iesg"), "rfcqueue")
        self.assertCountEqual(draft.action_holders.all(), [])
        self.assertEqual(set(draft.tags.all()), set(DocTagName.objects.filter(slug__in=("iana", "ref"))))
        events = draft.docevent_set.all()
        self.assertEqual(events[0].type, "changed_state") # changed draft-iesg state
        self.assertEqual(events[1].type, "changed_action_holders")
        self.assertEqual(events[2].type, "changed_state") # changed draft-rfceditor state
        self.assertEqual(events[3].type, "rfc_editor_received_announcement")

        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("RFC Editor queue" in outbox[-1]["Subject"])

        # make sure we can apply it again with no changes
        changed, warnings = rfceditor.update_drafts_from_queue(drafts)
        self.assertEqual(len(changed), 0)
        self.assertEqual(len(warnings), 0)

    def test_rfceditor_parse_queue(self):
        """Test that rfceditor.parse_queue() behaves as expected.

        Currently does a limited test - old comment was 
        "currently, we only check what we actually use".
        """
        draft = WgDraftFactory(states=[('draft-iesg','ann')])
        t = self._generate_rfc_queue_xml(draft,
                                         state='EDIT*R*A(1G)',
                                         auth48_url="http://www.rfc-editor.org/auth48/rfc1234")

        drafts, warnings = rfceditor.parse_queue(io.StringIO(t))
        self.assertEqual(len(drafts), 1)
        self.assertEqual(len(warnings), 0)

        draft_name, date_received, state, tags, missref_generation, stream, auth48, cluster, refs = drafts[0]
        self.assertEqual(draft_name, draft.name)
        self.assertEqual(state, "EDIT")
        self.assertEqual(set(tags), set(["iana", "ref"]))
        self.assertEqual(auth48, "http://www.rfc-editor.org/auth48/rfc1234")

    def test_rfceditor_parse_queue_TI_state(self):
        # Test with TI state introduced 11 Sep 2019
        draft = WgDraftFactory(states=[('draft-iesg','ann')])
        t = self._generate_rfc_queue_xml(draft,
                                         state='TI',
                                         auth48_url="http://www.rfc-editor.org/auth48/rfc1234")
        __, warnings = rfceditor.parse_queue(io.StringIO(t))
        self.assertEqual(len(warnings), 0)

    def _generate_rfceditor_update(self, draft, state, tags=None, auth48_url=None):
        """Helper to generate fake output from rfceditor.parse_queue()"""
        return [[
            draft.name, # draft_name
            '2020-06-03',  # date_received
            state,
            tags or [],
            '1',  # missref_generation
            'ietf',  # stream
            auth48_url or '',
            '',  # cluster
            ['draft-ietf-test'],  # refs
        ]]

    def test_update_draft_auth48_url(self):
        """Test that auth48 URLs are handled correctly."""
        draft = WgDraftFactory(states=[('draft-iesg','ann')])

        # Step 1 setup: update to a state with no auth48 URL
        changed, warnings = rfceditor.update_drafts_from_queue(
            self._generate_rfceditor_update(draft, state='EDIT')
        )
        self.assertEqual(len(changed), 1)
        self.assertEqual(len(warnings), 0)
        auth48_docurl = draft.documenturl_set.filter(tag_id='auth48').first()
        self.assertIsNone(auth48_docurl)

        # Step 2: update to auth48 state with auth48 URL
        changed, warnings = rfceditor.update_drafts_from_queue(
            self._generate_rfceditor_update(draft, state='AUTH48', auth48_url='http://www.rfc-editor.org/rfc1234')
        )
        self.assertEqual(len(changed), 1)
        self.assertEqual(len(warnings), 0)
        auth48_docurl = draft.documenturl_set.filter(tag_id='auth48').first()
        self.assertIsNotNone(auth48_docurl)
        self.assertEqual(auth48_docurl.url, 'http://www.rfc-editor.org/rfc1234')

        # Step 3: update to auth48-done state without auth48 URL
        changed, warnings = rfceditor.update_drafts_from_queue(
            self._generate_rfceditor_update(draft, state='AUTH48-DONE')
        )
        self.assertEqual(len(changed), 1)
        self.assertEqual(len(warnings), 0)
        auth48_docurl = draft.documenturl_set.filter(tag_id='auth48').first()
        self.assertIsNone(auth48_docurl)

    def test_post_approved_draft_in_production_only(self):
        self.requests_mock.post("https://rfceditor.example.com/", status_code=200, text="OK")

        # be careful playing with SERVER_MODE!
        with override_settings(SERVER_MODE="test"):
            self.assertEqual(
                rfceditor.post_approved_draft("https://rfceditor.example.com/", "some-draft"),
                ("", "")
            )
            self.assertFalse(self.requests_mock.called)
        with override_settings(SERVER_MODE="development"):
            self.assertEqual(
                rfceditor.post_approved_draft("https://rfceditor.example.com/", "some-draft"),
                ("", "")
            )
            self.assertFalse(self.requests_mock.called)
        with override_settings(SERVER_MODE="production"):
            self.assertEqual(
                rfceditor.post_approved_draft("https://rfceditor.example.com/", "some-draft"),
                ("", "")
            )
            self.assertTrue(self.requests_mock.called)


class DiscrepanciesTests(TestCase):
    def test_discrepancies(self):

        # draft approved but no RFC Editor state
        doc = Document.objects.create(name="draft-ietf-test1", type_id="draft")
        doc.set_state(State.objects.get(used=True, type="draft-iesg", slug="ann"))

        r = self.client.get(urlreverse("ietf.sync.views.discrepancies"))
        self.assertContains(r, doc.name)

        # draft with IANA state "In Progress" but RFC Editor state not IANA
        doc = Document.objects.create(name="draft-ietf-test2", type_id="draft")
        doc.set_state(State.objects.get(used=True, type="draft-iesg", slug="rfcqueue"))
        doc.set_state(State.objects.get(used=True, type="draft-iana-action", slug="inprog"))
        doc.set_state(State.objects.get(used=True, type="draft-rfceditor", slug="auth"))

        r = self.client.get(urlreverse("ietf.sync.views.discrepancies"))
        self.assertContains(r, doc.name)

        # draft with IANA state "Waiting on RFC Editor" or "RFC-Ed-Ack"
        # but RFC Editor state is IANA
        doc = Document.objects.create(name="draft-ietf-test3", type_id="draft")
        doc.set_state(State.objects.get(used=True, type="draft-iesg", slug="rfcqueue"))
        doc.set_state(State.objects.get(used=True, type="draft-iana-action", slug="waitrfc"))
        doc.set_state(State.objects.get(used=True, type="draft-rfceditor", slug="iana"))

        r = self.client.get(urlreverse("ietf.sync.views.discrepancies"))
        self.assertContains(r, doc.name)

        # draft with state other than "RFC Ed Queue" or "RFC Published"
        # that are in RFC Editor or IANA queues
        doc = Document.objects.create(name="draft-ietf-test4", type_id="draft")
        doc.set_state(State.objects.get(used=True, type="draft-iesg", slug="ann"))
        doc.set_state(State.objects.get(used=True, type="draft-rfceditor", slug="auth"))

        r = self.client.get(urlreverse("ietf.sync.views.discrepancies"))
        self.assertContains(r, doc.name)


class RFCEditorUndoTests(TestCase):
    def test_rfceditor_undo(self):
        draft = WgDraftFactory()

        e1 = add_state_change_event(draft, Person.objects.get(name="(System)"), None,
                                   State.objects.get(used=True, type="draft-rfceditor", slug="auth"))
        e1.desc = "First"
        e1.save()

        e2 = add_state_change_event(draft, Person.objects.get(name="(System)"), None,
                                   State.objects.get(used=True, type="draft-rfceditor", slug="edit"))
        e2.desc = "Second"
        e2.save()
        
        url = urlreverse('ietf.sync.views.rfceditor_undo')
        login_testing_unauthorized(self, "rfc", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, e2.doc.name)

        # delete e2
        deleted_before = DeletedEvent.objects.count()

        r = self.client.post(url, dict(event=e2.id))
        self.assertEqual(r.status_code, 302)

        self.assertEqual(StateDocEvent.objects.filter(id=e2.id).count(), 0)
        self.assertEqual(draft.get_state("draft-rfceditor").slug, "auth")
        self.assertEqual(DeletedEvent.objects.count(), deleted_before + 1)

        # delete e1
        draft.state_cache = None
        r = self.client.post(url, dict(event=e1.id))
        self.assertEqual(draft.get_state("draft-rfceditor"), None)

        # let's just test we can recover
        e = DeletedEvent.objects.all().order_by("-time", "-id")[0]

        e.content_type.model_class().objects.create(**json.loads(e.json))
        self.assertTrue(StateDocEvent.objects.filter(desc="First", doc=draft))


class TaskTests(TestCase):
    @override_settings(
        RFC_EDITOR_INDEX_URL="https://rfc-editor.example.com/index/",
        RFC_EDITOR_ERRATA_JSON_URL="https://rfc-editor.example.com/errata/",
    )
    @mock.patch("ietf.sync.tasks.rfceditor.update_docs_from_rfc_index")
    @mock.patch("ietf.sync.tasks.rfceditor.parse_index")
    @mock.patch("ietf.sync.tasks.requests.get")
    def test_rfc_editor_index_update_task(
        self, requests_get_mock, parse_index_mock, update_docs_mock
    ) -> None:  # the annotation here prevents mypy from complaining about annotation-unchecked
        """rfc_editor_index_update_task calls helpers correctly
        
        This tests that data flow is as expected. Assumes the individual helpers are
        separately tested to function correctly.
        """
        @dataclass
        class MockIndexData:
            """Mock index item that claims to be a specified length"""
            length: int

            def __len__(self):
                return self.length

        @dataclass
        class MockResponse:
            """Mock object that contains text and json() that claims to be a specified length"""
            text: str
            json_length: int = 0

            def json(self):
                return MockIndexData(length=self.json_length)

        # Response objects
        index_response = MockResponse(text="this is the index")
        errata_response = MockResponse(
            text="these are the errata", json_length=rfceditor.MIN_ERRATA_RESULTS
        )
        rfc = RfcFactory()
    
        # Test with full_index = False
        requests_get_mock.side_effect = (index_response, errata_response)  # will step through these
        parse_index_mock.return_value = MockIndexData(length=rfceditor.MIN_INDEX_RESULTS)
        update_docs_mock.return_value = (
            (rfc.rfc_number, ("something changed",), rfc, False),
        )

        tasks.rfc_editor_index_update_task(full_index=False)

        # Check parse_index() call
        self.assertTrue(parse_index_mock.called)
        (parse_index_args, _) = parse_index_mock.call_args
        self.assertEqual(
            parse_index_args[0].read(),  # arg is a StringIO
            "this is the index",
            "parse_index is called with the index text in a StringIO",
        )

        # Check update_docs_from_rfc_index call
        self.assertTrue(update_docs_mock.called)
        (update_docs_args, update_docs_kwargs) = update_docs_mock.call_args
        self.assertEqual(
            update_docs_args, (parse_index_mock.return_value, errata_response.json())
        )
        self.assertIsNotNone(update_docs_kwargs["skip_older_than_date"])

        # Test again with full_index = True
        requests_get_mock.reset_mock()
        parse_index_mock.reset_mock()
        update_docs_mock.reset_mock()
        requests_get_mock.side_effect = (index_response, errata_response)  # will step through these
        tasks.rfc_editor_index_update_task(full_index=True)

        # Check parse_index() call
        self.assertTrue(parse_index_mock.called)
        (parse_index_args, _) = parse_index_mock.call_args
        self.assertEqual(
            parse_index_args[0].read(),  # arg is a StringIO
            "this is the index",
            "parse_index is called with the index text in a StringIO",
        )

        # Check update_docs_from_rfc_index call
        self.assertTrue(update_docs_mock.called)
        (update_docs_args, update_docs_kwargs) = update_docs_mock.call_args
        self.assertEqual(
            update_docs_args, (parse_index_mock.return_value, errata_response.json())
        )
        self.assertIsNone(update_docs_kwargs["skip_older_than_date"])

        # Test error handling
        requests_get_mock.reset_mock()
        parse_index_mock.reset_mock()
        update_docs_mock.reset_mock()
        requests_get_mock.side_effect = requests.Timeout  # timeout on every get()
        tasks.rfc_editor_index_update_task(full_index=False)
        self.assertFalse(parse_index_mock.called)
        self.assertFalse(update_docs_mock.called)
        
        requests_get_mock.reset_mock()
        parse_index_mock.reset_mock()
        update_docs_mock.reset_mock()
        requests_get_mock.side_effect = [index_response, requests.Timeout]  # timeout second get()
        tasks.rfc_editor_index_update_task(full_index=False)
        self.assertFalse(update_docs_mock.called)

        requests_get_mock.reset_mock()
        parse_index_mock.reset_mock()
        update_docs_mock.reset_mock()
        requests_get_mock.side_effect = [index_response, errata_response]
        # feed in an index that is too short
        parse_index_mock.return_value = MockIndexData(length=rfceditor.MIN_INDEX_RESULTS - 1)
        tasks.rfc_editor_index_update_task(full_index=False)
        self.assertTrue(parse_index_mock.called)
        self.assertFalse(update_docs_mock.called)

        requests_get_mock.reset_mock()
        parse_index_mock.reset_mock()
        update_docs_mock.reset_mock()
        requests_get_mock.side_effect = [index_response, errata_response]
        errata_response.json_length = rfceditor.MIN_ERRATA_RESULTS - 1  # too short
        parse_index_mock.return_value = MockIndexData(length=rfceditor.MIN_INDEX_RESULTS)
        tasks.rfc_editor_index_update_task(full_index=False)
        self.assertFalse(update_docs_mock.called)

    @override_settings(RFC_EDITOR_QUEUE_URL="https://rfc-editor.example.com/queue/")
    @mock.patch("ietf.sync.tasks.update_drafts_from_queue")
    @mock.patch("ietf.sync.tasks.parse_queue")
    def test_rfc_editor_queue_updates_task(self, mock_parse, mock_update):
        # test a request timeout
        self.requests_mock.get("https://rfc-editor.example.com/queue/", exc=requests.exceptions.Timeout)
        tasks.rfc_editor_queue_updates_task()
        self.assertFalse(mock_parse.called)
        self.assertFalse(mock_update.called)
        
        # now return a value rather than an exception
        self.requests_mock.get("https://rfc-editor.example.com/queue/", text="the response")

        # mock returning < MIN_QUEUE_RESULTS values - treated as an error, so no update takes place
        mock_parse.return_value = ([n for n in range(rfceditor.MIN_QUEUE_RESULTS - 1)], ["a warning"])
        tasks.rfc_editor_queue_updates_task()
        self.assertEqual(mock_parse.call_count, 1)
        self.assertEqual(mock_parse.call_args[0][0].read(), "the response")
        self.assertFalse(mock_update.called)
        mock_parse.reset_mock()
        
        # mock returning +. MIN_QUEUE_RESULTS - should succeed
        mock_parse.return_value = ([n for n in range(rfceditor.MIN_QUEUE_RESULTS)], ["a warning"])
        mock_update.return_value = ([1,2,3], ["another warning"])
        tasks.rfc_editor_queue_updates_task()
        self.assertEqual(mock_parse.call_count, 1)
        self.assertEqual(mock_parse.call_args[0][0].read(), "the response")
        self.assertEqual(mock_update.call_count, 1)
        self.assertEqual(mock_update.call_args, mock.call([n for n in range(rfceditor.MIN_QUEUE_RESULTS)]))

    @override_settings(IANA_SYNC_CHANGES_URL="https://iana.example.com/sync/")
    @mock.patch("ietf.sync.tasks.iana.update_history_with_changes")
    @mock.patch("ietf.sync.tasks.iana.parse_changes_json")
    @mock.patch("ietf.sync.tasks.iana.fetch_changes_json")
    def test_iana_changes_update_task(
        self, 
        fetch_changes_mock,
        parse_changes_mock,
        update_history_mock,
    ):
        # set up mocks
        fetch_return_val = object()
        fetch_changes_mock.return_value = fetch_return_val
        parse_return_val = object()
        parse_changes_mock.return_value = parse_return_val
        event_with_json = DocEventFactory()
        event_with_json.json = "hi I'm json"
        update_history_mock.return_value = [
            [event_with_json],  # events
            ["oh no!"],  # warnings
        ]
        
        tasks.iana_changes_update_task()
        self.assertEqual(fetch_changes_mock.call_count, 1)
        self.assertEqual(
            fetch_changes_mock.call_args[0][0],
            "https://iana.example.com/sync/",
        )
        self.assertTrue(parse_changes_mock.called)
        self.assertEqual(
            parse_changes_mock.call_args,
            ((fetch_return_val,), {}),
        )
        self.assertTrue(update_history_mock.called)
        self.assertEqual(
            update_history_mock.call_args,
            ((parse_return_val,), {"send_email": True}),
        )

    @override_settings(IANA_SYNC_PROTOCOLS_URL="https://iana.example.com/proto/")
    @mock.patch("ietf.sync.tasks.iana.update_rfc_log_from_protocol_page")
    @mock.patch("ietf.sync.tasks.iana.parse_protocol_page")
    @mock.patch("ietf.sync.tasks.requests.get")
    def test_iana_protocols_update_task(
        self,
        requests_get_mock,
        parse_protocols_mock,
        update_rfc_log_mock,
    ):
        # set up mocks
        requests_get_mock.return_value = mock.Mock(text="fetched response")
        parse_protocols_mock.return_value = range(110)  # larger than batch size of 100
        update_rfc_log_mock.return_value = [
            mock.Mock(display_name=mock.Mock(return_value="name"))
        ]
        
        # call the task
        tasks.iana_protocols_update_task()
        
        # check that it did the right things
        self.assertTrue(requests_get_mock.called)
        self.assertEqual(
            requests_get_mock.call_args[0], 
            ("https://iana.example.com/proto/",),
        )
        self.assertTrue(parse_protocols_mock.called)
        self.assertEqual(
            parse_protocols_mock.call_args[0],
            ("fetched response",),
        )
        self.assertEqual(update_rfc_log_mock.call_count, 2)
        self.assertEqual(
            update_rfc_log_mock.call_args_list[0][0][0],
            range(100),  # first batch
        )
        self.assertEqual(
            update_rfc_log_mock.call_args_list[1][0][0],
            range(100, 110),  # second batch
        )
        # make sure the calls use the same later_than date and that it's the expected one
        published_later_than = set(
            update_rfc_log_mock.call_args_list[n][0][1] for n in (0, 1)
        )
        self.assertEqual(
            published_later_than, 
            {datetime.datetime(2012,11,26,tzinfo=datetime.timezone.utc)}
        )

        # try with an exception
        requests_get_mock.reset_mock()
        parse_protocols_mock.reset_mock()
        update_rfc_log_mock.reset_mock()
        requests_get_mock.side_effect = requests.Timeout

        tasks.iana_protocols_update_task()
        self.assertTrue(requests_get_mock.called)
        self.assertFalse(parse_protocols_mock.called)
        self.assertFalse(update_rfc_log_mock.called)
