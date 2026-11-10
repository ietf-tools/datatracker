# Copyright The IETF Trust 2016-2023, All Rights Reserved
# -*- coding: utf-8 -*-

import itertools

from django.conf import settings

from ietf.doc.factories import DocumentFactory, WgRfcFactory
from ietf.doc.models import RelatedDocument
from ietf.meeting.factories import MeetingFactory
from ietf.utils.test_utils import TestCase


class RelatedDocumentTests(TestCase):
    def test_is_downref(self):
        rfcs = [
            WgRfcFactory(std_level_id=lvl)
            for lvl in ["inf", "exp", "bcp", "ps", "ds", "std", "unkn"]
        ]

        result_matrix = {
            # source
            "inf": {
                "inf": None,  # target
                "exp": None,  # target
                "bcp": None,  # target
                "ps": None,  # target
                "ds": None,  # target
                "std": None,  # target
                "unkn": None,  # target
            },
            # source
            "exp": {
                "inf": None,  # target
                "exp": None,  # target
                "bcp": None,  # target
                "ps": None,  # target
                "ds": None,  # target
                "std": None,  # target
                "unkn": None,  # target
            },
            # source
            "bcp": {
                "inf": "Downref",  # target
                "exp": "Downref",  # target
                "bcp": None,  # target
                "ps": None,  # target
                "ds": None,  # target
                "std": None,  # target
                "unkn": "Possible Downref",  # target
            },
            # source
            "ps": {
                "inf": "Downref",  # target
                "exp": "Downref",  # target
                "bcp": None,  # target
                "ps": None,  # target
                "ds": None,  # target
                "std": None,  # target
                "unkn": "Possible Downref",  # target
            },
            # source
            "ds": {
                "inf": "Downref",  # target
                "exp": "Downref",  # target
                "bcp": None,  # target
                "ps": "Downref",  # target
                "ds": None,  # target
                "std": None,  # target
                "unkn": "Possible Downref",  # target
            },
            # source
            "std": {
                "inf": "Downref",  # target
                "exp": "Downref",  # target
                "bcp": None,  # target
                "ps": "Downref",  # target
                "ds": "Downref",  # target
                "std": None,  # target
                "unkn": "Possible Downref",  # target
            },
            # source
            "unkn": {
                "inf": None,  # target
                "exp": None,  # target
                "bcp": None,  # target
                "ps": "Possible Downref",  # target
                "ds": "Possible Downref",  # target
                "std": None,  # target
                "unkn": "Possible Downref",  # target
            },
        }

        for rel in ["refnorm", "refinfo", "refunk", "refold"]:
            for source, target in itertools.product(rfcs, rfcs):
                ref = RelatedDocument.objects.create(
                    source=source,
                    target=target,
                    relationship_id=rel,
                )

                result = ref.is_downref()

                desired_result = (
                    result_matrix[source.std_level_id][target.std_level_id]
                    if ref.relationship.slug in ["refnorm", "refunk"]
                    else None
                )
                if (
                    ref.relationship.slug == "refunk"
                    and desired_result is not None
                    and not desired_result.startswith("Possible")
                ):
                    desired_result = f"Possible {desired_result}"

                self.assertEqual(desired_result, result)


class MeetingMaterialHrefTests(TestCase):
    def test_bluesheets_href(self):
        """Bluesheets link to datatracker's materials URLs, like other meeting materials"""
        meetings = {
            "120": MeetingFactory(type_id="ietf", number="120"),
            # IETF 96 and earlier use proceedings format version 1
            "96": MeetingFactory(type_id="ietf", number="96"),
            "interim-2026-mars-01": MeetingFactory(type_id="interim", number="interim-2026-mars-01"),
        }
        for number, versioned, expected_path in [
            ("120", True, "/meeting/120/materials/bluesheets-x-01"),
            ("120", False, "/meeting/120/materials/bluesheets-x"),
            ("96", True, "/meeting/96/materials/bluesheets-x"),
            ("interim-2026-mars-01", True, "/meeting/interim-2026-mars-01/materials/bluesheets-x-01"),
        ]:
            with self.subTest(number=number, versioned=versioned):
                doc = DocumentFactory(type_id="bluesheets", name="bluesheets-x", rev="01")
                meeting = meetings[number]
                href = doc.get_href(meeting) if versioned else doc.get_versionless_href(meeting)
                self.assertEqual(href, settings.IDTRACKER_BASE_URL + expected_path)
                doc.delete()
