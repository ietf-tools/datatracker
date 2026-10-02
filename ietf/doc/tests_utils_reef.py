# Copyright The IETF Trust 2026, All Rights Reserved
import json
from contextlib import contextmanager
from unittest import mock

import jsonschema
from django.conf import settings
from django.core.cache.backends.base import BaseCache
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.test.utils import override_settings

from ietf.doc.utils_reef import (
    POPULARITY_CACHE_KEY,
    POPULARITY_CACHE_LIFETIME,
    build_scores_from_popularity_json,
    cached_popularity_scores,
    get_popularity_json,
    refresh_popularity_scores,
)
from ietf.utils.test_utils import TestCase


@contextmanager
def popularity_json_in_bucket(content: bytes, path=None):
    """Put content in the reef bucket, removing it on exit

    The in-memory bucket persists between tests, so it must be cleaned up.
    """
    storage = storages["reef_bucket"]
    saved_name = storage.save(
        settings.POPULARITY_JSON_PATH if path is None else path,
        ContentFile(content),
    )
    try:
        yield
    finally:
        storage.delete(saved_name)


class PopularityUtilsTests(TestCase):
    # Includes the boundary popularity values 0 and 1
    valid_popularity_json = {
        "computed_at": "2026-09-24T22:16:03Z",
        "entries": [
            {"rfc": "rfc9110", "popularity": 1.0},
            {"rfc": "rfc2119", "popularity": 0.5},
            {"rfc": "rfc7230", "popularity": 0},
        ],
    }

    def setUp(self):
        super().setUp()
        # Autospec so calls that a real cache would reject are not masked
        self.cache = mock.create_autospec(BaseCache, instance=True)
        cache_patcher = mock.patch(
            "ietf.doc.utils_reef.caches", {"default": self.cache}
        )
        cache_patcher.start()
        self.addCleanup(cache_patcher.stop)

    def test_get_popularity_json(self):
        with self.assertRaises(FileNotFoundError):
            get_popularity_json()

        with popularity_json_in_bucket(
            json.dumps(self.valid_popularity_json).encode()
        ):
            self.assertEqual(
                get_popularity_json(),
                self.valid_popularity_json,
            )

        # computed_at is optional
        without_computed_at = {"entries": self.valid_popularity_json["entries"]}
        with (
            popularity_json_in_bucket(
                json.dumps(without_computed_at).encode(), path="other/pop.json"
            ),
            override_settings(POPULARITY_JSON_PATH="other/pop.json"),
        ):
            self.assertEqual(
                get_popularity_json(), without_computed_at
            )

        with popularity_json_in_bucket(b"{not json"):
            with self.assertRaises(json.JSONDecodeError):
                get_popularity_json()

    def test_get_popularity_json_validation(self):
        def with_entry(entry):
            return {"entries": [entry]}

        invalid_docs = {
            "no entries": {"computed_at": "2026-09-24T22:16:03Z"},
            "no rfc": with_entry({"popularity": 0.5}),
            "no popularity": with_entry({"rfc": "rfc1"}),
            "uppercase rfc": with_entry({"rfc": "RFC1", "popularity": 0.5}),
            "rfc0": with_entry({"rfc": "rfc0", "popularity": 0.5}),
            "leading zero": with_entry({"rfc": "rfc01", "popularity": 0.5}),
            "bare number": with_entry({"rfc": "1", "popularity": 0.5}),
            "negative": with_entry({"rfc": "rfc1", "popularity": -0.1}),
            "over one": with_entry({"rfc": "rfc1", "popularity": 1.1}),
            "not a number": with_entry({"rfc": "rfc1", "popularity": "0.5"}),
            "bad computed_at": {
                "computed_at": "yesterday",
                "entries": [{"rfc": "rfc1", "popularity": 0.5}],
            },
        }
        for description, invalid_doc in invalid_docs.items():
            with (
                self.subTest(description),
                popularity_json_in_bucket(json.dumps(invalid_doc).encode()),
                self.assertRaises(jsonschema.ValidationError),
            ):
                get_popularity_json()

    def test_build_scores_from_popularity_json(self):
        self.assertEqual(
            build_scores_from_popularity_json(
                self.valid_popularity_json
            ),
            {9110: 1.0, 2119: 0.5, 7230: 0},
        )
        self.assertEqual(
            build_scores_from_popularity_json({"entries": []}),
            {},
        )

    @mock.patch("ietf.doc.utils_reef.build_scores_from_popularity_json")
    @mock.patch("ietf.doc.utils_reef.get_popularity_json")
    def test_refresh_popularity_scores(self, mock_get_json, mock_build_scores):
        mock_get_json.return_value = self.valid_popularity_json
        scores = {9110: 1.0}
        mock_build_scores.return_value = scores
        expected_set_call = mock.call(
            POPULARITY_CACHE_KEY, scores, POPULARITY_CACHE_LIFETIME
        )

        self.assertEqual(refresh_popularity_scores(), scores)
        self.assertEqual(mock_get_json.call_count, 1)
        self.assertEqual(
            mock_build_scores.call_args, mock.call(self.valid_popularity_json)
        )
        self.assertEqual(self.cache.set.call_args, expected_set_call)

        # Reloads and overwrites even when the cache holds scores
        self.cache.set.reset_mock()
        self.cache.get.return_value = {2119: 0.5}
        self.assertEqual(refresh_popularity_scores(), scores)
        self.assertEqual(mock_get_json.call_count, 2)
        self.assertEqual(self.cache.set.call_args, expected_set_call)

    @mock.patch("ietf.doc.utils_reef.refresh_popularity_scores")
    def test_cached_popularity_scores(self, mock_refresh):
        refreshed_scores = {9110: 1.0}
        mock_refresh.return_value = refreshed_scores

        # Cache miss
        self.cache.get.return_value = None
        self.assertEqual(
            cached_popularity_scores(), refreshed_scores
        )
        self.assertEqual(self.cache.get.call_args, mock.call(POPULARITY_CACHE_KEY))
        self.assertEqual(mock_refresh.call_count, 1)

        # Cache hit
        cached_scores = {2119: 0.5}
        self.cache.get.return_value = cached_scores
        self.assertEqual(
            cached_popularity_scores(), cached_scores
        )
        self.assertEqual(mock_refresh.call_count, 1)  # no additional refresh
        self.assertEqual(self.cache.set.call_count, 0)
