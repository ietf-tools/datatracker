# Copyright The IETF Trust 2026, All Rights Reserved
"""Reef-related utilities"""

import json

import jsonschema
from django.conf import settings
from django.core.cache import caches
from django.core.files.storage import storages

from ietf.utils.log import log

POPULARITY_CACHE_KEY = "ietf.doc.utils_reef.cached_popularity_rankings"
POPULARITY_CACHE_LIFETIME = 15 * 60  # seconds

_popularity_json_validator = jsonschema.Draft202012Validator(
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


def get_popularity_json():
    storage = storages["reef_bucket"]
    popularity_json_path = settings.POPULARITY_JSON_PATH
    with storage.open(popularity_json_path, "rb") as fp:
        popularity_json = json.load(fp)
    try:
        _popularity_json_validator.validate(popularity_json)
    except jsonschema.ValidationError as err:
        log(f"Error parsing popularity.json: {str(err)}")
        raise
    return popularity_json


def build_scores_from_popularity_json(popularity_json) -> dict[int, float]:
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


def refresh_popularity_scores() -> dict[int, float]:
    """Load scores from popularity.json and store them in the cache"""
    popularity_json = get_popularity_json()
    scores = build_scores_from_popularity_json(popularity_json)
    caches["default"].set(POPULARITY_CACHE_KEY, scores, POPULARITY_CACHE_LIFETIME)
    return scores


def cached_popularity_scores() -> dict[int, float]:
    cached_scores = caches["default"].get(POPULARITY_CACHE_KEY)
    if cached_scores is None:
        cached_scores = refresh_popularity_scores()
    return cached_scores
