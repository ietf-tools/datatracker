# Copyright The IETF Trust 2026, All Rights Reserved

from django.conf import settings
from django.urls import reverse as urlreverse

from pyquery import PyQuery

from ietf.doc.factories import WgRfcFactory
from ietf.utils.test_utils import TestCase


class RfcEditorSourceButtonTests(TestCase):
    def test_button_shown_for_v3_rfc(self):
        rfc = WgRfcFactory(rfc_number=settings.FIRST_V3_RFC)
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=rfc.name)))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        buttons = q('a.btn:contains("Get editor source")')
        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons.attr("href"), "#")

    def test_button_shown_for_rfc_above_v3_threshold(self):
        rfc = WgRfcFactory(rfc_number=settings.FIRST_V3_RFC + 1)
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=rfc.name)))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        buttons = q('a.btn:contains("Get editor source")')
        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons.attr("href"), "#")

    def test_button_not_shown_for_pre_v3_rfc(self):
        rfc = WgRfcFactory(rfc_number=settings.FIRST_V3_RFC - 1)
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=rfc.name)))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        buttons = q('a.btn:contains("Get editor source")')
        self.assertEqual(len(buttons), 0)

