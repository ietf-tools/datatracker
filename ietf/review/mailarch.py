# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


# various utilities for working with the mailarch mail archive at
# mailarchive.ietf.org

import base64
import contextlib
import datetime
import email.utils
import hashlib
import mailbox
import tarfile
import tempfile

from urllib.parse import urlencode
from urllib.request import urlopen

import debug                            # pyflakes:ignore

from pyquery import PyQuery

from django.conf import settings
from django.utils.encoding import force_bytes, force_str

from ietf.utils.mail import get_payload_text

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

def construct_query_urls(doc, team, query=None):
    list_name = list_name_from_email(team.list_email)
    if not list_name:
        return None

    if not query:
        query = doc.name

    encoded_query = "?" + urlencode({
        "qdr": "c", # custom time frame
        "start_date": (datetime.date.today() - datetime.timedelta(days=180)).isoformat(),
        "email_list": list_name,
        "q": "subject:({})".format(query),
        "as": "1", # this is an advanced search
    })

    return {
        "query": query,
        "query_url": settings.MAILING_LIST_ARCHIVE_URL + "/arch/search/" + encoded_query,
        "query_data_url": settings.MAILING_LIST_ARCHIVE_URL + "/arch/export/mbox/" + encoded_query,
    }

def construct_message_url(list_name, msgid):
    return "{}/arch/msg/{}/{}".format(settings.MAILING_LIST_ARCHIVE_URL, list_name, hash_list_message_id(list_name, msgid))

def retrieve_messages_from_mbox(mbox_fileobj):
    """Return selected content in message from mbox from mailarch."""
    res = []
    with tempfile.NamedTemporaryFile(suffix=".mbox") as mbox_file:
        # mailbox.mbox needs a path, so we need to put the contents
        # into a file
        mbox_data = mbox_fileobj.read()
        mbox_file.write(mbox_data)
        mbox_file.flush()

        mbox = mailbox.mbox(mbox_file.name, create=False)
        for msg in mbox:
            content = ""

            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    charset = part.get_content_charset() or "utf-8"
                    content += get_payload_text(part, default_charset=charset)

            # parse a couple of things for the front end
            utcdate = None
            d = email.utils.parsedate_tz(msg["Date"])
            if d:
                utcdate = datetime.datetime.fromtimestamp(email.utils.mktime_tz(d))

            res.append({
                "from": msg["From"],
                "splitfrom": email.utils.parseaddr(msg["From"]),
                "subject": msg["Subject"],
                "content": content.replace("\r\n", "\n").replace("\r", "\n").strip("\n"),
                "message_id": email.utils.unquote(msg["Message-ID"].strip()),
                "url": email.utils.unquote(msg["Archived-At"].strip()),
                "date": msg["Date"],
                "utcdate": (utcdate.date().isoformat(), utcdate.time().isoformat()) if utcdate else ("", ""),
            })

    return res

def retrieve_messages(query_data_url):
    """Retrieve and return selected content from mailarch."""
    res = []

    # This has not been rewritten to use requests.get() because get() does
    # not handle file URLs out of the box, which we need for tesing
    with contextlib.closing(urlopen(query_data_url, timeout=15)) as fileobj:
        content_type = fileobj.info()["Content-type"]
        if not content_type.startswith("application/x-tar"):
            if content_type.startswith("text/html"):
                r = fileobj.read(20000)
                q = PyQuery(r)
                div = q('div[class~="no-results"]')
                if div:
                    raise KeyError("No results: %s -> %s" % (query_data_url, div.text(), ))
            raise Exception("Export failed - this usually means no matches were found")

        with tarfile.open(fileobj=fileobj, mode='r|*') as tar:
            for entry in tar:
                if entry.isfile():
                    mbox_fileobj = tar.extractfile(entry)
                    res.extend(retrieve_messages_from_mbox(mbox_fileobj))

    return res
