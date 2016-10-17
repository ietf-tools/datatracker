# various utilities for working with the mailarch mail archive at
# mailarchive.ietf.org

import datetime, tarfile, mailbox, tempfile, hashlib, base64, email.utils
import urllib
import urllib2, contextlib

from django.conf import settings

def list_name_from_email(list_email):
    if not list_email.endswith("@ietf.org"):
        return None

    return list_email[:-len("@ietf.org")]

def hash_list_message_id(list_name, msgid):
    # hash in mailarch is computed similar to
    # https://www.mail-archive.com/faq.html#listserver except the list
    # name (without "@ietf.org") is used instead of the full address,
    # and rightmost "=" signs are (optionally) stripped
    sha = hashlib.sha1(msgid)
    sha.update(list_name)
    return base64.urlsafe_b64encode(sha.digest()).rstrip("=")

def construct_query_urls(review_req, query=None):
    list_name = list_name_from_email(review_req.team.list_email)
    if not list_name:
        return None

    if not query:
        query = review_req.doc.name

    encoded_query = "?" + urllib.urlencode({
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
            content = u""

            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    charset = part.get_content_charset() or "utf-8"
                    content += part.get_payload(decode=True).decode(charset, "ignore")

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
                "message_id": email.utils.unquote(msg["Message-ID"]),
                "url": email.utils.unquote(msg["Archived-At"]),
                "date": msg["Date"],
                "utcdate": (utcdate.date().isoformat(), utcdate.time().isoformat()) if utcdate else ("", ""),
            })

    return res

def retrieve_messages(query_data_url):
    """Retrieve and return selected content from mailarch."""
    res = []

    with contextlib.closing(urllib2.urlopen(query_data_url, timeout=15)) as fileobj:
        content_type = fileobj.info()["Content-type"]
        if not content_type.startswith("application/x-tar"):
            raise Exception("Export failed - this usually means no matches were found")

        with tarfile.open(fileobj=fileobj, mode='r|*') as tar:
            for entry in tar:
                if entry.isfile():
                    mbox_fileobj = tar.extractfile(entry)
                    res.extend(retrieve_messages_from_mbox(mbox_fileobj))

    return res
