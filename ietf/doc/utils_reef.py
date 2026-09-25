# Copyright The IETF Trust 2026, All Rights Reserved
"""Reef-related utilities"""

import json

import jsonschema
from django.conf import settings
from django.core.cache import caches
from django.core.files.storage import storages
from ietf.utils.log import log

from ietf.doc.models import Document


class PopularityCache:
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

    def build_scores_from_popularity_json(self, popularity_json) -> dict[int, int]:
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

    def cached_popularity_scores(self) -> dict[int, int]:
        cache_key = "ietf.doc.utils_reef.cached_popularity_rankings"
        cache = caches["default"]
        cached_scores = cache.get(cache_key)
        if cached_scores is None:
            popularity_json = self.get_popularity_json()
            cached_scores = self.build_scores_from_popularity_json(popularity_json)
            cache.set(
                cache_key,
                cached_scores,
                self.CACHE_LIFETIME,
            )
        return cached_scores

    def __call__(self, item: Document) -> int | None:
        if item.rfc_number is None:
            return None
        scores = self.cached_popularity_scores()
        return scores.get(item.rfc_number, None)


# Look up popularity ranking of an RFC. Call with rfc_number (int) as a parameter, get
# ranking. Value is None if there is no ranking for the RFC. This indicates the lowest
# tier of popularity. Otherwise, the value is an integer with 1 the most popular and
# higher rankings indicating lower popularity.
get_popularity_score = PopularityCache()
