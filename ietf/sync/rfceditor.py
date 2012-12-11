import re, urllib2, json, email, socket
from xml.dom import pulldom, Node

from django.utils.http import urlquote

from ietf.utils.mail import send_mail_text

from ietf.doc.models import *
from ietf.person.models import *
from ietf.name.models import *
from ietf.doc.utils import add_state_change_event

QUEUE_URL = "http://www.rfc-editor.org/queue2.xml"
INDEX_URL = "http://www.rfc-editor.org/rfc/rfc-index.xml"

MIN_QUEUE_RESULTS = 10
MIN_INDEX_RESULTS = 5000

# Python < 2.7 doesn't have the total_seconds method on datetime.timedelta.
def total_seconds(td):
    return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6

def get_child_text(parent_node, tag_name):
    for node in parent_node.childNodes:
        if node.nodeType == Node.ELEMENT_NODE and node.localName == tag_name:
            return node.firstChild.data
    return None


def fetch_queue_xml(url):
    socket.setdefaulttimeout(30)
    return urllib2.urlopen(url)

def parse_queue(response):
    events = pulldom.parse(response)
    drafts = []
    warnings = []

    for event, node in events:
        if event == pulldom.START_ELEMENT and node.tagName == "entry":
            events.expandNode(node)
            node.normalize()
            draft_name = get_child_text(node, "draft").strip()
            draft_name = re.sub("(-\d\d)?(.txt){1,2}$", "", draft_name)
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

    return drafts, warnings

def update_drafts_from_queue(drafts):
    tag_mapping = {
        'IANA': DocTagName.objects.get(slug='iana'),
        'REF':  DocTagName.objects.get(slug='ref')
    }

    slookup = dict((s.slug, s)
                   for s in State.objects.filter(type=StateType.objects.get(slug="draft-rfceditor")))
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
        'TO': slookup['timeout'],
        'MISSREF': slookup['missref'],
    }

    system = Person.objects.get(name="(System)")

    warnings = []

    names = [t[0] for t in drafts]

    drafts_in_db = dict((d.name, d)
                        for d in Document.objects.filter(type="draft", docalias__name__in=names))

    changed = set()

    for name, date_received, state, tags, missref_generation, stream, auth48, cluster, refs in drafts:
        if name not in drafts_in_db:
            warnings.append("unknown document %s" % name)
            continue

        if not state or state not in state_mapping:
            warnings.append("unknown state '%s'" % state)
            continue

        d = drafts_in_db[name]

        prev_state = d.get_state("draft-rfceditor")
        next_state = state_mapping[state]

        # check if we've noted it's been received
        if d.get_state_slug("draft-iesg") == "ann" and not prev_state and not d.latest_event(DocEvent, type="rfc_editor_received_announcement"):
            e = DocEvent(doc=d, by=system, type="rfc_editor_received_announcement")
            e.desc = "Announcement was received by RFC Editor"
            e.save()
            send_mail_text(None, "iesg-secretary@ietf.org", None,
                           '%s in RFC Editor queue' % d.name,
                           'The announcement for %s has been received by the RFC Editor.' % d.name)


        if prev_state != next_state:
            save_document_in_history(d)

            d.set_state(next_state)

            e = add_state_change_event(d, system, prev_state, next_state)

            if auth48:
                e.desc = re.sub(r"(<b>.*</b>)", "<a href=\"%s\">\\1</a>" % auth48, e.desc)
                e.save()

            changed.add(name)

        t = DocTagName.objects.filter(slug__in=tags)
        if set(t) != set(d.tags.all()):
            d.tags = t
            changed.add(name)


    # remove tags and states for those not in the queue anymore
    for d in Document.objects.exclude(docalias__name__in=names).filter(states__type="draft-rfceditor").distinct():
        d.tags.remove(*tag_mapping.values())
        d.unset_state("draft-rfceditor")
        # we do not add a history entry here - most likely we already
        # have something that explains what happened
        changed.add(name)

    return changed, warnings


def fetch_index_xml(url):
    socket.setdefaulttimeout(30)
    return urllib2.urlopen(url)

def parse_index(response):
    def getDocList(parentNode, tagName):
        l = []
        for u in parentNode.getElementsByTagName(tagName):
            for d in u.getElementsByTagName("doc-id"):
                l.append(d.firstChild.data)
        return l

    also_list = {}
    data = []
    events = pulldom.parse(response)
    for event, node in events:
        if event == pulldom.START_ELEMENT and node.tagName in ["bcp-entry", "fyi-entry", "std-entry"]:
            events.expandNode(node)
            node.normalize()
            bcpid = get_child_text(node, "doc-id")
            doclist = getDocList(node, "is-also")
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

            updates = getDocList(node, "updates") 
            updated_by = getDocList(node, "updated-by")
            obsoletes = getDocList(node, "obsoletes") 
            obsoleted_by = getDocList(node, "obsoleted-by")
            stream = get_child_text(node, "stream")
            wg = get_child_text(node, "wg_acronym")
            if wg and ((wg == "NON WORKING GROUP") or len(wg) > 15):
                wg = None
           
            l = []
            pages = ""
            for fmt in node.getElementsByTagName("format"):
                l.append(get_child_text(fmt, "file-format"))
                if get_child_text(fmt, "file-format") == "ASCII":
                    pages = get_child_text(fmt, "page-count")
            file_formats = (",".join(l)).lower()

            abstract = ""
            for abstract in node.getElementsByTagName("abstract"):
                abstract = get_child_text(abstract, "p")

            draft = get_child_text(node, "draft")
            if draft and re.search("-\d\d$", draft):
                draft = draft[0:-3]

            if len(node.getElementsByTagName("errata-url")) > 0:
                has_errata = 1
            else:
                has_errata = 0

            data.append((rfc_number,title,authors,rfc_published_date,current_status,updates,updated_by,obsoletes,obsoleted_by,[],draft,has_errata,stream,wg,file_formats,pages,abstract))

    for d in data:
        k = "RFC%04d" % d[0]
        if k in also_list:
            d[9].extend(also_list[k])
    return data


def update_docs_from_rfc_index(data, skip_older_than_date=None):
    std_level_mapping = {
        "Standard": StdLevelName.objects.get(slug="std"),
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

    tag_has_errata = DocTagName.objects.get(slug='errata')
    relationship_obsoletes = DocRelationshipName.objects.get(slug="obs")
    relationship_updates = DocRelationshipName.objects.get(slug="updates")

    system = Person.objects.get(name="(System)")

    results = []

    for rfc_number, title, authors, rfc_published_date, current_status, updates, updated_by, obsoletes, obsoleted_by, also, draft, has_errata, stream, wg, file_formats, pages, abstract in data:

        if skip_older_than_date and rfc_published_date < skip_older_than_date:
            # speed up the process by skipping old entries
            continue

        # we assume two things can happen: we get a new RFC, or an
        # attribute has been updated at the RFC Editor (RFC Editor
        # attributes take precedence over our local attributes)

        # make sure we got the document and alias
        created = False
        doc = None
        name = "rfc%s" % rfc_number
        a = DocAlias.objects.filter(name=name).select_related("document")
        if a:
            doc = a[0].document
        else:
            if draft:
                try:
                    doc = Document.objects.get(name=draft)
                except Document.DoesNotExist:
                    pass

            if not doc:
                results.append("created document %s" % name)
                doc = Document.objects.get_or_create(name=name)[0]

            # add alias
            DocAlias.objects.get_or_create(name=name, document=doc)
            results.append("created alias %s to %s" % (name, doc.name))
            created = True

                
        # check attributes
        changed_attributes = {}
        changed_states = []
        created_relations = []
        other_changes = False
        if title != doc.title:
            changed_attributes["title"] = title

        if abstract and abstract != doc.abstract:
            changed_attributes["abstract"] = abstract

        if pages and int(pages) != doc.pages:
            changed_attributes["pages"] = int(pages)

        if std_level_mapping[current_status] != doc.std_level:
            changed_attributes["std_level"] = std_level_mapping[current_status]

        if doc.get_state_slug() != "rfc":
            changed_states.append(State.objects.get(type="draft", slug="rfc"))

        if doc.stream != stream_mapping[stream]:
            changed_attributes["stream"] = stream_mapping[stream]

        if not doc.group and wg:
            changed_attributes["group"] = Group.objects.get(acronym=wg)

        if not doc.latest_event(type="published_rfc"):
            e = DocEvent(doc=doc, type="published_rfc")
            # unfortunately, rfc_published_date doesn't include the correct day
            # at the moment because the data only has month/year, so
            # try to deduce it
            d = datetime.datetime.combine(rfc_published_date, datetime.time())
            synthesized = datetime.datetime.now()
            if abs(d - synthesized) > datetime.timedelta(days=60):
                synthesized = d
            else:
                direction = -1 if total_seconds(d - synthesized) < 0 else +1
                while synthesized.month != d.month or synthesized.year != d.year:
                    synthesized += datetime.timedelta(days=direction)
            e.time = synthesized
            e.by = system
            e.desc = "RFC published"
            e.save()
            other_changes = True

            results.append("Added RFC published event: %s" % e.time.strftime("%Y-%m-%d"))

        for t in ("draft-iesg", "draft-stream-iab", "draft-stream-irtf", "draft-stream-ise"):
            slug = doc.get_state_slug(t)
            if slug and slug != "pub":
                changed_states.append(State.objects.get(type=t, slug="pub"))

        def parse_relation_list(l):
            res = []
            for x in l:
                if x[:3] in ("NIC", "IEN", "STD", "RTR"):
                    # try translating this to RFCs that we can handle
                    # sensibly; otherwise we'll have to ignore them
                    l = DocAlias.objects.filter(name__startswith="rfc", document__docalias__name=x.lower())
                else:
                    l = DocAlias.objects.filter(name=x.lower())

                for a in l:
                    if a not in res:
                        res.append(a)
            return res

        for x in parse_relation_list(obsoletes):
            if not RelatedDocument.objects.filter(source=doc, target=x, relationship=relationship_obsoletes):
                created_relations.append(RelatedDocument(source=doc, target=x, relationship=relationship_obsoletes))

        for x in parse_relation_list(updates):
            if not RelatedDocument.objects.filter(source=doc, target=x, relationship=relationship_updates):
                created_relations.append(RelatedDocument(source=doc, target=x, relationship=relationship_updates))

        if also:
            for a in also:
                a = a.lower()
                if not DocAlias.objects.filter(name=a):
                    DocAlias.objects.create(name=a, document=doc)
                    other_changes = True
                    results.append("Created alias %s to %s" % (a, doc.name))

        if has_errata:
            if not doc.tags.filter(pk=tag_has_errata.pk):
                changed_attributes["tags"] = list(doc.tags.all()) + [tag_has_errata]
        else:
            if doc.tags.filter(pk=tag_has_errata.pk):
                changed_attributes["tags"] = set(doc.tags.all()) - set([tag_has_errata])

        if changed_attributes or changed_states or created_relations or other_changes:
            # apply changes
            save_document_in_history(doc)
            for k, v in changed_attributes.iteritems():
                setattr(doc, k, v)
                results.append("Changed %s to %s on %s" % (k, v, doc.name))

            for s in changed_states:
                doc.set_state(s)
                results.append("Set state %s on %s" % (s, doc.name))

            for o in created_relations:
                o.save()
                results.append("Created %s" % o)

            doc.time = datetime.datetime.now()
            doc.save()

    return results
