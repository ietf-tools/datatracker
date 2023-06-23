# Copyright The IETF Trust 2023, All Rights Reserved

import debug  # pyflakes:ignore

from pyquery import PyQuery

from pathlib import Path

from django.conf import settings
from django.urls import reverse as urlreverse

from ietf.doc.factories import StatementFactory
from ietf.doc.models import State
from ietf.utils.test_utils import TestCase


class StatementsTestCase(TestCase):
    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + [
        "DOCUMENT_PATH_PATTERN"
    ]

    def write_statement_file(self, statement):
        (
            Path(settings.DOCUMENT_PATH_PATTERN.format(doc=statement))
            / ("%s-%s.md" % (statement.name, statement.rev))
        ).write_text(
            """# This is a test bofreq.
Version: {bofreq.rev}

## A section

This test section has some text.
"""
        )

    def test_statement_doc_view(self):
        doc = StatementFactory()
        self.write_statement_file(doc)
        url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc.name))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(q("#statement-state").text(), "Active")
        self.assertEqual(q("#statement-type").text(), "IAB Statement")
        self.assertIn("has some text", q(".card-body").text())

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
