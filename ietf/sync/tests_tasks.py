# Copyright The IETF Trust 2026, All Rights Reserved

from django.test.utils import override_settings

from ietf.doc.factories import WgDraftFactory
from ietf.doc.models import (
    DocEvent,
    DocTagName,
    Document,
    DocumentURL,
    RpcAssignmentDocEvent,
    State,
)
from ietf.person.models import Person
from ietf.sync import tasks
from ietf.utils.mail import outbox
from ietf.utils.test_utils import TestCase


def _make_entry(
    doc_name, roles=None, blocking_reasons=None, rfc_number=None, final_approval=None
):
    return {
        "name": doc_name,
        "assignment_set": [{"role": r, "state": "in_progress"} for r in (roles or [])],
        "blocking_reasons": blocking_reasons or [],
        "rfc_number": rfc_number,
        "final_approval": final_approval or [],
    }


class ProcessRpcQueueTaskTests(TestCase):
    def setUp(self):
        super().setUp()
        self.system = Person.objects.get(name="(System)")

    # --- Unknown document --------------------------------------------------------

    def test_unknown_document_is_skipped(self):
        """Entries with unknown doc names are logged and skipped without raising."""
        tasks.process_rpc_queue_task([_make_entry("draft-does-not-exist")])
        self.assertFalse(Document.objects.filter(name="draft-does-not-exist").exists())

    # --- First-arrival announcement ----------------------------------------------

    def test_first_arrival_fires_announcement(self):
        """Fires rfc_editor_received_announcement and email on first arrival."""
        draft = WgDraftFactory(states=[("draft-iesg", "ann")])
        mailbox_before = len(outbox)

        tasks.process_rpc_queue_task([_make_entry(draft.name, roles=["first_editor"])])

        draft = Document.objects.get(pk=draft.pk)
        self.assertEqual(draft.get_state_slug("draft-iesg"), "rfcqueue")
        self.assertTrue(
            draft.docevent_set.filter(type="rfc_editor_received_announcement").exists()
        )
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertIn("RFC Editor queue", outbox[-1]["Subject"])
        self.assertIn("iesg-secretary@ietf.org", outbox[-1]["To"])

    def test_first_arrival_skipped_if_rfceditor_state_exists(self):
        """No announcement when doc already has a draft-rfceditor state."""
        draft = WgDraftFactory(states=[("draft-iesg", "ann")])
        draft.set_state(
            State.objects.get(used=True, type="draft-rfceditor", slug="in_progress")
        )
        mailbox_before = len(outbox)

        tasks.process_rpc_queue_task([_make_entry(draft.name, roles=["first_editor"])])

        self.assertFalse(
            draft.docevent_set.filter(type="rfc_editor_received_announcement").exists()
        )
        self.assertEqual(len(outbox), mailbox_before)

    def test_first_arrival_skipped_if_announcement_event_exists(self):
        """No duplicate announcement when rfc_editor_received_announcement already exists."""
        draft = WgDraftFactory(states=[("draft-iesg", "ann")])
        DocEvent.objects.create(
            doc=draft,
            rev=draft.rev,
            by=self.system,
            type="rfc_editor_received_announcement",
            desc="Announcement was received by RFC Editor",
        )
        mailbox_before = len(outbox)

        tasks.process_rpc_queue_task([_make_entry(draft.name)])

        self.assertEqual(
            draft.docevent_set.filter(type="rfc_editor_received_announcement").count(),
            1,
        )
        self.assertEqual(len(outbox), mailbox_before)

    def test_first_arrival_skipped_if_not_ann_iesg_state(self):
        """No announcement when IESG state is not 'ann'."""
        draft = WgDraftFactory(states=[("draft-iesg", "rfcqueue")])
        mailbox_before = len(outbox)

        tasks.process_rpc_queue_task([_make_entry(draft.name, roles=["first_editor"])])

        self.assertFalse(
            draft.docevent_set.filter(type="rfc_editor_received_announcement").exists()
        )
        self.assertEqual(len(outbox), mailbox_before)

    # --- draft-rfceditor state transitions ---------------------------------------

    def test_sets_in_progress_state(self):
        """Non-blocked assignment results in in_progress draft-rfceditor state."""
        draft = WgDraftFactory()

        tasks.process_rpc_queue_task([_make_entry(draft.name, roles=["first_editor"])])

        draft = Document.objects.get(pk=draft.pk)
        self.assertEqual(draft.get_state_slug("draft-rfceditor"), "in_progress")

    def test_sets_blocked_state(self):
        """Assignment with role='blocked' results in blocked draft-rfceditor state."""
        draft = WgDraftFactory()

        tasks.process_rpc_queue_task(
            [
                {
                    "name": draft.name,
                    "assignment_set": [{"role": "blocked", "state": "in_progress"}],
                    "blocking_reasons": [],
                    "rfc_number": None,
                    "final_approval": [],
                }
            ]
        )

        draft = Document.objects.get(pk=draft.pk)
        self.assertEqual(draft.get_state_slug("draft-rfceditor"), "blocked")

    def test_no_state_change_event_when_state_unchanged(self):
        """No state-change DocEvent created when draft-rfceditor state is already correct."""
        draft = WgDraftFactory(states=[("draft-rfceditor", "in_progress")])
        events_before = draft.docevent_set.filter(type="changed_state").count()

        tasks.process_rpc_queue_task([_make_entry(draft.name, roles=["first_editor"])])

        self.assertEqual(
            draft.docevent_set.filter(type="changed_state").count(), events_before
        )

    def test_state_change_event_created_on_transition(self):
        """State-change DocEvent is created when draft-rfceditor state changes."""
        draft = WgDraftFactory(states=[("draft-rfceditor", "in_progress")])

        tasks.process_rpc_queue_task(
            [
                {
                    "name": draft.name,
                    "assignment_set": [{"role": "blocked", "state": "in_progress"}],
                    "blocking_reasons": [],
                    "rfc_number": None,
                    "final_approval": [],
                }
            ]
        )

        self.assertTrue(draft.docevent_set.filter(type="changed_state").exists())
        draft = Document.objects.get(pk=draft.pk)
        self.assertEqual(draft.get_state_slug("draft-rfceditor"), "blocked")

    # --- RpcAssignmentDocEvent ---------------------------------------------------

    def test_creates_assignment_event_on_first_update(self):
        """Creates RpcAssignmentDocEvent when no prior event exists."""
        draft = WgDraftFactory()

        tasks.process_rpc_queue_task(
            [_make_entry(draft.name, roles=["first_editor", "second_editor"])]
        )

        event = draft.latest_event(
            RpcAssignmentDocEvent, type="changed_rpc_assignments"
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.assignments, "first_editor, second_editor")

    def test_no_assignment_event_when_unchanged(self):
        """No new RpcAssignmentDocEvent when assignments match the last recorded ones."""
        draft = WgDraftFactory()
        RpcAssignmentDocEvent.objects.create(
            doc=draft,
            rev=draft.rev,
            by=self.system,
            type="changed_rpc_assignments",
            assignments="first_editor",
            desc="RPC status changed to first_editor",
        )
        events_before = RpcAssignmentDocEvent.objects.filter(doc=draft).count()

        tasks.process_rpc_queue_task([_make_entry(draft.name, roles=["first_editor"])])

        self.assertEqual(
            RpcAssignmentDocEvent.objects.filter(doc=draft).count(), events_before
        )

    def test_assignment_desc_includes_previous_assignments(self):
        """Assignment event desc includes previous assignments when they exist."""
        draft = WgDraftFactory()
        RpcAssignmentDocEvent.objects.create(
            doc=draft,
            rev=draft.rev,
            by=self.system,
            type="changed_rpc_assignments",
            assignments="first_editor",
            desc="RPC status changed to first_editor",
        )

        tasks.process_rpc_queue_task([_make_entry(draft.name, roles=["second_editor"])])

        event = draft.latest_event(
            RpcAssignmentDocEvent, type="changed_rpc_assignments"
        )
        self.assertIn("from first_editor", event.desc)

    def test_blocking_reasons_appended_to_assignments(self):
        """Blocking reason names are appended after ':' in the assignment string, sorted."""
        draft = WgDraftFactory()

        tasks.process_rpc_queue_task(
            [
                {
                    "name": draft.name,
                    "assignment_set": [{"role": "blocked", "state": "in_progress"}],
                    "blocking_reasons": [
                        {"reason": {"name": "missing reference"}},
                    ],
                    "rfc_number": None,
                    "final_approval": [],
                }
            ]
        )

        event = draft.latest_event(
            RpcAssignmentDocEvent, type="changed_rpc_assignments"
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.assignments, "blocked: missing reference")

    def test_roles_sorted_in_assignment_string(self):
        """Roles are sorted alphabetically in the assignment string."""
        draft = WgDraftFactory()

        tasks.process_rpc_queue_task(
            [_make_entry(draft.name, roles=["second_editor", "first_editor"])]
        )

        event = draft.latest_event(
            RpcAssignmentDocEvent, type="changed_rpc_assignments"
        )
        self.assertEqual(event.assignments, "first_editor, second_editor")

    def test_empty_roles_uses_awaiting_editor_assignment(self):
        """Empty assignment_set records 'Awaiting Editor Assignment' rather than an empty string."""
        draft = WgDraftFactory()

        tasks.process_rpc_queue_task([_make_entry(draft.name)])

        event = draft.latest_event(
            RpcAssignmentDocEvent, type="changed_rpc_assignments"
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.assignments, "Awaiting Editor Assignment")

    # --- DocumentURL (auth48) handling -------------------------------------------

    @override_settings(RFC_EDITOR_QUEUE_SITE_BASE_URL="https://queue.example.com")
    def test_auth48_url_created_on_final_approval(self):
        """auth48 DocumentURL is created when final_approval is truthy and rfc_number is set."""
        draft = WgDraftFactory()

        tasks.process_rpc_queue_task(
            [
                {
                    "name": draft.name,
                    "assignment_set": [
                        {"role": "first_editor", "state": "in_progress"}
                    ],
                    "blocking_reasons": [],
                    "rfc_number": 9999,
                    "final_approval": [{"approved": True}],
                }
            ]
        )

        url_obj = draft.documenturl_set.filter(tag_id="auth48").first()
        self.assertIsNotNone(url_obj)
        self.assertEqual(url_obj.url, "https://queue.example.com/final-review/rfc9999/")

    @override_settings(RFC_EDITOR_QUEUE_SITE_BASE_URL="https://queue.example.com")
    def test_auth48_url_not_created_without_rfc_number(self):
        """No auth48 URL created when rfc_number is None even if final_approval is set."""
        draft = WgDraftFactory()

        tasks.process_rpc_queue_task(
            [
                {
                    "name": draft.name,
                    "assignment_set": [
                        {"role": "first_editor", "state": "in_progress"}
                    ],
                    "blocking_reasons": [],
                    "rfc_number": None,
                    "final_approval": [{"approved": True}],
                }
            ]
        )

        self.assertFalse(draft.documenturl_set.filter(tag_id="auth48").exists())

    @override_settings(RFC_EDITOR_QUEUE_SITE_BASE_URL="https://queue.example.com")
    def test_auth48_url_deleted_when_final_approval_cleared(self):
        """Existing auth48 URL is deleted whenever final_approval is empty, regardless of whether assignments changed."""
        draft = WgDraftFactory()
        DocumentURL.objects.create(
            doc=draft,
            tag_id="auth48",
            url="https://queue.example.com/final-review/rfc9999/",
        )
        RpcAssignmentDocEvent.objects.create(
            doc=draft,
            rev=draft.rev,
            by=self.system,
            type="changed_rpc_assignments",
            assignments="old_editor",
            desc="RPC status changed to old_editor",
        )

        tasks.process_rpc_queue_task([_make_entry(draft.name, roles=["first_editor"])])

        self.assertFalse(draft.documenturl_set.filter(tag_id="auth48").exists())

    @override_settings(RFC_EDITOR_QUEUE_SITE_BASE_URL="https://queue.example.com")
    def test_auth48_url_updated_when_rfc_number_changes(self):
        """auth48 URL is updated whenever final_approval and rfc_number are set, regardless of whether assignments changed."""
        draft = WgDraftFactory()
        DocumentURL.objects.create(
            doc=draft,
            tag_id="auth48",
            url="https://queue.example.com/final-review/rfc8888/",
        )
        RpcAssignmentDocEvent.objects.create(
            doc=draft,
            rev=draft.rev,
            by=self.system,
            type="changed_rpc_assignments",
            assignments="old_editor",
            desc="RPC status changed to old_editor",
        )

        tasks.process_rpc_queue_task(
            [
                {
                    "name": draft.name,
                    "assignment_set": [
                        {"role": "first_editor", "state": "in_progress"}
                    ],
                    "blocking_reasons": [],
                    "rfc_number": 9999,
                    "final_approval": [{"approved": True}],
                }
            ]
        )

        url_obj = draft.documenturl_set.filter(tag_id="auth48").first()
        self.assertIsNotNone(url_obj)
        self.assertEqual(url_obj.url, "https://queue.example.com/final-review/rfc9999/")

    @override_settings(RFC_EDITOR_QUEUE_SITE_BASE_URL="https://queue.example.com")
    def test_auth48_url_created_when_assignments_unchanged(self):
        """auth48 URL is created even when assignments have not changed."""
        draft = WgDraftFactory()
        RpcAssignmentDocEvent.objects.create(
            doc=draft,
            rev=draft.rev,
            by=self.system,
            type="changed_rpc_assignments",
            assignments="first_editor",
            desc="RPC status changed to first_editor",
        )

        tasks.process_rpc_queue_task(
            [
                {
                    "name": draft.name,
                    "assignment_set": [
                        {"role": "first_editor", "state": "in_progress"}
                    ],
                    "blocking_reasons": [],
                    "rfc_number": 9999,
                    "final_approval": [{"approved": True}],
                }
            ]
        )

        url_obj = draft.documenturl_set.filter(tag_id="auth48").first()
        self.assertIsNotNone(url_obj)
        self.assertEqual(url_obj.url, "https://queue.example.com/final-review/rfc9999/")

    @override_settings(RFC_EDITOR_QUEUE_SITE_BASE_URL="https://queue.example.com")
    def test_auth48_url_deleted_when_assignments_unchanged(self):
        """Existing auth48 URL is deleted even when assignments have not changed."""
        draft = WgDraftFactory()
        DocumentURL.objects.create(
            doc=draft,
            tag_id="auth48",
            url="https://queue.example.com/final-review/rfc9999/",
        )
        RpcAssignmentDocEvent.objects.create(
            doc=draft,
            rev=draft.rev,
            by=self.system,
            type="changed_rpc_assignments",
            assignments="first_editor",
            desc="RPC status changed to first_editor",
        )

        tasks.process_rpc_queue_task([_make_entry(draft.name, roles=["first_editor"])])

        self.assertFalse(draft.documenturl_set.filter(tag_id="auth48").exists())

    # --- Tag handling ------------------------------------------------------------

    def test_removes_iana_and_ref_tags_from_queued_docs(self):
        """iana and ref tags are removed from documents in the queue."""
        iana_tag = DocTagName.objects.get(slug="iana")
        ref_tag = DocTagName.objects.get(slug="ref")
        draft = WgDraftFactory()
        draft.tags.add(iana_tag, ref_tag)

        tasks.process_rpc_queue_task([_make_entry(draft.name)])

        draft = Document.objects.get(pk=draft.pk)
        self.assertNotIn(iana_tag, draft.tags.all())
        self.assertNotIn(ref_tag, draft.tags.all())

    # --- Cleanup of docs no longer in queue --------------------------------------

    def test_unsets_rfceditor_state_for_docs_not_in_queue(self):
        """Documents with draft-rfceditor state but absent from the queue have that state cleared."""
        draft = WgDraftFactory(states=[("draft-rfceditor", "in_progress")])

        tasks.process_rpc_queue_task([])

        draft = Document.objects.get(pk=draft.pk)
        self.assertIsNone(draft.get_state("draft-rfceditor"))

    def test_removes_tags_from_docs_not_in_queue(self):
        """iana and ref tags are removed from docs with rfceditor state not in the queue."""
        iana_tag = DocTagName.objects.get(slug="iana")
        ref_tag = DocTagName.objects.get(slug="ref")
        draft = WgDraftFactory(states=[("draft-rfceditor", "in_progress")])
        draft.tags.add(iana_tag, ref_tag)

        tasks.process_rpc_queue_task([])

        draft = Document.objects.get(pk=draft.pk)
        self.assertNotIn(iana_tag, draft.tags.all())
        self.assertNotIn(ref_tag, draft.tags.all())

    def test_docs_in_queue_retain_rfceditor_state(self):
        """Documents present in the queue keep their draft-rfceditor state."""
        draft = WgDraftFactory(states=[("draft-rfceditor", "in_progress")])

        tasks.process_rpc_queue_task([_make_entry(draft.name, roles=["first_editor"])])

        draft = Document.objects.get(pk=draft.pk)
        self.assertIsNotNone(draft.get_state("draft-rfceditor"))
