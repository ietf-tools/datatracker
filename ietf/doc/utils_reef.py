# Copyright The IETF Trust 2026, All Rights Reserved
"""Reef-related utilities"""

import json

from django.conf import settings
from django.core.cache import caches
from django.core.files.storage import storages, Storage


class _PopularityRankingCache:
    CACHE_LIFETIME = 15 * 60  # seconds

    def get_popularity_json(self):
        storage = storages["reef_bucket"]
        popularity_json_path = settings.POPULARITY_JSON_PATH
        with storage.open(popularity_json_path, "rb") as fp:
            return json.load(fp)

    @staticmethod
    def build_rankings_from_popularity_json(popularity_json) -> dict[int, int]:
        """Frob the incoming popularity.json contents into our format

        :popularity_json: parsed JSON from popularity.json

        Expected input format is
        [
          {
            "Rank": 1,
            "RFC": "RFC7505",
          },
          {
            "Rank": 2,
            "RFC": "RFC4754",
          },
          ...
        ]

        Output is a mapping from integer rfc_number to ranking integer, lower is more
        popular. Not guaranteed to include every rfc_number.
        """
        return {int(item["RFC"][3:]): int(item["Rank"]) for item in popularity_json}

    def cached_popularity_rankings(self) -> dict[int, int]:
        cache_key = "ietf.doc.utils_reef.cached_popularity_rankings"
        cache = caches["default"]
        cached_rankings = cache.get(cache_key)
        if cached_rankings is None:
            popularity_json = self.get_popularity_json()
            cached_rankings = self.build_rankings_from_popularity_json(popularity_json)
            cache.set(
                cache_key,
                cached_rankings,
                self.CACHE_LIFETIME,
            )
        return cached_rankings

    def __call__(self, item: int) -> int | None:
        rankings = self.cached_popularity_rankings()
        return rankings.get(item, None)


# Look up popularity ranking of an RFC. Call with rfc_number (int) as a parameter, get
# ranking. Value is None if there is no ranking for the RFC. This indicates the lowest
# tier of popularity. Otherwise, the value is an integer with 1 the most popular and
# higher rankings indicating lower popularity.
get_popularity_ranking = _PopularityRankingCache()
