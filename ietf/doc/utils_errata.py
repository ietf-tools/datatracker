# Copyright The IETF Trust 2026, All Rights Reserved

import requests

from django.conf import settings

from ietf.utils.log import log

def signal_update_rfc_metadata(rfc_number_list=()):
    key = getattr(settings, 'ERRATA_METADATA_NOTIFICATION_API_KEY', None)
    if key is not None:
        headers = {'X-Api-Key': settings.ERRATA_METADATA_NOTIFICATION_API_KEY}
        post_dict = {
            "rfc_number_list": list(rfc_number_list),
        }
        try:
            response = requests.post(
                settings.ERRATA_METADATA_NOTIFICATION_URL,
                headers=headers,
                json=post_dict,
                timeout=settings.DEFAULT_REQUESTS_TIMEOUT)
        except requests.Timeout as e:
            log(f'POST request timed out for {settings.ERRATA_METADATA_NOTIFICATION_URL} ]: {e}')
            # raise RuntimeError(f'POST request timed out for {settings.ERRATA_METADATA_NOTIFICATION_URL}') from e
            return
        if response.status_code != 200:
            log(f'POST request failed for {settings.ERRATA_METADATA_NOTIFICATION_URL} ]: {response.status_code} {response.text}')
    else:
        log("No API key configured for errata metadata notification, skipping")
