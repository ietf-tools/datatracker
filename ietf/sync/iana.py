import base64
import datetime
import email
import json
import re
import urllib2

from django.utils.http import urlquote
from django.conf import settings

from ietf.doc.mails import email_state_changed
from ietf.doc.models import Document, DocEvent, State, StateDocEvent, StateType, save_document_in_history
from ietf.doc.utils import add_state_change_event
from ietf.person.models import Person
from ietf.utils.timezone import local_timezone_to_utc, email_time_to_local_timezone, utc_to_local_timezone


#PROTOCOLS_URL = "https://www.iana.org/protocols/"
#CHANGES_URL = "https://datatracker.dev.icann.org:8080/data-tracker/changes"

def fetch_protocol_page(url):
    f = urllib2.urlopen(settings.IANA_SYNC_PROTOCOLS_URL)
    text = f.read()
    f.close()
    return text
    
def parse_protocol_page(text):
    """Parse IANA protocols page to extract referenced RFCs (as
    rfcXXXX document names)."""
    matches = re.findall('RFC [0-9]+', text)
    res = set()
    for m in matches:
        res.add("rfc" + m[len("RFC "):])

    return list(res)

def update_rfc_log_from_protocol_page(rfc_names, rfc_must_published_later_than):
    """Add notices to RFC history log that IANA is now referencing the RFC."""
    system = Person.objects.get(name="(System)")

    updated = []

    docs = Document.objects.filter(docalias__name__in=rfc_names).exclude(
        docevent__type="rfc_in_iana_registry").filter(
        # only take those that were published after cutoff since we
        # have a big bunch of old RFCs that we unfortunately don't have data for
        docevent__type="published_rfc", docevent__time__gte=rfc_must_published_later_than
        ).distinct()

    for d in docs:
        e = DocEvent(doc=d)
        e.by = system
        e.type = "rfc_in_iana_registry"
        e.desc = "IANA registries were updated to include %s" % d.display_name()
        e.save()

        updated.append(d)

    return updated
        
    

def fetch_changes_json(url, start, end):
    url += "?start=%s&end=%s" % (urlquote(local_timezone_to_utc(start).strftime("%Y-%m-%d %H:%M:%S")),
                                 urlquote(local_timezone_to_utc(end).strftime("%Y-%m-%d %H:%M:%S")))
    request = urllib2.Request(url)
    # HTTP basic auth
    username = "ietfsync"
    password = settings.IANA_SYNC_PASSWORD
    request.add_header("Authorization", "Basic %s" % base64.encodestring("%s:%s" % (username, password)).replace("\n", ""))
    f = urllib2.urlopen(request)
    text = f.read()
    f.close()
    return text

def parse_changes_json(text):
    response = json.loads(text)

    if "error" in response:
        raise Exception("IANA server returned error: %s" % response["error"])

    changes = response["changes"]

    # do some rudimentary validation
    for i in changes:
        for f in ['doc', 'type', 'time']:
            if f not in i:
                raise Exception('Error in response: Field %s missing in input: %s - %s' % (f, json.dumps(i), json.dumps(changes)))

        # a little bit of cleaning
        i["doc"] = i["doc"].strip()
        if i["doc"].startswith("https://www.ietf.org/internet-drafts/"):
            i["doc"] = i["doc"][len("https://www.ietf.org/internet-drafts/"):]

    # make sure we process oldest entries first
    changes.sort(key=lambda c: c["time"])

    return changes

def update_history_with_changes(changes, send_email=True):
    """Take parsed changes from IANA and apply them. Note that we
    expect to get these chronologically sorted, otherwise the change
    descriptions generated may not be right."""

    # build up state lookup
    states = {}

    slookup = dict((s.slug, s)
                   for s in State.objects.filter(used=True, type=StateType.objects.get(slug="draft-iana-action")))
    states["action"] = {
        "": slookup["newdoc"],
        "In Progress": slookup["inprog"],
        "Open": slookup["inprog"],
        "pre-approval In Progress": slookup["inprog"],
        "Waiting on Authors": slookup["waitauth"],
        "Author": slookup["waitauth"],
        "Waiting on ADs": slookup["waitad"],
        "Waiting on AD": slookup["waitad"],
        "AD": slookup["waitad"],
        "Waiting on WGC": slookup["waitwgc"],
        "WGC": slookup["waitwgc"],
        "Waiting on RFC-Editor": slookup["waitrfc"],
        "Waiting on RFC Editor": slookup["waitrfc"],
        "RFC-Editor": slookup["waitrfc"],
        "RFC-Ed-ACK": slookup["rfcedack"],
        "RFC-Editor-ACK": slookup["rfcedack"],
        "Completed": slookup["rfcedack"],
        "On Hold": slookup["onhold"],
        "No IC": slookup["noic"],
    }

    slookup = dict((s.slug, s)
                  for s in State.objects.filter(used=True, type=StateType.objects.get(slug="draft-iana-review")))
    states["review"] = {
        "IANA Review Needed": slookup["need-rev"],
        "IANA - Review Needed": slookup["need-rev"],
        "IANA OK - Actions Needed": slookup["ok-act"],
        "IANA OK - No Actions Needed": slookup["ok-noact"],
        "IANA Not OK": slookup["not-ok"],
        "IANA - Not OK": slookup["not-ok"],
        "Version Changed - Review Needed": slookup["changed"],
        }

    # so it turns out IANA has made a mistake and are including some
    # wrong states, we'll have to skip those
    wrong_action_states = ("Waiting on Reviewer", "Review Complete", "Last Call",
                           "Last Call - Questions", "Evaluation", "Evaluation -  Questions",
                           "With Reviewer", "IESG Notification Received", "Watiing on Last Call",
                           "IANA Comments Submitted", "Waiting on Last Call")

    system = Person.objects.get(name="(System)")

    added_events = []
    warnings = []

    for c in changes:
        docname = c['doc']
        timestamp = datetime.datetime.strptime(c["time"], "%Y-%m-%d %H:%M:%S")
        timestamp = utc_to_local_timezone(timestamp) # timestamps are in UTC

        if c['type'] in ("iana_state", "iana_review"):
            if c['type'] == "iana_state":
                kind = "action"

                if c["state"] in wrong_action_states:
                    warnings.append("Wrong action state '%s' encountered in changes from IANA" % c["state"])
                    continue
            else:
                kind = "review"

            if c["state"] not in states[kind]:
                warnings.append("Unknown IANA %s state %s (%s)" % (kind, c["state"], timestamp))
                continue

            state = states[kind][c["state"]]
            state_type = "draft-iana-%s" % kind

            if state.slug in ("need-rev", "changed"):
                # the Datatracker is the ultimate source of these
                # states, so skip them
                continue

            e = StateDocEvent.objects.filter(type="changed_state", time=timestamp,
                                             state_type=state_type, state=state)
            if not e:
                try:
                    doc = Document.objects.get(docalias__name=docname)
                except Document.DoesNotExist:
                    warnings.append("Document %s not found" % docname)
                    continue

                # the naive way of extracting prev_state here means
                # that we assume these changes are cronologically
                # applied
                prev_state = doc.get_state(state_type)
                e = add_state_change_event(doc, system, prev_state, state, timestamp=timestamp)

                if e:
                    # for logging purposes
                    e.json = c
                    added_events.append(e)

                if not StateDocEvent.objects.filter(doc=doc, time__gt=timestamp, state_type=state_type):
                    save_document_in_history(doc)
                    doc.set_state(state)

                    if send_email and (state != prev_state):
                        email_state_changed(None, doc, "IANA %s state changed to %s" % (kind, state.name),'doc_iana_state_changed')

                if doc.time < timestamp:
                    doc.time = timestamp
                    doc.save()

    return added_events, warnings


def find_document_name(text):
    prefixes = ['draft','conflict-review','status-change','charter']
    leading_delimiter_re = '(?<![-a-zA-Z0-9])'
    prefix_re = '(%s)' % '|'.join(prefixes)
    tail_re = '(-[a-z0-9]+)+?(-\d\d\.txt)?'
    trailing_delimiter_re = '((?![-a-zA-Z0-9])|$)'
    name_re = '%s(%s%s)%s' % (leading_delimiter_re, prefix_re, tail_re, trailing_delimiter_re)
    m = re.search(name_re,text)
    return m and m.group(0).lower()

def strip_version_extension(text):
    if re.search(r"\.\w{3}$", text): # strip off extension
        text = text[:-4]
    if re.search(r"-\d{2}$", text): # strip off revision
        text = text[:-3]
    return text

def parse_review_email(text):
    msg = email.message_from_string(text)

    # doc
    doc_name = find_document_name(msg["Subject"]) or ""
    doc_name = strip_version_extension(doc_name)

    # date
    review_time = datetime.datetime.now()
    if "Date" in msg:
        review_time = email_time_to_local_timezone(msg["Date"])

    # by
    by = None
    m = re.search(r"\"(.*)\"", msg["From"])
    if m:
        name = m.group(1).strip()
        if name.endswith(" via RT"):
            name = name[:-len(" via RT")]

        try:
            by = Person.objects.get(alias__name=name, role__group__acronym="iana")
        except Person.DoesNotExist:
            pass

    if not by:
        by = Person.objects.get(name="(System)")

    # comment
    body = msg.get_payload().decode('quoted-printable').replace("\r", "")

    begin_search = re.search('\(BEGIN\s+IANA\s+(LAST\s+CALL\s+)?COMMENTS?(\s*:\s*[a-zA-Z0-9-\.]*)?\s*\)',body)
    end_search = re.search('\(END\s+IANA\s+(LAST\s+CALL\s+)?COMMENTS?\)',body)
    if begin_search and end_search:
        begin_string = begin_search.group(0)
        end_string = end_search.group(0)
        b = body.find(begin_string)
        e = body.find(end_string)
        comment = body[b + len(begin_string):e].strip()
        embedded_name = strip_version_extension(find_document_name(begin_string) or "")
        if embedded_name:
            doc_name = embedded_name
    else:
        comment = ""

    # strip leading IESG:
    if comment.startswith("IESG:"):
        comment = comment[len("IESG:"):].lstrip()

    # strip ending Thanks, followed by signature
    m = re.compile(r"^Thanks,\n\n", re.MULTILINE).search(comment)
    if m:
        comment = comment[:m.start()].rstrip()

    m = re.search(r"<(.*)>", msg["From"])
    if m:
        comment = '(Via %s): %s' % ( m.group(1).strip() , comment )

    return doc_name, review_time, by, comment

def add_review_comment(doc_name, review_time, by, comment):
    if comment:
        try:
            e = DocEvent.objects.get(doc__name=doc_name, time=review_time, type="iana_review")
        except DocEvent.DoesNotExist:
            doc = Document.objects.get(name=doc_name)
            e = DocEvent(doc=doc, time=review_time, type="iana_review")

        e.desc = comment
        e.by = by

        e.save()
