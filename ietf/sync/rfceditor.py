# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import base64
import datetime
import re
import requests

from typing import Iterator, Optional, Union
from urllib.parse import urlencode
from xml.dom import pulldom, Node

from django.conf import settings
from django.db.models import Subquery, OuterRef, F, Q
from django.utils import timezone
from django.utils.encoding import smart_bytes, force_str

import debug                            # pyflakes:ignore

from ietf.doc.models import ( Document, State, StateType, DocEvent, DocRelationshipName,
    DocTagName, RelatedDocument, RelatedDocHistory )
from ietf.doc.expire import move_draft_files_to_archive
from ietf.doc.utils import add_state_change_event, new_state_change_event, prettify_std_name, update_action_holders
from ietf.group.models import Group
from ietf.ipr.models import IprDocRel
from ietf.name.models import StdLevelName, StreamName
from ietf.person.models import Person
from ietf.utils.log import log
from ietf.utils.mail import send_mail_text
from ietf.utils.timezone import datetime_from_date, RPC_TZINFO

#QUEUE_URL = "https://www.rfc-editor.org/queue2.xml"
#INDEX_URL = "https://www.rfc-editor.org/rfc/rfc-index.xml"
#POST_APPROVED_DRAFT_URL = "https://www.rfc-editor.org/sdev/jsonexp/jsonparser.php"

MIN_ERRATA_RESULTS = 5000
MIN_INDEX_RESULTS = 8000
MIN_QUEUE_RESULTS = 10

def get_child_text(parent_node, tag_name):
    text = []
    for node in parent_node.childNodes:
        if node.nodeType == Node.ELEMENT_NODE and node.localName == tag_name:
            text.append(node.firstChild.data)
    return '\n\n'.join(text)


def parse_queue(response):
    """Parse RFC Editor queue XML into a bunch of tuples + warnings."""

    events = pulldom.parse(response)
    drafts = []
    warnings = []
    stream = None

    for event, node in events:
        try:
            if event == pulldom.START_ELEMENT and node.tagName == "entry":
                events.expandNode(node)
                node.normalize()
                draft_name = get_child_text(node, "draft").strip()
                draft_name = re.sub(r"(-\d\d)?(.txt){1,2}$", "", draft_name)
                date_received = get_child_text(node, "date-received")

                state = ""
                tags = []
                missref_generation = ""
                for child in node.childNodes:
                    if child.nodeType == Node.ELEMENT_NODE and child.localName == "state":
                        state = child.firstChild.data
                        # state has some extra annotations encoded, parse
                        # them out
                        if '*R' in state:
                            tags.append("ref")
                            state = state.replace("*R", "")
                        if '*A' in state:
                            tags.append("iana")
                            state = state.replace("*A", "")
                        m = re.search(r"\(([0-9]+)G\)", state)
                        if m:
                            missref_generation = m.group(1)
                            state = state.replace("(%sG)" % missref_generation, "")

                # AUTH48 link
                auth48 = ""
                for child in node.childNodes:
                    if child.nodeType == Node.ELEMENT_NODE and child.localName == "auth48-url":
                        auth48 = child.firstChild.data

                # cluster link (if it ever gets implemented)
                cluster = ""
                for child in node.childNodes:
                    if child.nodeType == Node.ELEMENT_NODE and child.localName == "cluster-url":
                        cluster = child.firstChild.data

                refs = []
                for child in node.childNodes:
                    if child.nodeType == Node.ELEMENT_NODE and child.localName == "normRef":
                        ref_name = get_child_text(child, "ref-name")
                        ref_state = get_child_text(child, "ref-state")
                        in_queue = ref_state.startswith("IN-QUEUE")
                        refs.append((ref_name, ref_state, in_queue))

                drafts.append((draft_name, date_received, state, tags, missref_generation, stream, auth48, cluster, refs))

            elif event == pulldom.START_ELEMENT and node.tagName == "section":
                name = node.getAttribute('name')
                if name.startswith("IETF"):
                    stream = "ietf"
                elif name.startswith("IAB"):
                    stream = "iab"
                elif name.startswith("IRTF"):
                    stream = "irtf"
                elif name.startswith("INDEPENDENT"):
                    stream = "ise"
                else:
                    stream = None
                    warnings.append("unrecognized section " + name)
        except Exception as e:
            log("Exception when processing an RFC queue entry: %s" % e)
            log("node: %s" % node)
            raise
            
    return drafts, warnings

def update_drafts_from_queue(drafts):
    """Given a list of parsed drafts from the RFC Editor queue, update the
    documents in the database. Return those that were changed."""

    tag_mapping = {
        'IANA': DocTagName.objects.get(slug='iana'),
        'REF':  DocTagName.objects.get(slug='ref')
    }

    slookup = dict((s.slug, s)
                   for s in State.objects.filter(used=True, type=StateType.objects.get(slug="draft-rfceditor")))
    state_mapping = {
        'AUTH': slookup['auth'],
        'AUTH48': slookup['auth48'],
        'AUTH48-DONE': slookup['auth48-done'],
        'EDIT': slookup['edit'],
        'IANA': slookup['iana'],
        'IESG': slookup['iesg'],
        'ISR': slookup['isr'],
        'ISR-AUTH': slookup['isr-auth'],
        'REF': slookup['ref'],
        'RFC-EDITOR': slookup['rfc-edit'],
        'TI': slookup['tooling-issue'],
        'TO': slookup['timeout'],
        'MISSREF': slookup['missref'],
    }

    system = Person.objects.get(name="(System)")

    warnings = []

    names = [t[0] for t in drafts]

    drafts_in_db = dict((d.name, d)
                        for d in Document.objects.filter(type="draft", name__in=names))

    changed = set()

    for name, date_received, state, tags, missref_generation, stream, auth48, cluster, refs in drafts:
        if name not in drafts_in_db:
            warnings.append("unknown document %s" % name)
            continue

        if not state or state not in state_mapping:
            warnings.append("unknown state '%s' for %s" % (state, name))
            continue

        d = drafts_in_db[name]

        prev_state = d.get_state("draft-rfceditor")
        next_state = state_mapping[state]
        events = []

        # check if we've noted it's been received
        if d.get_state_slug("draft-iesg") == "ann" and not prev_state and not d.latest_event(DocEvent, type="rfc_editor_received_announcement"):
            e = DocEvent(doc=d, rev=d.rev, by=system, type="rfc_editor_received_announcement")
            e.desc = "Announcement was received by RFC Editor"
            e.save()
            send_mail_text(None, "iesg-secretary@ietf.org", None,
                           '%s in RFC Editor queue' % d.name,
                           'The announcement for %s has been received by the RFC Editor.' % d.name)
            # change draft-iesg state to RFC Ed Queue
            prev_iesg_state = State.objects.get(used=True, type="draft-iesg", slug="ann")
            next_iesg_state = State.objects.get(used=True, type="draft-iesg", slug="rfcqueue")

            d.set_state(next_iesg_state)
            e = add_state_change_event(d, system, prev_iesg_state, next_iesg_state)
            if e:
                events.append(e)
            e = update_action_holders(d, prev_iesg_state, next_iesg_state)
            if e:
                events.append(e)
            changed.add(name)
            
        # check draft-rfceditor state
        if prev_state != next_state:
            d.set_state(next_state)

            e = new_state_change_event(d, system, prev_state, next_state)  # unsaved
            if e:
                if auth48:
                    e.desc = re.sub(r"(<b>.*</b>)", "<a href=\"%s\">\\1</a>" % auth48, e.desc)
                e.save()
                events.append(e)

            if auth48:
                # Create or update the auth48 URL whether or not this is a state expected to have one.
                d.documenturl_set.update_or_create(
                    tag_id='auth48',  # look up existing based on this field
                    defaults=dict(url=auth48)  # create or update with this field
                )
            else:
                # Remove any existing auth48 URL when an update does not have one.
                d.documenturl_set.filter(tag_id='auth48').delete()

            changed.add(name)

        t = DocTagName.objects.filter(slug__in=tags)
        if set(t) != set(d.tags.all()):
            d.tags.clear()
            d.tags.set(t)
            changed.add(name)

        if events:
            d.save_with_history(events)


    # remove tags and states for those not in the queue anymore
    for d in Document.objects.exclude(name__in=names).filter(states__type="draft-rfceditor").distinct():
        d.tags.remove(*list(tag_mapping.values()))
        d.unset_state("draft-rfceditor")
        # we do not add a history entry here - most likely we already
        # have something that explains what happened
        changed.add(name)

    return changed, warnings


def parse_index(response):
    """Parse RFC Editor index XML into a bunch of tuples."""

    def normalize_std_name(std_name):
        # remove zero padding
        prefix = std_name[:3]
        if prefix in ("RFC", "FYI", "BCP", "STD"):
            try:
                return prefix + str(int(std_name[3:]))
            except ValueError:
                pass
        return std_name

    def extract_doc_list(parentNode, tagName):
        l = []
        for u in parentNode.getElementsByTagName(tagName):
            for d in u.getElementsByTagName("doc-id"):
                l.append(normalize_std_name(d.firstChild.data))
        return l

    also_list = {}
    data = []
    events = pulldom.parse(response)
    for event, node in events:
        try:
            if event == pulldom.START_ELEMENT and node.tagName in ["bcp-entry", "fyi-entry", "std-entry"]:
                events.expandNode(node)
                node.normalize()
                bcpid = normalize_std_name(get_child_text(node, "doc-id"))
                doclist = extract_doc_list(node, "is-also")
                for docid in doclist:
                    if docid in also_list:
                        also_list[docid].append(bcpid)
                    else:
                        also_list[docid] = [bcpid]

            elif event == pulldom.START_ELEMENT and node.tagName == "rfc-entry":
                events.expandNode(node)
                node.normalize()
                rfc_number = int(get_child_text(node, "doc-id")[3:])
                title = get_child_text(node, "title")

                authors = []
                for author in node.getElementsByTagName("author"):
                    authors.append(get_child_text(author, "name"))

                d = node.getElementsByTagName("date")[0]
                year = int(get_child_text(d, "year"))
                month = get_child_text(d, "month")
                month = ["January","February","March","April","May","June","July","August","September","October","November","December"].index(month)+1
                rfc_published_date = datetime.date(year, month, 1)

                current_status = get_child_text(node, "current-status").title()

                updates = extract_doc_list(node, "updates") 
                updated_by = extract_doc_list(node, "updated-by")
                obsoletes = extract_doc_list(node, "obsoletes") 
                obsoleted_by = extract_doc_list(node, "obsoleted-by")
                pages = get_child_text(node, "page-count")
                stream = get_child_text(node, "stream")
                wg = get_child_text(node, "wg_acronym")
                if wg and ((wg == "NON WORKING GROUP") or len(wg) > 15):
                    wg = None

                l = []
                for fmt in node.getElementsByTagName("format"):
                    l.append(get_child_text(fmt, "file-format"))
                file_formats = (",".join(l)).lower()

                abstract = ""
                for abstract in node.getElementsByTagName("abstract"):
                    abstract = get_child_text(abstract, "p")

                draft = get_child_text(node, "draft")
                if draft and re.search(r"-\d\d$", draft):
                    draft = draft[0:-3]

                if len(node.getElementsByTagName("errata-url")) > 0:
                    has_errata = 1
                else:
                    has_errata = 0

                data.append((rfc_number,title,authors,rfc_published_date,current_status,updates,updated_by,obsoletes,obsoleted_by,[],draft,has_errata,stream,wg,file_formats,pages,abstract))
        except Exception as e:
            log("Exception when processing an RFC index entry: %s" % e)
            log("node: %s" % node)
            raise
    for d in data:
        k = "RFC%d" % d[0]
        if k in also_list:
            d[9].extend(also_list[k])
    return data


def update_docs_from_rfc_index(
    index_data, errata_data, skip_older_than_date: Optional[datetime.date] = None
) -> Iterator[tuple[int, list[str], Document, bool]]:
    """Given parsed data from the RFC Editor index, update the documents in the database

    Returns an iterator that yields (rfc_number, change_list, doc, rfc_published) for the
    RFC document and, if applicable, the I-D that it came from.

    The skip_older_than_date is a bare date, not a datetime.
    """
    # Create dict mapping doc-id to list of errata records that apply to it
    errata: dict[str, list[dict]] = {}
    for item in errata_data:
        name = item["doc-id"]
        if name.upper().startswith("RFC"):
            name = f"RFC{int(name[3:])}"  # removes leading 0s on the rfc number
        if not name in errata:
            errata[name] = []
        errata[name].append(item)

    std_level_mapping = {
        "Standard": StdLevelName.objects.get(slug="std"),
        "Internet Standard": StdLevelName.objects.get(slug="std"),
        "Draft Standard": StdLevelName.objects.get(slug="ds"),
        "Proposed Standard": StdLevelName.objects.get(slug="ps"),
        "Informational": StdLevelName.objects.get(slug="inf"),
        "Experimental": StdLevelName.objects.get(slug="exp"),
        "Best Current Practice": StdLevelName.objects.get(slug="bcp"),
        "Historic": StdLevelName.objects.get(slug="hist"),
        "Unknown": StdLevelName.objects.get(slug="unkn"),
    }

    stream_mapping = {
        "IETF": StreamName.objects.get(slug="ietf"),
        "INDEPENDENT": StreamName.objects.get(slug="ise"),
        "IRTF": StreamName.objects.get(slug="irtf"),
        "IAB": StreamName.objects.get(slug="iab"),
        "Legacy": StreamName.objects.get(slug="legacy"),
    }

    tag_has_errata = DocTagName.objects.get(slug="errata")
    tag_has_verified_errata = DocTagName.objects.get(slug="verified-errata")
    relationship_obsoletes = DocRelationshipName.objects.get(slug="obs")
    relationship_updates = DocRelationshipName.objects.get(slug="updates")
    rfc_published_state = State.objects.get(type_id="rfc", slug="published")

    system = Person.objects.get(name="(System)")

    first_sync_creating_subseries = not Document.objects.filter(type_id__in=["bcp","std","fyi"]).exists()

    for (
        rfc_number,
        title,
        authors,
        rfc_published_date,
        current_status,
        updates,
        updated_by,
        obsoletes,
        obsoleted_by,
        also,
        draft_name,
        has_errata,
        stream,
        wg,
        file_formats,
        pages,
        abstract,
    ) in index_data:
        if skip_older_than_date and rfc_published_date < skip_older_than_date:
            # speed up the process by skipping old entries (n.b., the comparison above is a
            # lexical comparison between "YYYY-MM-DD"-formatted dates)
            continue

        # we assume two things can happen: we get a new RFC, or an
        # attribute has been updated at the RFC Editor (RFC Editor
        # attributes take precedence over our local attributes)
        rfc_events = []
        rfc_changes = []
        rfc_published = False

        # Find the draft, if any
        draft = None
        if draft_name:
            try:
                draft = Document.objects.get(name=draft_name, type_id="draft")
            except Document.DoesNotExist:
                pass
                # Logging below warning turns out to be unhelpful - there are many references
                # to such things in the index:
                # * all april-1 RFCs have an internal name that looks like a draft name, but there 
                # was never such a draft. More of these will exist in the future
                # * Several documents were created with out-of-band input to the RFC-editor, for a
                # variety of reasons.
                #
                # What this exposes is that the rfc-index needs to stop talking about these things.
                # If there is no draft to point to, don't point to one, even if there was an RPC
                # internal name in use (and in the RPC database). This will be a requirement on the
                # reimplementation of the creation of the rfc-index.
                # 
                # log(f"Warning: RFC index for {rfc_number} referred to unknown draft {draft_name}")

        # Find or create the RFC document
        creation_args: dict[str, Optional[Union[str, int]]] = {"name": f"rfc{rfc_number}"}
        if draft:
            creation_args.update(
                {
                    "title": draft.title,
                    "stream": draft.stream,
                    "group": draft.group,
                    "abstract": draft.abstract,
                    "pages": draft.pages,
                    "words": draft.words,
                    "std_level": draft.std_level,
                    "ad": draft.ad,
                    "external_url": draft.external_url,
                    "uploaded_filename": draft.uploaded_filename,
                    "note": draft.note,
                }
            )
        doc, created_rfc = Document.objects.get_or_create(
            rfc_number=rfc_number, type_id="rfc", defaults=creation_args
        )
        if created_rfc:
            rfc_changes.append(f"created document {prettify_std_name(doc.name)}")
            doc.set_state(rfc_published_state)
            if draft:
                doc.formal_languages.set(draft.formal_languages.all())
                for author in draft.documentauthor_set.all():
                    # Copy the author but point at the new doc. 
                    # See https://docs.djangoproject.com/en/4.2/topics/db/queries/#copying-model-instances
                    author.pk = None
                    author.id = None
                    author._state.adding = True
                    author.document = doc
                    author.save()

        if draft:
            draft_events = []
            draft_changes = []

            # Ensure the draft is in the "rfc" state and move its files to the archive
            # if necessary.
            if draft.get_state_slug() != "rfc":
                draft.set_state(
                    State.objects.get(used=True, type="draft", slug="rfc")
                )
                move_draft_files_to_archive(draft, draft.rev)
                draft_changes.append(f"changed state to {draft.get_state()}")

            # Ensure the draft and rfc are linked with a "became_rfc" relationship
            r, created_relateddoc = RelatedDocument.objects.get_or_create(
                source=draft, target=doc, relationship_id="became_rfc"
            )
            if created_relateddoc:
                change = "created {rel_name} relationship between {pretty_draft_name} and {pretty_rfc_name}".format(
                    rel_name=r.relationship.name.lower(),
                    pretty_draft_name=prettify_std_name(draft_name),
                    pretty_rfc_name=prettify_std_name(doc.name),
                )
                draft_changes.append(change)
                rfc_changes.append(change)

            # Always set the "draft-iesg" state. This state should be set for all drafts, so
            # log a warning if it is not set. What should happen here is that ietf stream
            # RFCs come in as "rfcqueue" and are set to "pub" when they appear in the RFC index.
            # Other stream documents should normally be "idexists" and be left that way. The
            # code here *actually* leaves "draft-iesg" state alone if it is "idexists" or "pub",
            # and changes any other state to "pub". If unset, it changes it to "idexists".
            # This reflects historical behavior and should probably be updated, but a migration
            # of existing drafts (and validation of the change) is needed before we change the
            # handling.
            prev_iesg_state = draft.get_state("draft-iesg")
            if prev_iesg_state is None:
                log(f'Warning while processing {doc.name}: {draft.name} has no "draft-iesg" state')
                new_iesg_state = State.objects.get(type_id="draft-iesg", slug="idexists")
            elif prev_iesg_state.slug not in ("pub", "idexists"):
                if prev_iesg_state.slug != "rfcqueue":
                    log(
                        'Warning while processing {}: {} is in "draft-iesg" state {} (expected "rfcqueue")'.format(
                            doc.name, draft.name, prev_iesg_state.slug
                        )
                    )
                new_iesg_state = State.objects.get(type_id="draft-iesg", slug="pub")
            else:
                new_iesg_state = prev_iesg_state

            if new_iesg_state != prev_iesg_state:
                draft.set_state(new_iesg_state)
                draft_changes.append(f"changed {new_iesg_state.type.label} to {new_iesg_state}")
                e = update_action_holders(draft, prev_iesg_state, new_iesg_state)
                if e:
                    draft_events.append(e)

            # If the draft and RFC streams agree, move draft to "pub" stream state. If not, complain.
            if draft.stream != doc.stream:
                log("Warning while processing {}: draft {} stream is {} but RFC stream is {}".format(
                    doc.name, draft.name, draft.stream, doc.stream
                ))
            elif draft.stream.slug in ["iab", "irtf", "ise"]:
                stream_slug = f"draft-stream-{draft.stream.slug}"
                prev_state = draft.get_state(stream_slug)
                if prev_state is not None and prev_state.slug != "pub":
                    new_state = State.objects.select_related("type").get(used=True, type__slug=stream_slug, slug="pub")
                    draft.set_state(new_state)
                    draft_changes.append(
                        f"changed {new_state.type.label} to {new_state}"
                    )
                    e = update_action_holders(draft, prev_state, new_state)
                    if e:
                        draft_events.append(e)
            if draft_changes:
                draft_events.append(
                    DocEvent.objects.create(
                        doc=draft,
                        rev=doc.rev,
                        by=system,
                        type="sync_from_rfc_editor",
                        desc=f"Received changes through RFC Editor sync ({', '.join(draft_changes)})",
                    )
                )
                draft.save_with_history(draft_events)
                yield rfc_number, draft_changes, draft, False  # yield changes to the draft

        # check attributes
        verbed = "set" if created_rfc else "changed"
        if title != doc.title:
            doc.title = title
            rfc_changes.append(f"{verbed} title to '{doc.title}'")

        if abstract and abstract != doc.abstract:
            doc.abstract = abstract
            rfc_changes.append(f"{verbed} abstract to '{doc.abstract}'")

        if pages and int(pages) != doc.pages:
            doc.pages = int(pages)
            rfc_changes.append(f"{verbed} pages to {doc.pages}")

        if std_level_mapping[current_status] != doc.std_level:
            doc.std_level = std_level_mapping[current_status]
            rfc_changes.append(f"{verbed} standardization level to {doc.std_level}")

        if doc.stream != stream_mapping[stream]:
            doc.stream = stream_mapping[stream]
            rfc_changes.append(f"{verbed} stream to {doc.stream}")

        if doc.get_state() != rfc_published_state:
            doc.set_state(rfc_published_state)
            rfc_changes.append(f"{verbed} {rfc_published_state.type.label} to {rfc_published_state}")

        # if we have no group assigned, check if RFC Editor has a suggestion
        if not doc.group:  
            if wg:
                doc.group = Group.objects.get(acronym=wg)
                rfc_changes.append(f"set group to {doc.group}")
            else:
                doc.group = Group.objects.get(
                    type="individ"
                )  # fallback for newly created doc

        if not doc.latest_event(type="published_rfc"):
            e = DocEvent(doc=doc, rev=doc.rev, type="published_rfc")
            # unfortunately, rfc_published_date doesn't include the correct day
            # at the moment because the data only has month/year, so
            # try to deduce it
            #
            # Note: This is in done PST8PDT to preserve compatibility with events created when
            # USE_TZ was False. The published_rfc event was created with a timestamp whose
            # server-local datetime (PST8PDT) matched the publication date from the RFC index.
            # When switching to USE_TZ=True, the timestamps were migrated so they still
            # matched the publication date in PST8PDT. When interpreting the event timestamp
            # as a publication date, you must treat it in the PST8PDT time zone. The
            # RPC_TZINFO constant in ietf.utils.timezone is defined for this purpose.
            d = datetime_from_date(rfc_published_date, RPC_TZINFO)
            synthesized = timezone.now().astimezone(RPC_TZINFO)
            if abs(d - synthesized) > datetime.timedelta(days=60):
                synthesized = d
            else:
                direction = -1 if (d - synthesized).total_seconds() < 0 else +1
                while synthesized.month != d.month or synthesized.year != d.year:
                    synthesized += datetime.timedelta(days=direction)
            e.time = synthesized
            e.by = system
            e.desc = "RFC published"
            e.save()
            rfc_events.append(e)

            rfc_changes.append(
                f"added RFC published event at {e.time.strftime('%Y-%m-%d')}"
            )
            rfc_published = True

        def parse_relation_list(l):
            res = []
            for x in l:
                for a in Document.objects.filter(name=x.lower(), type_id="rfc"):
                    if a not in res:
                        res.append(a)
            return res

        for x in parse_relation_list(obsoletes):
            if not RelatedDocument.objects.filter(
                source=doc, target=x, relationship=relationship_obsoletes
            ):
                r = RelatedDocument.objects.create(
                    source=doc, target=x, relationship=relationship_obsoletes
                )
                rfc_changes.append(
                    "created {rel_name} relation between {src_name} and {tgt_name}".format(
                        rel_name=r.relationship.name.lower(),
                        src_name=prettify_std_name(r.source.name),
                        tgt_name=prettify_std_name(r.target.name),
                    )
                )

        for x in parse_relation_list(updates):
            if not RelatedDocument.objects.filter(
                source=doc, target=x, relationship=relationship_updates
            ):
                r = RelatedDocument.objects.create(
                    source=doc, target=x, relationship=relationship_updates
                )
                rfc_changes.append(
                    "created {rel_name} relation between {src_name} and {tgt_name}".format(
                        rel_name=r.relationship.name.lower(),
                        src_name=prettify_std_name(r.source.name),
                        tgt_name=prettify_std_name(r.target.name),
                    )
                )

        if also:
            # recondition also to have proper subseries document names:
            conditioned_also = []
            for a in also:
                a = a.lower()
                subseries_slug = a[:3]
                if subseries_slug not in ["bcp", "std", "fyi"]:
                    log(f"Unexpected 'also' relationship of {a} encountered for {doc}")
                    next
                maybe_number = a[3:].strip()
                if not maybe_number.isdigit():
                    log(f"Unexpected 'also' subseries element identifier {a} encountered for {doc}")
                    next
                else:
                    subseries_number = int(maybe_number)
                    conditioned_also.append(f"{subseries_slug}{subseries_number}") # Note the lack of leading zeros
            also = conditioned_also

            for a in also:
                subseries_doc_name = a
                subseries_slug=a[:3]
                # Leaving most things to the default intentionally
                # Of note, title and stream are left to the defaults of "" and none.
                subseries_doc, created = Document.objects.get_or_create(type_id=subseries_slug, name=subseries_doc_name)
                if created:
                    if first_sync_creating_subseries:
                        subseries_doc.docevent_set.create(type=f"{subseries_slug}_history_marker", by=system, desc=f"No history of this {subseries_slug.upper()} document is currently available in the datatracker before this point")
                        subseries_doc.docevent_set.create(type=f"{subseries_slug}_doc_created", by=system, desc=f"Imported {subseries_doc_name} into the datatracker via sync to the rfc-index")
                    else:
                        subseries_doc.docevent_set.create(type=f"{subseries_slug}_doc_created", by=system, desc=f"Created {subseries_doc_name} via sync to the rfc-index")
                _, relationship_created = subseries_doc.relateddocument_set.get_or_create(relationship_id="contains", target=doc)
                if relationship_created:
                    if first_sync_creating_subseries:
                        subseries_doc.docevent_set.create(type="sync_from_rfc_editor", by=system, desc=f"Imported membership of {doc.name} in {subseries_doc.name} via sync to the rfc-index")
                        rfc_events.append(doc.docevent_set.create(type=f"{subseries_slug}_history_marker", by=system, desc=f"No history of {subseries_doc.name.upper()} is currently available in the datatracker before this point"))
                        rfc_events.append(doc.docevent_set.create(type="sync_from_rfc_editor", by=system, desc=f"Imported membership of {doc.name} in {subseries_doc.name} via sync to the rfc-index"))
                    else:
                        subseries_doc.docevent_set.create(type="sync_from_rfc_editor", by=system, desc=f"Added {doc.name} to {subseries_doc.name}")
                        rfc_events.append(doc.docevent_set.create(type="sync_from_rfc_editor", by=system, desc=f"Added {doc.name} to {subseries_doc.name}"))

        for subdoc in doc.related_that("contains"):
            if subdoc.name not in also:
                assert(not first_sync_creating_subseries)
                subseries_doc.relateddocument_set.filter(target=subdoc).delete()
                rfc_events.append(doc.docevent_set.create(type="sync_from_rfc_editor", by=system, desc=f"Removed {doc.name} from {subseries_doc.name}"))
                subseries_doc.docevent_set.create(type="sync_from_rfc_editor", by=system, desc=f"Removed {doc.name} from {subseries_doc.name}")

        doc_errata = errata.get(f"RFC{rfc_number}", [])
        all_rejected = doc_errata and all(
            er["errata_status_code"] == "Rejected" for er in doc_errata
        )
        if has_errata and not all_rejected:
            if not doc.tags.filter(pk=tag_has_errata.pk).exists():
                doc.tags.add(tag_has_errata)
                rfc_changes.append("added Errata tag")
            has_verified_errata = any(
                [er["errata_status_code"] == "Verified" for er in doc_errata]
            )
            if (
                has_verified_errata
                and not doc.tags.filter(pk=tag_has_verified_errata.pk).exists()
            ):
                doc.tags.add(tag_has_verified_errata)
                rfc_changes.append("added Verified Errata tag")
        else:
            if doc.tags.filter(pk=tag_has_errata.pk):
                doc.tags.remove(tag_has_errata)
                if all_rejected:
                    rfc_changes.append("removed Errata tag (all errata rejected)")
                else:
                    rfc_changes.append("removed Errata tag")
            if doc.tags.filter(pk=tag_has_verified_errata.pk):
                doc.tags.remove(tag_has_verified_errata)
                rfc_changes.append("removed Verified Errata tag")

        if rfc_changes:
            rfc_events.append(
                DocEvent.objects.create(
                    doc=doc,
                    rev=doc.rev,
                    by=system,
                    type="sync_from_rfc_editor",
                    desc=f"Received changes through RFC Editor sync ({', '.join(rfc_changes)})",
                )
            )
            doc.save_with_history(rfc_events)
            yield rfc_number, rfc_changes, doc, rfc_published  # yield changes to the RFC
    
    if first_sync_creating_subseries:
        # First - create the known subseries documents that have ghosted. 
        # The RFC editor (as of 31 Oct 2023) claims these subseries docs do not exist.
        # The datatracker, on the other hand, will say that the series doc currently contains no RFCs.
        for name in ["fyi17", "std1", "bcp12", "bcp113", "bcp66"]:
            # Leaving most things to the default intentionally
            # Of note, title and stream are left to the defaults of "" and none.
            subseries_doc, created = Document.objects.get_or_create(type_id=name[:3], name=name)
            if not created:
                log(f"Warning: {name} unexpectedly already exists")
            else:
                subseries_slug = name[:3]
                subseries_doc.docevent_set.create(type=f"{subseries_slug}_history_marker", by=system, desc=f"No history of this {subseries_slug.upper()} document is currently available in the datatracker before this point")


        RelatedDocument.objects.filter(
            Q(originaltargetaliasname__startswith="bcp") |
            Q(originaltargetaliasname__startswith="std") |
            Q(originaltargetaliasname__startswith="fyi")
        ).annotate(
            subseries_target=Subquery(
                Document.objects.filter(name=OuterRef("originaltargetaliasname")).values_list("pk",flat=True)[:1]
            )
        ).update(target=F("subseries_target"))
        RelatedDocHistory.objects.filter(
            Q(originaltargetaliasname__startswith="bcp") |
            Q(originaltargetaliasname__startswith="std") |
            Q(originaltargetaliasname__startswith="fyi")
        ).annotate(
            subseries_target=Subquery(
                Document.objects.filter(name=OuterRef("originaltargetaliasname")).values_list("pk",flat=True)[:1]
            )
        ).update(target=F("subseries_target"))
        IprDocRel.objects.filter(
            Q(originaldocumentaliasname__startswith="bcp") |
            Q(originaldocumentaliasname__startswith="std") |
            Q(originaldocumentaliasname__startswith="fyi")
        ).annotate(
            subseries_target=Subquery(
                Document.objects.filter(name=OuterRef("originaldocumentaliasname")).values_list("pk",flat=True)[:1]
            )
        ).update(document=F("subseries_target"))


def post_approved_draft(url, name):
    """Post an approved draft to the RFC Editor so they can retrieve
    the data from the Datatracker and start processing it. Returns
    response and error (empty string if no error)."""

    if settings.SERVER_MODE != "production":
        log(f"In production, would have posted RFC-Editor notification of approved I-D '{name}' to '{url}'")
        return "", ""

    # HTTP basic auth
    username = "dtracksync"
    password = settings.RFC_EDITOR_SYNC_PASSWORD
    headers = {
            "Content-type": "application/x-www-form-urlencoded",
            "Accept": "text/plain",
            "Authorization": "Basic %s" % force_str(base64.encodebytes(smart_bytes("%s:%s" % (username, password)))).replace("\n", ""),
        }

    log("Posting RFC-Editor notification of approved Internet-Draft '%s' to '%s'" % (name, url))
    text = error = ""

    try:
        r = requests.post(
            url,
            headers=headers,
            data=smart_bytes(urlencode({ 'draft': name })),
            timeout=settings.DEFAULT_REQUESTS_TIMEOUT,
        )

        log("RFC-Editor notification result for Internet-Draft '%s': %s:'%s'" % (name, r.status_code, r.text))

        if r.status_code != 200:
            raise RuntimeError("Status code is not 200 OK (it's %s)." % r.status_code)

        if force_str(r.text) != "OK":
            raise RuntimeError('Response is not "OK" (it\'s "%s").' % r.text)

    except Exception as e:
        # catch everything so we don't leak exceptions, convert them
        # into string instead
        msg = "Exception on RFC-Editor notification for Internet-Draft '%s': %s: %s" % (name, type(e), str(e))
        log(msg)
        if settings.SERVER_MODE == 'test':
            debug.say(msg)
        error = str(e)

    return text, error
