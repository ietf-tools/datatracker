# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


# various utilities for working with the mailarch mail archive at
# mailarchive.ietf.org

import base64
import datetime
import email.utils
import hashlib
import requests

import debug                            # pyflakes:ignore


from django.conf import settings
from django.utils.encoding import force_bytes, force_str

from ietf.utils.log import log
from ietf.utils.timezone import date_today


def list_name_from_email(list_email):
    if not list_email.endswith("@ietf.org"):
        return None

    return list_email[:-len("@ietf.org")]

def hash_list_message_id(list_name, msgid):
    # hash in mailarch is computed similar to
    # https://www.mail-archive.com/faq.html#listserver except the list
    # name (without "@ietf.org") is used instead of the full address,
    # and rightmost "=" signs are (optionally) stripped
    sha = hashlib.sha1(force_bytes(msgid))
    sha.update(force_bytes(list_name))
    return force_str(base64.urlsafe_b64encode(sha.digest()).rstrip(b"="))

def construct_query_data(doc, team, query=None):
    list_name = list_name_from_email(team.list_email)
    if not list_name:
        return None

    if not query:
        query = doc.name

    query_data = {
        'start_date': (date_today() - datetime.timedelta(days=180)).isoformat(),
        'email_list': list_name,
        'query_value': query,
        'query': f'subject:({query})',
        'limit': '30',
    }
    return query_data

def construct_message_url(list_name, msgid):
    return "{}/arch/msg/{}/{}".format(settings.MAILING_LIST_ARCHIVE_URL, list_name, hash_list_message_id(list_name, msgid))

def retrieve_messages(query_data):
    """Retrieve and return selected content from mailarch."""

    headers = {'X-Api-Key': settings.MAILING_LIST_ARCHIVE_API_KEY}
    try:
        response = requests.post(
            settings.MAILING_LIST_ARCHIVE_SEARCH_URL,
            headers=headers,
            json=query_data,
            timeout=settings.DEFAULT_REQUESTS_TIMEOUT)
    except requests.Timeout as exc:
        log(f'POST request failed for [{query_data["url"]}]: {exc}')
        raise RuntimeError(f'Timeout retrieving [{query_data["url"]}]') from exc

    results = []
    jresponse = response.json()
    if 'results' not in jresponse or len(jresponse['results']) == 0:
        raise KeyError(f'No results: {query_data["query"]}')
    for msg in jresponse['results']:
        # datetime is already UTC
        dt = datetime.datetime.fromisoformat(msg['date'])
        dt_utc = dt.replace(tzinfo=datetime.timezone.utc)
        results.append({
            "from": msg["from"],
            "splitfrom": email.utils.parseaddr(msg["from"]),
            "subject": msg["subject"],
            "content": msg["content"].replace("\r\n", "\n").replace("\r", "\n").strip("\n"),
            "message_id": msg["message_id"],
            "url": msg["url"],
            "utcdate": (dt_utc.date().isoformat(), dt_utc.time().isoformat()),
        })

    return results
