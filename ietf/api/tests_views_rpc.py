# Copyright The IETF Trust 2025, All Rights Reserved
# -*- coding: utf-8 -*-

from django.test.utils import override_settings
from django.urls import reverse as urlreverse

from ietf.doc.factories import IndividualDraftFactory
from ietf.doc.models import RelatedDocument
from ietf.utils.test_utils import TestCase, reload_db_objects


class RpcApiTests(TestCase):
    @override_settings(APP_API_TOKENS={"ietf.api.views_rpc": ["valid-token"]})
    def test_api_refs(self):
        # non-existent draft
        url = urlreverse("ietf.api.views_rpc.rpc_draft_refs", kwargs={"doc_id": 999999})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        r = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        jsondata = r.json()
        refs = jsondata["references"]
        self.assertEqual(refs, [])

        # draft without any nominative references
        draft = IndividualDraftFactory()
        draft = reload_db_objects(draft)
        url = urlreverse(
            "ietf.api.views_rpc.rpc_draft_refs", kwargs={"doc_id": draft.id}
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        r = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        jsondata = r.json()
        refs = jsondata["references"]
        self.assertEqual(refs, [])

        # draft without any nominative references but with an informative reference
        draft_foo = IndividualDraftFactory()
        draft_foo = reload_db_objects(draft_foo)
        RelatedDocument.objects.create(
            source=draft, target=draft_foo, relationship_id="refinfo"
        )
        url = urlreverse(
            "ietf.api.views_rpc.rpc_draft_refs", kwargs={"doc_id": draft.id}
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        r = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        jsondata = r.json()
        refs = jsondata["references"]
        self.assertEqual(refs, [])

        # draft with a nominative reference
        draft_bar = IndividualDraftFactory()
        draft_bar = reload_db_objects(draft_bar)
        RelatedDocument.objects.create(
            source=draft, target=draft_bar, relationship_id="refnorm"
        )
        url = urlreverse(
            "ietf.api.views_rpc.rpc_draft_refs", kwargs={"doc_id": draft.id}
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        r = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        jsondata = r.json()
        refs = jsondata["references"]
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["id"], draft_bar.id)
        self.assertEqual(refs[0]["name"], draft_bar.name)
