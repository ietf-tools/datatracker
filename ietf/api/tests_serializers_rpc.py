# Copyright The IETF Trust 2026, All Rights Reserved

from unittest import mock

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

    @mock.patch("ietf.api.serializers_rpc.update_rfc_searchindex_task")
    @mock.patch("ietf.api.serializers_rpc.trigger_red_precomputer_task")
    def test_update(self, mock_trigger_red_task, mock_update_searchindex_task):
        updates = WgRfcFactory.create_batch(2)
        obsoletes = WgRfcFactory.create_batch(2)
        rfc = WgRfcFactory(pages=10)
        updated_by = WgRfcFactory.create_batch(2)
        obsoleted_by = WgRfcFactory.create_batch(2)
        for d in updates:
            rfc.relateddocument_set.create(relationship_id="updates",target=d)
        for d in obsoletes:
            rfc.relateddocument_set.create(relationship_id="updates",target=d)
        for d in updated_by:
            d.relateddocument_set.create(relationship_id="updates",target=rfc)
        for d in obsoleted_by:
            d.relateddocument_set.create(relationship_id="updates",target=rfc)        
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
        result.refresh_from_db()
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
        # Confirm that red precomputer was triggered correctly
        self.assertTrue(mock_trigger_red_task.delay.called)
        _, mock_kwargs = mock_trigger_red_task.delay.call_args
        self.assertIn("rfc_number_list", mock_kwargs)
        expected_numbers = sorted(
            [
                d.rfc_number
                for d in [rfc] + updates + obsoletes + updated_by + obsoleted_by
            ]
        )
        self.assertEqual(mock_kwargs["rfc_number_list"], expected_numbers)
        # Confirm that the search index update task was triggered correctly
        self.assertTrue(mock_update_searchindex_task.delay.called)
        self.assertEqual(
            mock_update_searchindex_task.delay.call_args,
            mock.call(rfc.rfc_number),
        )

    @mock.patch("ietf.api.serializers_rpc.update_rfc_searchindex_task")
    @mock.patch("ietf.api.serializers_rpc.trigger_red_precomputer_task")
    def test_partial_update(self, mock_trigger_red_task, mock_update_searchindex_task):
        # We could test other permutations of fields, but authors is a partial update
        # we know we are going to use, so verifying that one in particular.
        updates = WgRfcFactory.create_batch(2)
        obsoletes = WgRfcFactory.create_batch(2)
        rfc = WgRfcFactory(pages=10, abstract="do or do not", title="padawan")
        updated_by = WgRfcFactory.create_batch(2)
        obsoleted_by = WgRfcFactory.create_batch(2)
        for d in updates:
            rfc.relateddocument_set.create(relationship_id="updates",target=d)
        for d in obsoletes:
            rfc.relateddocument_set.create(relationship_id="updates",target=d)
        for d in updated_by:
            d.relateddocument_set.create(relationship_id="updates",target=rfc)
        for d in obsoleted_by:
            d.relateddocument_set.create(relationship_id="updates",target=rfc) 
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
        result.refresh_from_db()
        self.assertEqual(rfc.title, "padawan")
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
        # Confirm that the red precomputer was triggered correctly
        self.assertTrue(mock_trigger_red_task.delay.called)
        _, mock_kwargs = mock_trigger_red_task.delay.call_args
        self.assertIn("rfc_number_list", mock_kwargs)
        expected_numbers = sorted(
            [
                d.rfc_number
                for d in [rfc] + updates + obsoletes + updated_by + obsoleted_by
            ]
        )
        self.assertEqual(mock_kwargs["rfc_number_list"], expected_numbers)
        # Confirm that the search index update task was called correctly
        self.assertTrue(mock_update_searchindex_task.delay.called)
        self.assertEqual(
            mock_update_searchindex_task.delay.call_args,
            mock.call(rfc.rfc_number),
        )

        # Test only a field on the Document itself to be sure that it works
        mock_trigger_red_task.delay.reset_mock()
        mock_update_searchindex_task.delay.reset_mock()
        serializer = EditableRfcSerializer(
            partial=True,
            instance=rfc,
            data={"title": "jedi master"},
        )
        self.assertTrue(serializer.is_valid())
        result = serializer.save()
        result.refresh_from_db()
        self.assertEqual(rfc.title, "jedi master")
        # Confirm that the red precomputer was triggered correctly
        self.assertTrue(mock_trigger_red_task.delay.called)
        _, mock_kwargs = mock_trigger_red_task.delay.call_args
        self.assertIn("rfc_number_list", mock_kwargs)
        self.assertEqual(mock_kwargs["rfc_number_list"], expected_numbers)
        # Confirm that the search index update task was called correctly
        self.assertTrue(mock_update_searchindex_task.delay.called)
        self.assertEqual(
            mock_update_searchindex_task.delay.call_args,
            mock.call(rfc.rfc_number),
        )
