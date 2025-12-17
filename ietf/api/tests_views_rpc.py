# Copyright The IETF Trust 2025, All Rights Reserved
# -*- coding: utf-8 -*-

from django.conf import settings
from django.db.models import Max
from django.test.utils import override_settings
from django.urls import reverse as urlreverse
from rest_framework.test import APIRequestFactory

from ietf.doc.factories import IndividualDraftFactory
from ietf.doc.models import RelatedDocument, Document
from ietf.utils.test_utils import APITestCase, reload_db_objects


class RpcApiTests(APITestCase):
    @override_settings(APP_API_TOKENS={"ietf.api.views_rpc": ["valid-token"]})
    def test_draftviewset_references(self):
        viewname = "ietf.api.purple_api.draft-references"

        # non-existent draft
        bad_id = Document.objects.aggregate(max_id=Max("id") + 100)["max_id"]
        url = urlreverse(viewname, kwargs={"doc_id": bad_id})
        # Without credentials
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)
        # Add credentials
        r = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(r.status_code, 404)

        # draft without any normative references
        draft = IndividualDraftFactory()
        draft = reload_db_objects(draft)
        url = urlreverse(viewname, kwargs={"doc_id": draft.id})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)
        r = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(r.status_code, 200)
        refs = r.json()
        self.assertEqual(refs, [])

        # draft without any normative references but with an informative reference
        draft_foo = IndividualDraftFactory()
        draft_foo = reload_db_objects(draft_foo)
        RelatedDocument.objects.create(
            source=draft, target=draft_foo, relationship_id="refinfo"
        )
        url = urlreverse(viewname, kwargs={"doc_id": draft.id})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)
        r = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(r.status_code, 200)
        refs = r.json()
        self.assertEqual(refs, [])

        # draft with a normative reference
        draft_bar = IndividualDraftFactory()
        draft_bar = reload_db_objects(draft_bar)
        RelatedDocument.objects.create(
            source=draft, target=draft_bar, relationship_id="refnorm"
        )
        url = urlreverse(viewname, kwargs={"doc_id": draft.id})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)
        r = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(r.status_code, 200)
        refs = r.json()
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["id"], draft_bar.id)
        self.assertEqual(refs[0]["name"], draft_bar.name)
