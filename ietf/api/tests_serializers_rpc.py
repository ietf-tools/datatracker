# Copyright The IETF Trust 2026, All Rights Reserved
from django.utils import timezone

from ietf.utils.test_utils import TestCase
from ietf.doc.models import Document
from ietf.doc.factories import WgRfcFactory
from .serializers_rpc import EditableRfcSerializer


class EditableRfcSerializerTests(TestCase):
    def test_create(self):
        serializer = EditableRfcSerializer(
            data={
                "published": timezone.now(),
                "title": "Yadda yadda yadda",
                "authors": [
                    {
                        "titlepage_name": "B. Fett",
                        "is_editor": False,
                        "affiliation": "DBA Galactic Empire",
                        "country": "",
                    },
                ],
                "stream": "ietf",
                "abstract": "A long time ago in a galaxy far, far away...",
                "pages": 3,
                "std_level": "inf",
                "subseries": ["fyi999"],
            }
        )
        self.assertTrue(serializer.is_valid())
        with self.assertRaises(RuntimeError, msg="serializer does not allow create()"):
            serializer.save()

    def test_update(self):
        rfc = WgRfcFactory(pages=10)
        serializer = EditableRfcSerializer(
            instance=rfc,
            data={
                "published": timezone.now(),
                "title": "Yadda yadda yadda",
                "authors": [
                    {
                        "titlepage_name": "B. Fett",
                        "is_editor": False,
                        "affiliation": "DBA Galactic Empire",
                        "country": "",
                    },
                ],
                "stream": "ise",
                "abstract": "A long time ago in a galaxy far, far away...",
                "pages": 3,
                "std_level": "inf",
                "subseries": ["fyi999"],
            },
        )
        self.assertTrue(serializer.is_valid())
        result = serializer.save()
        self.assertEqual(result.title, "Yadda yadda yadda")
        self.assertEqual(
            list(
                result.rfcauthor_set.values(
                    "titlepage_name", "is_editor", "affiliation", "country"
                )
            ),
            [
                {
                    "titlepage_name": "B. Fett",
                    "is_editor": False,
                    "affiliation": "DBA Galactic Empire",
                    "country": "",
                },
            ],
        )
        self.assertEqual(result.stream_id, "ise")
        self.assertEqual(
            result.abstract, "A long time ago in a galaxy far, far away..."
        )
        self.assertEqual(result.pages, 3)
        self.assertEqual(result.std_level_id, "inf")
        self.assertEqual(
            result.part_of(),
            [Document.objects.get(name="fyi999")],
        )

    def test_partial_update(self):
        # We could test other permutations of fields, but authors is a partial update
        # we know we are going to use, so verifying that one in particular.
        rfc = WgRfcFactory(pages=10, abstract="do or do not", title="jedi master")
        serializer = EditableRfcSerializer(
            partial=True,
            instance=rfc,
            data={
                "authors": [
                    {
                        "titlepage_name": "B. Fett",
                        "is_editor": False,
                        "affiliation": "DBA Galactic Empire",
                        "country": "",
                    },
                ],
            },
        )
        self.assertTrue(serializer.is_valid())
        result = serializer.save()
        self.assertEqual(rfc.title, "jedi master")
        self.assertEqual(
            list(
                result.rfcauthor_set.values(
                    "titlepage_name", "is_editor", "affiliation", "country"
                )
            ),
            [
                {
                    "titlepage_name": "B. Fett",
                    "is_editor": False,
                    "affiliation": "DBA Galactic Empire",
                    "country": "",
                },
            ],
        )
        self.assertEqual(result.stream_id, "ietf")
        self.assertEqual(result.abstract, "do or do not")
        self.assertEqual(result.pages, 10)
        self.assertEqual(result.std_level_id, "ps")
        self.assertEqual(result.part_of(), [])
