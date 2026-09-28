# Copyright The IETF Trust 2026, All Rights Reserved
"""Reef-related utilities"""

import json

import jsonschema
from django.conf import settings
from django.core.cache import caches
from django.core.files.storage import storages

from ietf.doc.models import Document
from ietf.utils.log import log


class PopularityCache:
    CACHE_KEY = "ietf.doc.utils_reef.cached_popularity_rankings"
    CACHE_LIFETIME = 15 * 60  # seconds

    json_validator = jsonschema.Draft202012Validator(
        schema={
            "type": "object",
            "properties": {
                "computed_at": {"type": "string", "format": "date-time"},
                "entries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "rfc": {"type": "string", "pattern": "^rfc[1-9][0-9]*$"},
                            "popularity": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                            },
                        },
                        "required": ["rfc", "popularity"],
                    },
                },
            },
            "required": ["entries"],
        },
        format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER,
    )

    def get_popularity_json(self):
        storage = storages["reef_bucket"]
        popularity_json_path = settings.POPULARITY_JSON_PATH
        with storage.open(popularity_json_path, "rb") as fp:
            popularity_json = json.load(fp)
        try:
            self.json_validator.validate(popularity_json)
        except jsonschema.ValidationError as err:
            log(f"Error parsing popularity.json: {str(err)}")
            raise
        return popularity_json

    def build_scores_from_popularity_json(self, popularity_json) -> dict[int, float]:
        """Frob the incoming popularity.json contents into our format

        :popularity_json: parsed JSON from popularity.json

        Expected input format is
        {
          "computed_at": "2026-09-24T22:16:03Z",
          "entries": [
            {"rfc": "rfc9110", "popularity": 1.0},
            {"rfc": "rfc2119", "popularity": 0.5},
            {"rfc": "rfc7230", "popularity": 0.0}
          ]
        }

        Output is a mapping from integer rfc_number to float score, higher is more
        popular. Not guaranteed to include every rfc_number.
        """
        entries = popularity_json["entries"]
        return {int(entry["rfc"][3:]): entry["popularity"] for entry in entries}

    def refresh(self) -> dict[int, float]:
        """Load scores from popularity.json and store them in the cache"""
        popularity_json = self.get_popularity_json()
        scores = self.build_scores_from_popularity_json(popularity_json)
        caches["default"].set(self.CACHE_KEY, scores, self.CACHE_LIFETIME)
        return scores

    def cached_popularity_scores(self) -> dict[int, float]:
        cached_scores = caches["default"].get(self.CACHE_KEY)
        if cached_scores is None:
            cached_scores = self.refresh()
        return cached_scores

    def __call__(self, item: Document) -> float | None:
        if item.rfc_number is None:
            return None
        scores = self.cached_popularity_scores()
        return scores.get(item.rfc_number, None)


# Look up the popularity score of an RFC. Call with the RFC's Document, get a float
# between 0 and 1, higher being more popular. Value is None if there is no score for
# the RFC.
get_popularity_score = PopularityCache()
