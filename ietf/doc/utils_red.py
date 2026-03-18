# Copyright The IETF Trust 2026, All Rights Reserved

import requests

from django.conf import settings

from ietf.utils.log import log


def trigger_red_precomputer(rfc_number_list=()):
    url = getattr(settings, "TRIGGER_RED_PRECOMPUTE_MULTIPLE_URL", None)
    if url is not None:
        payload = {
            "rfcs": ",".join([str(n) for n in rfc_number_list]),
        }
        try:
            log.log(f"Triggering red precompute multiple for RFCs {rfc_number_list}")
            response = requests.post(
                url,
                json=payload,
                timeout=settings.DEFAULT_REQUESTS_TIMEOUT,
            )
        except requests.Timeout as e:
            log(f"POST request timed out for {url} ]: {e}")
            return
        if response.status_code != 200:
            log(
                f"POST request failed for {url} ]: {response.status_code} {response.text}"
            )
    else:
        log("No URL configured for triggering red precompute multiple, skipping")
