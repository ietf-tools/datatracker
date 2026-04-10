# Copyright The IETF Trust 2026, All Rights Reserved

from django.conf import settings
from django.urls import reverse as urlreverse

from pyquery import PyQuery

from ietf.doc.factories import WgRfcFactory
from ietf.utils.test_utils import TestCase


class RfcEditorSourceButtonTests(TestCase):
    def test_editor_source_button_visibility(self):
        pre_v3 = WgRfcFactory(rfc_number=settings.FIRST_V3_RFC - 1)
        first_v3 = WgRfcFactory(rfc_number=settings.FIRST_V3_RFC)
        post_v3 = WgRfcFactory(rfc_number=settings.FIRST_V3_RFC + 1)

        for rfc, expect_button in [(pre_v3, False), (first_v3, True), (post_v3, True)]:
            r = self.client.get(
                urlreverse(
                    "ietf.doc.views_doc.document_main", kwargs=dict(name=rfc.name)
                )
            )
            self.assertEqual(r.status_code, 200)
            buttons = PyQuery(r.content)('a.btn:contains("Get editor source")')
            if expect_button:
                self.assertEqual(len(buttons), 1, msg=f"rfc_number={rfc.rfc_number}")
                self.assertEqual(
                    buttons.attr("href"), "#", msg=f"rfc_number={rfc.rfc_number}"
                )
            else:
                self.assertEqual(len(buttons), 0, msg=f"rfc_number={rfc.rfc_number}")
