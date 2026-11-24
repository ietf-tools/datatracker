# Copyright The IETF Trust 2026, All Rights Reserved

from django.template.loader import render_to_string
from django.urls import reverse
from pyquery import PyQuery

from ietf.doc.factories import WgDraftFactory
from ietf.doc.models import Document
from ietf.group.factories import GroupFactory, RoleFactory
from ietf.group.utils import setup_default_community_list_for_group
from ietf.sync.tasks import process_rpc_queue_task
from ietf.utils.test_utils import TestCase


class RfcEditorQueueStatusLinkTests(TestCase):
    def test_status_links_in_document_lists(self):
        ad = RoleFactory(name_id="ad", group__type_id="area").person
        group = GroupFactory(acronym="finalreviewtest")
        setup_default_community_list_for_group(group)
        draft_prefix = "draft-ietf-finalreviewtest-"
        draft_args = {
            "ad": ad,
            "group": group,
            "states": [("draft", "active"), ("draft-iesg", "rfcqueue")],
        }
        blocked = WgDraftFactory(name=draft_prefix + "blocked", **draft_args)
        final = WgDraftFactory(name=draft_prefix + "final", **draft_args)
        no_review_page = WgDraftFactory(name=draft_prefix + "no-page", **draft_args)
        editing = WgDraftFactory(name=draft_prefix + "editing", **draft_args)

        process_rpc_queue_task([
            {
                "name": blocked.name,
                "assignment_set": [{"role": "final_review_editor"}, {"role": "blocked"}],
                "blocking_reasons": [
                    {"reason": {"name": "Waiting for Action Holder"}},
                    {"reason": {"name": "Final Approval Pending"}},
                ],
                "rfc_number": 99001,
                "final_approval": [{"approved": False}],
            },
            {
                "name": final.name,
                "assignment_set": [{"role": "final_review_editor"}],
                "rfc_number": 99002,
                "final_approval": [{"approved": True}],
            },
            {
                "name": no_review_page.name,
                "assignment_set": [{"role": "final_review_editor"}],
            },
            {
                "name": editing.name,
                "assignment_set": [{"role": "first_editor"}],
                "rfc_number": 99003,
                "final_approval": [{"approved": True}],
            },
        ])

        listings = [
            (reverse("ietf.group.views.group_documents", kwargs={"acronym": group.acronym}), {}),
            (reverse("ietf.doc.views_search.docs_for_ad", kwargs={"name": ad.full_name_as_key()}), {}),
            (reverse("ietf.doc.views_search.search"), {"activedrafts": "on", "name": draft_prefix}),
        ]
        queue = "https://queue.rfc-editor.org"
        blocked_review_url = f"{queue}/final-review/rfc99001/"
        expected = {
            blocked_review_url: (
                "In Final Review. Blocked: Final Approval Pending, Waiting for Action Holder"
            ),
            f"{queue}/final-review/rfc99002/": "In Final Review",
            f"{queue}/#{no_review_page.name}": "In Final Review",
            f"{queue}/#{editing.name}": "In Progress (First Edit)",
        }
        for url, params in listings:
            with self.subTest(url=url):
                response = self.client.get(url, params)
                self.assertEqual(response.status_code, 200)
                queue_links = PyQuery(response.content)(f'td.status a[href^="{queue}/"]')
                self.assertEqual(
                    {link.get("href"): PyQuery(link).text() for link in queue_links},
                    expected,
                )

        status_cell = render_to_string(
            "doc/search/status_columns.html", {"doc": Document.objects.get(pk=blocked.pk)}
        )
        self.assertEqual(
            PyQuery(status_cell)(f'a[href="{blocked_review_url}"]').text(),
            expected[blocked_review_url],
        )
