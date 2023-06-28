# Copyright The IETF Trust 2023, All Rights Reserved

import debug  # pyflakes:ignore

from pyquery import PyQuery

from pathlib import Path

from django.conf import settings
from django.urls import reverse as urlreverse

from ietf.doc.factories import StatementFactory, DocEventFactory
from ietf.doc.models import State
from ietf.utils.test_utils import TestCase


class StatementsTestCase(TestCase):

    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + [
        "DOCUMENT_PATH_PATTERN"
    ]

    def extract_content(self, response):
        if not hasattr(response,"_cached_extraction"):
            response._cached_extraction = list(response.streaming_content)[0].decode("utf-8")
        return response._cached_extraction

    def write_statement_markdown_file(self, statement):
        (
            Path(settings.DOCUMENT_PATH_PATTERN.format(doc=statement))
            / ("%s-%s.md" % (statement.name, statement.rev))
        ).write_text(
            """# This is a test statement.
Version: {statement.rev}

## A section

This test section has some text.
"""
        )

    def write_statement_pdf_file(self, statement):
        (
            Path(settings.DOCUMENT_PATH_PATTERN.format(doc=statement))
            / ("%s-%s.pdf" % (statement.name, statement.rev))
        ).write_text(
            f"{statement.rev} This is not valid PDF, but the test does not need it to be"
        )

    def test_statement_doc_view(self):
        doc = StatementFactory()
        self.write_statement_markdown_file(doc)
        url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc.name))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(q("#statement-state").text(), "Active")
        self.assertEqual(q("#statement-type").text(), "IAB Statement")
        self.assertIn("has some text", q(".card-body").text())
        published = doc.docevent_set.filter(type="published_statement").last().time
        self.assertIn(published.date().isoformat(), q("#published").text())

        doc.set_state(State.objects.get(type_id="statement", slug="replaced"))
        doc2 = StatementFactory()
        doc2.relateddocument_set.create(
            relationship_id="replaces", target=doc.docalias.first()
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(q("#statement-state").text(), "Replaced")
        self.assertEqual(q("#statement-type").text(), "Replaced IAB Statement")
        self.assertEqual(q("#statement-type").next().text(), f"Replaced by {doc2.name}")

        url = urlreverse(
            "ietf.doc.views_doc.document_main", kwargs=dict(name=doc2.name)
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(q("#statement-type").text(), "IAB Statement")
        self.assertEqual(q("#statement-type").next().text(), f"Replaces {doc.name}")

    def test_serve_pdf(self):
        url = urlreverse(
            "ietf.doc.views_statement.serve_pdf",
            kwargs=dict(name="statement-does-not-exist"),
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

        doc = StatementFactory()
        url = urlreverse(
            "ietf.doc.views_statement.serve_pdf", kwargs=dict(name=doc.name)
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)  # File not found

        self.write_statement_pdf_file(doc)
        doc.rev = "01"
        e = DocEventFactory(type="published_statement", doc=doc, rev=doc.rev)
        doc.save_with_history([e])
        self.write_statement_pdf_file(doc)

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get("Content-Type"), "application/pdf")
        self.assertTrue(
            self.extract_content(r).startswith(doc.rev)
        )  # relies on test doc not actually being pdf

        url = urlreverse(
            "ietf.doc.views_statement.serve_pdf", kwargs=dict(name=doc.name, rev="00")
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self.extract_content(r).startswith("00 "))
        url = urlreverse(
            "ietf.doc.views_statement.serve_pdf", kwargs=dict(name=doc.name, rev="01")
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self.extract_content(r).startswith("01 "))
