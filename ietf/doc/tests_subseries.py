# Copyright The IETF Trust 2023, All Rights Reserved
# -*- coding: utf-8 -*-

import debug # pyflakes:ignore

from pyquery import PyQuery

from django.urls import reverse as urlreverse

from ietf.doc.factories import SubseriesFactory, RfcFactory
from ietf.doc.models import Document
from ietf.utils.test_utils import TestCase

class SubseriesTests(TestCase):

    def test_index_and_view(self):
        types = ["bcp", "std", "fyi"]
        for type_id in types:
            doc = SubseriesFactory(type_id=type_id)
            self.assertEqual(len(doc.contains()), 1)
            rfc = doc.contains()[0]
            # Index
            url = urlreverse("ietf.doc.views_search.index_subseries", kwargs=dict(type_id=type_id))
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertIsNotNone(q(f"#{doc.name}"))
            self.assertIn(f"RFC {rfc.name[3:]}",q(f"#{doc.name}").text())
            # Subseries document view
            url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc.name))
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertIn(f"{doc.type_id.upper()} {doc.name[3:]} consists of:",q("h2").text())
            self.assertIn(f"RFC {rfc.name[3:]}", q("div.row p a").text())
            # RFC view
            url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=rfc.name))
            r = self.client.get(url)
            q = PyQuery(r.content)
            self.assertIn(f"RFC {rfc.name[3:]} also known as {type_id.upper()} {doc.name[3:]}", q("h1").text())
        bcp = Document.objects.filter(type_id="bcp").last()
        bcp.relateddocument_set.create(relationship_id="contains", target=RfcFactory())
        for rfc in bcp.contains():
            url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=rfc.name))
            r = self.client.get(url)
            q = PyQuery(r.content)
            self.assertIn(f"RFC {rfc.name[3:]} part of BCP {bcp.name[3:]}", q("h1").text())     


