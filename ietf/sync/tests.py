# Copyright The IETF Trust 2012-2026, All Rights Reserved

import json
import datetime
from unittest import mock
import quopri
import requests

from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.urls import reverse as urlreverse
from django.utils import timezone
from django.test.utils import override_settings

import debug                            # pyflakes:ignore

from ietf.api.views import EmailIngestionError
from ietf.doc.factories import (
    WgDraftFactory,
    RfcFactory,
    DocEventFactory,
    WgRfcFactory,
)
from ietf.doc.models import (
    Document,
    DocEvent,
    DeletedEvent,
    DocTagName,
    State,
    StateDocEvent,
)
from ietf.doc.utils import add_state_change_event
from ietf.person.factories import PersonFactory
from ietf.person.models import Person
from ietf.sync import iana, tasks
from ietf.sync.errata import (
    update_errata_from_rfceditor,
    get_errata_last_updated,
    get_errata_data,
    errata_map_from_json,
    update_errata_dirty_time,
    mark_errata_as_processed,
    update_errata_tags,
)
from ietf.sync.tasks import update_errata_from_rfceditor_task
from ietf.utils.mail import outbox, empty_outbox
from ietf.utils.models import DirtyBits
from ietf.utils.test_utils import login_testing_unauthorized
from ietf.utils.test_utils import TestCase


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
                        self.assertEqual(review_time, datetime.datetime(2012, 5, 10, 12, 0, rtime, tzinfo=datetime.UTC))
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
            datetime.datetime.now(tz=datetime.UTC),
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


class ErrataTests(TestCase):
    @override_settings(ERRATA_JSON_BLOB_NAME="myblob.json")
    def test_get_errata_last_update(self):
        red_bucket = storages["red_bucket"]  # InMemoryStorage in test
        red_bucket.save("myblob.json", ContentFile("file"))
        self.assertEqual(
            get_errata_last_updated(), red_bucket.get_modified_time("myblob.json")
        )
    
    @override_settings(ERRATA_JSON_BLOB_NAME="myblob.json")
    def test_get_errata_data(self):
        red_bucket = storages["red_bucket"]  # InMemoryStorage in test
        red_bucket.save("myblob.json", ContentFile('[{"value": 3}]'))
        self.assertEqual(
            get_errata_data(),
            [{"value": 3}],
        )

    def test_errata_map_from_json(self):
        input_data = [
            {
                "doc-id": "not-an-rfc",
                "errata_status_code": "Verified",
            },
            {
                "doc-id": "rfc01234",
                "errata_status_code": "Reported",
            },
            {
                "doc-id": "RFC1001",
                "errata_status_code": "Verified"
            },
            {
                "doc-id": "RfC1234",
                "errata_status_code": "Verified",
            },
        ]
        expected_output = {1001: [input_data[2]], 1234: [input_data[1], input_data[3]]}
        self.assertDictEqual(errata_map_from_json(input_data), expected_output)

    @mock.patch("ietf.sync.errata.update_errata_tags")
    @mock.patch("ietf.sync.errata.get_errata_data")
    def test_update_errata_from_rfceditor(self, mock_get_data, mock_update):
        fake_data = object()
        fake_changed = {1234, 5678}
        mock_get_data.return_value = fake_data
        mock_update.return_value = fake_changed
        result = update_errata_from_rfceditor()
        self.assertTrue(mock_get_data.called)
        self.assertTrue(mock_update.called)
        self.assertEqual(mock_update.call_args, mock.call(fake_data))
        self.assertEqual(result, fake_changed)

    def test_update_errata_tags(self):
        tag_has_errata = DocTagName.objects.get(slug="errata")
        tag_has_verified_errata = DocTagName.objects.get(slug="verified-errata")

        rfcs = WgRfcFactory.create_batch(10)
        rfcs[0].tags.set([tag_has_errata])
        rfcs[1].tags.set([tag_has_errata, tag_has_verified_errata])
        rfcs[2].tags.set([tag_has_errata])
        rfcs[3].tags.set([tag_has_errata, tag_has_verified_errata])
        rfcs[4].tags.set([tag_has_errata])
        rfcs[5].tags.set([tag_has_errata, tag_has_verified_errata])

        # Only contains the fields we care about, not the full JSON
        errata_data = [
            # rfcs[0] had errata and should keep it
            {"doc-id": rfcs[0].name, "errata_status_code": "Held for Document Update"},
            {"doc-id": rfcs[0].name, "errata_status_code": "Rejected"},
            # rfcs[1] had errata+verified-errata and should keep both
            {"doc-id": rfcs[1].name, "errata_status_code": "Verified"},
            # rfcs[2] had errata and should gain verified-errata
            {"doc-id": rfcs[2].name, "errata_status_code": "Verified"},
            # rfcs[3] had errata+verified errata and should lose both
            {"doc-id": rfcs[3].name, "errata_status_code": "Rejected"},
            # rfcs[4] had errata and should gain verified-errata
            {"doc-id": rfcs[4].name, "errata_status_code": "Verified"},
            {"doc-id": rfcs[4].name, "errata_status_code": "Reported"},
            # rfcs[5] had errata+verified-errata and should lose verified-errata
            {"doc-id": rfcs[5].name, "errata_status_code": "Reported"},
            # rfcs[6] had none and should gain errata
            {"doc-id": rfcs[6].name, "errata_status_code": "Reported"},
            # rfcs[7] had none and should gain errata+verified-errata
            {"doc-id": rfcs[7].name, "errata_status_code": "Verified"},
            # rfcs[8] had none and it should stay that way
            {"doc-id": rfcs[8].name, "errata_status_code": "Rejected"},
            # rfcs[9] had none and it should stay that way (no entry at all)
        ]
        changed = update_errata_tags(errata_data)

        self.assertCountEqual(rfcs[0].tags.all(), [tag_has_errata])
        self.assertIsNone(rfcs[0].docevent_set.first())  # no change

        self.assertCountEqual(
            rfcs[1].tags.all(), [tag_has_errata, tag_has_verified_errata]
        )
        self.assertIsNone(rfcs[1].docevent_set.first())  # no change

        self.assertCountEqual(
            rfcs[2].tags.all(), [tag_has_errata, tag_has_verified_errata]
        )
        self.assertEqual(rfcs[2].docevent_set.count(), 1)
        self.assertIn(": added verified-errata tag", rfcs[2].docevent_set.first().desc)

        self.assertCountEqual(rfcs[3].tags.all(), [])
        self.assertEqual(rfcs[3].docevent_set.count(), 1)
        self.assertIn(
            ": removed errata tag, removed verified-errata tag (all errata rejected)",
            rfcs[3].docevent_set.first().desc,
        )

        self.assertCountEqual(
            rfcs[4].tags.all(), [tag_has_errata, tag_has_verified_errata]
        )
        self.assertEqual(rfcs[4].docevent_set.count(), 1)
        self.assertIn(": added verified-errata tag", rfcs[4].docevent_set.first().desc)

        self.assertCountEqual(rfcs[5].tags.all(), [tag_has_errata])
        self.assertEqual(rfcs[5].docevent_set.count(), 1)
        self.assertIn(
            ": removed verified-errata tag", rfcs[5].docevent_set.first().desc
        )

        self.assertCountEqual(rfcs[6].tags.all(), [tag_has_errata])
        self.assertEqual(rfcs[6].docevent_set.count(), 1)
        self.assertIn(": added errata tag", rfcs[6].docevent_set.first().desc)

        self.assertCountEqual(
            rfcs[7].tags.all(), [tag_has_errata, tag_has_verified_errata]
        )
        self.assertEqual(rfcs[7].docevent_set.count(), 1)
        self.assertIn(
            ": added errata tag, added verified-errata tag",
            rfcs[7].docevent_set.first().desc,
        )

        self.assertCountEqual(rfcs[8].tags.all(), [])
        self.assertIsNone(rfcs[8].docevent_set.first())  # no change

        self.assertCountEqual(rfcs[9].tags.all(), [])
        self.assertIsNone(rfcs[9].docevent_set.first())  # no change

        # return value: only RFCs whose tags actually changed
        # rfcs[0], rfcs[1], rfcs[8], rfcs[9] had no tag changes
        for unchanged_rfc in (rfcs[0], rfcs[1], rfcs[8], rfcs[9]):
            self.assertNotIn(unchanged_rfc.rfc_number, changed)
        # rfcs[2..7] had tag changes
        for changed_rfc in rfcs[2:8]:
            self.assertIn(changed_rfc.rfc_number, changed)

    @override_settings(ERRATA_JSON_BLOB_NAME="myblob.json")
    @mock.patch("ietf.sync.errata.get_errata_last_updated")
    def test_update_errata_dirty_time(self, mock_last_updated):
        ERRATA_SLUG = DirtyBits.Slugs.ERRATA
        
        # No time available
        mock_last_updated.side_effect = FileNotFoundError
        self.assertIsNone(DirtyBits.objects.filter(slug=ERRATA_SLUG).first())
        self.assertIsNone(update_errata_dirty_time())  # no blob yet
        self.assertIsNone(DirtyBits.objects.filter(slug=ERRATA_SLUG).first())

        # Now set a time
        first_timestamp = timezone.now() - datetime.timedelta(hours=3)
        mock_last_updated.return_value = first_timestamp
        mock_last_updated.side_effect = None
        result = update_errata_dirty_time()
        self.assertTrue(isinstance(result, DirtyBits))
        result.refresh_from_db()
        self.assertEqual(result.slug, ERRATA_SLUG)
        self.assertEqual(result.processed_time, None)
        self.assertEqual(result.dirty_time, first_timestamp)
        
        # Update the time
        second_timestamp = timezone.now()
        mock_last_updated.return_value = second_timestamp
        second_result = update_errata_dirty_time()
        self.assertEqual(result.pk, second_result.pk)  # should be the same record
        result.refresh_from_db()
        self.assertEqual(result.slug, ERRATA_SLUG)
        self.assertEqual(result.processed_time, None)
        self.assertEqual(result.dirty_time, second_timestamp)

    def test_mark_errata_as_processed(self):
        ERRATA_SLUG = DirtyBits.Slugs.ERRATA
        first_timestamp = timezone.now()
        mark_errata_as_processed(first_timestamp)  # no DirtyBits is not an error
        self.assertIsNone(DirtyBits.objects.filter(slug=ERRATA_SLUG).first())
        dbits = DirtyBits.objects.create(slug=ERRATA_SLUG, dirty_time=first_timestamp)
        second_timestamp = timezone.now()
        mark_errata_as_processed(second_timestamp)
        dbits.refresh_from_db()
        self.assertEqual(dbits.dirty_time, first_timestamp)
        self.assertEqual(dbits.processed_time, second_timestamp)
        

class TaskTests(TestCase):
    
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
            {datetime.datetime(2012,11,26,tzinfo=datetime.UTC)}
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

    @mock.patch("ietf.sync.tasks.rsync_helper")
    @mock.patch("ietf.sync.tasks.load_rfcs_into_blobdb")
    @mock.patch("ietf.sync.tasks.rebuild_reference_relations_task.delay")
    def test_rsync_rfcs_from_rfceditor_task(
        self,
        rebuild_relations_mock,
        load_blobs_mock,
        rsync_helper_mock,
    ):
        tasks.rsync_rfcs_from_rfceditor_task([12345, 54321])
        self.assertTrue(rsync_helper_mock.called)
        self.assertTrue(load_blobs_mock.called)
        load_blobs_args, load_blobs_kwargs = load_blobs_mock.call_args
        self.assertEqual(load_blobs_args, ([12345, 54321],))
        self.assertEqual(load_blobs_kwargs, {})
        self.assertTrue(rebuild_relations_mock.called)
        rebuild_args, rebuild_kwargs = rebuild_relations_mock.call_args
        self.assertEqual(rebuild_args, (["rfc12345", "rfc54321"],))
        self.assertEqual(rebuild_kwargs, {})

    @mock.patch("ietf.sync.tasks.load_rfcs_into_blobdb")
    def test_load_rfcs_into_blobdb_task(
        self,
        load_blobs_mock,
    ):
        tasks.load_rfcs_into_blobdb_task(5, 3)
        self.assertFalse(load_blobs_mock.called)
        load_blobs_mock.reset_mock()
        tasks.load_rfcs_into_blobdb_task(-1, 1)
        self.assertTrue(load_blobs_mock.called)
        mock_args, mock_kwargs = load_blobs_mock.call_args
        self.assertEqual(mock_args, ([1],))
        self.assertEqual(mock_kwargs, {})
        load_blobs_mock.reset_mock()
        tasks.load_rfcs_into_blobdb_task(10999, 50000)
        self.assertTrue(load_blobs_mock.called)
        mock_args, mock_kwargs = load_blobs_mock.call_args
        self.assertEqual(mock_args, ([10999, 11000],))
        self.assertEqual(mock_kwargs, {})
        load_blobs_mock.reset_mock()
        tasks.load_rfcs_into_blobdb_task(3261, 3263)
        self.assertTrue(load_blobs_mock.called)
        mock_args, mock_kwargs = load_blobs_mock.call_args
        self.assertEqual(mock_args, ([3261, 3262, 3263],))
        self.assertEqual(mock_kwargs, {})

    @mock.patch("ietf.sync.tasks.update_rfc_json_task.delay")
    @mock.patch("ietf.sync.tasks.update_errata_from_rfceditor")
    @mock.patch("ietf.sync.tasks.mark_rfcindex_as_dirty")
    @mock.patch("ietf.sync.tasks.mark_errata_as_processed")
    @mock.patch("ietf.sync.tasks.errata_are_dirty")
    def test_update_errata_from_rfceditor_task(
        self,
        mock_errata_are_dirty,
        mock_mark_errata_processed,
        mock_mark_rfcindex_dirty,
        mock_update,
        mock_rfc_json_delay,
    ):
        mock_errata_are_dirty.return_value = False
        update_errata_from_rfceditor_task()
        self.assertTrue(mock_errata_are_dirty.called)
        self.assertFalse(mock_mark_errata_processed.called)
        self.assertFalse(mock_mark_rfcindex_dirty.called)
        self.assertFalse(mock_update.called)

        mock_errata_are_dirty.reset_mock()
        mock_errata_are_dirty.return_value = True
        update_errata_from_rfceditor_task()
        self.assertTrue(mock_errata_are_dirty.called)
        self.assertTrue(mock_mark_errata_processed.called)
        self.assertTrue(mock_mark_rfcindex_dirty.called)
        self.assertTrue(mock_update.called)
