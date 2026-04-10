# Copyright The IETF Trust 2026, All Rights Reserved

from django.conf import settings
from django.utils import timezone
from django.urls import reverse as urlreverse

from pyquery import PyQuery

from ietf.doc.factories import WgRfcFactory
from ietf.doc.models import StoredObject
from ietf.doc.storage_utils import store_bytes
from ietf.utils.test_utils import TestCase


class UnpreppedRfcXmlTests(TestCase):
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
                expected_href = urlreverse(
                    "ietf.doc.views_doc.rfcxml_notprepped_wrapper",
                    kwargs=dict(number=rfc.rfc_number),
                )
                self.assertEqual(
                    buttons.attr("href"),
                    expected_href,
                    msg=f"rfc_number={rfc.rfc_number}",
                )
            else:
                self.assertEqual(len(buttons), 0, msg=f"rfc_number={rfc.rfc_number}")

    def test_rfcxml_notprepped(self):
        number = settings.FIRST_V3_RFC
        stored_name = f"notprepped/rfc{number}.notprepped.xml"
        url = f"/doc/rfc{number}/notprepped/"

        # 404 for pre-v3 RFC numbers (no document needed)
        r = self.client.get(f"/doc/rfc{number - 1}/notprepped/")
        self.assertEqual(r.status_code, 404)

        # 404 when no RFC document exists in the database
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

        # 404 when RFC document exists but has no StoredObject
        WgRfcFactory(rfc_number=number)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

        # 404 when StoredObject exists but backing storage is missing (FileNotFoundError)
        now = timezone.now()
        StoredObject.objects.create(
            store="rfc",
            name=stored_name,
            sha384="a" * 96,
            len=0,
            store_created=now,
            created=now,
            modified=now,
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

        # 200 with correct content-type and body when object is fully stored
        xml_content = b"<rfc>test</rfc>"
        store_bytes("rfc", stored_name, xml_content, allow_overwrite=True)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/xml")
        self.assertEqual(r.content, xml_content)

    def test_rfcxml_notprepped_wrapper(self):
        number = settings.FIRST_V3_RFC

        # 404 for pre-v3 RFC numbers (no document needed)
        r = self.client.get(
            urlreverse(
                "ietf.doc.views_doc.rfcxml_notprepped_wrapper",
                kwargs=dict(number=number - 1),
            )
        )
        self.assertEqual(r.status_code, 404)

        # 404 when no RFC document exists in the database
        r = self.client.get(
            urlreverse(
                "ietf.doc.views_doc.rfcxml_notprepped_wrapper",
                kwargs=dict(number=number),
            )
        )
        self.assertEqual(r.status_code, 404)

        # 200 with rendered template when RFC document exists
        rfc = WgRfcFactory(rfc_number=number)
        r = self.client.get(
            urlreverse(
                "ietf.doc.views_doc.rfcxml_notprepped_wrapper",
                kwargs=dict(number=number),
            )
        )
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertIn(str(rfc.rfc_number), q("h1").text())
        download_url = urlreverse(
            "ietf.doc.views_doc.rfcxml_notprepped", kwargs=dict(number=number)
        )
        self.assertEqual(len(q(f'a.btn[href="{download_url}"]')), 1)
