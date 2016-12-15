# code to generate plain-text index files that are placed on
# www.ietf.org in the same directory as the I-Ds

import datetime, os

import pytz

from django.conf import settings
from django.template.loader import render_to_string

from ietf.doc.templatetags.ietf_filters import clean_whitespace
from ietf.doc.models import Document, DocEvent, DocumentAuthor, RelatedDocument, DocAlias, State
from ietf.doc.models import LastCallDocEvent, NewRevisionDocEvent
from ietf.doc.models import IESG_SUBSTATE_TAGS
from ietf.group.models import Group
from ietf.person.models import Person, Email

def all_id_txt():
    # this returns a lot of data so try to be efficient

    # precalculations
    revision_time = dict(NewRevisionDocEvent.objects.filter(type="new_revision", doc__name__startswith="draft-").order_by('time').values_list("doc_id", "time"))

    def formatted_rev_date(name):
        t = revision_time.get(name)
        return t.strftime("%Y-%m-%d") if t else ""

    rfc_aliases = dict(DocAlias.objects.filter(name__startswith="rfc",
                                               document__states=State.objects.get(type="draft", slug="rfc")).values_list("document_id", "name"))

    replacements = dict(RelatedDocument.objects.filter(target__document__states=State.objects.get(type="draft", slug="repl"),
                                                       relationship="replaces").values_list("target__document_id", "source"))


    # we need a distinct to prevent the queries below from multiplying the result
    all_ids = Document.objects.filter(type="draft").order_by('name').exclude(name__startswith="rfc").distinct()

    res = ["\nInternet-Drafts Status Summary\n"]

    def add_line(f1, f2, f3, f4):
        # each line must have exactly 4 tab-separated fields
        res.append(f1 + "\t" + f2 + "\t" + f3 + "\t" + f4)


    inactive_states = ["pub", "watching", "dead"]

    in_iesg_process = all_ids.exclude(states=State.objects.filter(type="draft", slug__in=["rfc","repl"])).filter(states__in=list(State.objects.filter(type="draft-iesg").exclude(slug__in=inactive_states))).only("name", "rev")

    # handle those actively in the IESG process
    for d in in_iesg_process:
        state = d.get_state("draft-iesg").name
        tags = d.tags.filter(slug__in=IESG_SUBSTATE_TAGS).values_list("name", flat=True)
        if tags:
            state += "::" + "::".join(tags)
        add_line(d.name + "-" + d.rev,
                 formatted_rev_date(d.name),
                 "In IESG processing - ID Tracker state <" + state + ">",
                 "",
                 )


    # handle the rest

    not_in_process = all_ids.exclude(pk__in=[d.name for d in in_iesg_process])

    for s in State.objects.filter(type="draft").order_by("order"):
        for name, rev in not_in_process.filter(states=s).values_list("name", "rev"):
            state = s.name
            last_field = ""

            if s.slug == "rfc":
                a = rfc_aliases.get(name)
                if a:
                    last_field = a[3:]
            elif s.slug == "repl":
                state += " replaced by " + replacements.get(name, "0")

            add_line(name + "-" + rev,
                     formatted_rev_date(name),
                     state,
                     last_field,
                    )

    return u"\n".join(res) + "\n"

def file_types_for_drafts():
    """Look in the draft directory and return file types found as dict (name + rev -> [t1, t2, ...])."""
    file_types = {}
    for filename in os.listdir(settings.INTERNET_DRAFT_PATH):
        if filename.startswith("draft-"):
            base, ext = os.path.splitext(filename)
            if ext:
                if base not in file_types:
                    file_types[base] = [ext]
                else:
                    file_types[base].append(ext)

    return file_types

def all_id2_txt():
    # this returns a lot of data so try to be efficient

    drafts = Document.objects.filter(type="draft").exclude(name__startswith="rfc").order_by('name')
    drafts = drafts.select_related('group', 'group__parent', 'ad', 'intended_std_level', 'shepherd', )
    drafts = drafts.prefetch_related("states")

    rfc_aliases = dict(DocAlias.objects.filter(name__startswith="rfc",
                                               document__states=State.objects.get(type="draft", slug="rfc")).values_list("document_id", "name"))

    replacements = dict(RelatedDocument.objects.filter(target__document__states=State.objects.get(type="draft", slug="repl"),
                                                       relationship="replaces").values_list("target__document_id", "source"))

    revision_time = dict(DocEvent.objects.filter(type="new_revision", doc__name__startswith="draft-").order_by('time').values_list("doc_id", "time"))

    file_types = file_types_for_drafts()

    authors = {}
    for a in DocumentAuthor.objects.filter(document__name__startswith="draft-").order_by("order").select_related("author", "author__person").iterator():
        if a.document_id not in authors:
            l = authors[a.document_id] = []
        else:
            l = authors[a.document_id]
        if "@" in a.author.address:
            l.append(u'%s <%s>' % (a.author.person.plain_name().replace("@", ""), a.author.address.replace(",", "")))
        else:
            l.append(a.author.person.plain_name())

    shepherds = dict((e.pk, e.formatted_email().replace('"', ''))
                     for e in Email.objects.filter(shepherd_document_set__type="draft").select_related("person").distinct())
    ads = dict((p.pk, p.formatted_email().replace('"', ''))
               for p in Person.objects.filter(ad_document_set__type="draft").distinct())

    res = []
    for d in drafts:
        state = d.get_state_slug()
        iesg_state = d.get_state("draft-iesg")

        fields = []
        # 0
        fields.append(d.name + "-" + d.rev)
        # 1
        fields.append("-1") # used to be internal numeric identifier, we don't have that anymore
        # 2
        fields.append(d.get_state().name if state else "")
        # 3
        if state == "active":
            s = "I-D Exists"
            if iesg_state:
                s = iesg_state.name
                tags = d.tags.filter(slug__in=IESG_SUBSTATE_TAGS).values_list("name", flat=True)
                if tags:
                    s += "::" + "::".join(tags)
            fields.append(s)
        else:
            fields.append("")
        # 4
        rfc_number = ""
        if state == "rfc":
            a = rfc_aliases.get(d.name)
            if a:
                rfc_number = a[3:]
        fields.append(rfc_number)
        # 5
        repl = ""
        if state == "repl":
            repl = replacements.get(d.name, "")
        fields.append(repl)
        # 6
        t = revision_time.get(d.name)
        fields.append(t.strftime("%Y-%m-%d") if t else "")
        # 7
        group_acronym = ""
        if d.group and d.group.type_id != "area" and d.group.acronym != "none":
            group_acronym = d.group.acronym
        fields.append(group_acronym)
        # 8
        area = ""
        if d.group:
            if d.group.type_id == "area":
                area = d.group.acronym
            elif d.group.type_id == "wg" and d.group.parent and d.group.parent.type_id == "area":
                area = d.group.parent.acronym
        fields.append(area)
        # 9 responsible AD name
        fields.append(unicode(d.ad) if d.ad else "")
        # 10
        fields.append(d.intended_std_level.name if d.intended_std_level else "")
        # 11
        lc_expires = ""
        if iesg_state and iesg_state.slug == "lc":
            e = d.latest_event(LastCallDocEvent, type="sent_last_call")
            if e:
                lc_expires = e.expires.strftime("%Y-%m-%d")
        fields.append(lc_expires)
        # 12
        doc_file_types = file_types.get(d.name + "-" + d.rev, [])
        doc_file_types.sort()           # make the order consistent (and the result testable)
        fields.append(",".join(doc_file_types) if state == "active" else "")
        # 13
        fields.append(clean_whitespace(d.title)) # FIXME: we should make sure this is okay in the database and in submit
        # 14
        fields.append(u", ".join(authors.get(d.name, [])))
        # 15
        fields.append(shepherds.get(d.shepherd_id, ""))
        # 16 Responsible AD name and email
        fields.append(ads.get(d.ad_id, ""))

        #
        res.append(u"\t".join(fields))

    return render_to_string("idindex/all_id2.txt", {'data': u"\n".join(res) })

def active_drafts_index_by_group(extra_values=()):
    """Return active drafts grouped into their corresponding
    associated group, for spitting out draft index."""

    # this returns a lot of data so try to be efficient

    active_state = State.objects.get(type="draft", slug="active")

    groups_dict = dict((g.id, g) for g in Group.objects.all())

    extracted_values = ("name", "rev", "title", "group_id") + extra_values

    docs_dict = dict((d["name"], d)
                     for d in Document.objects.filter(states=active_state).values(*extracted_values))

    # add initial and latest revision time
    for time, doc_id in NewRevisionDocEvent.objects.filter(type="new_revision", doc__states=active_state).order_by('-time').values_list("time", "doc_id"):
        d = docs_dict.get(doc_id)
        if d:
            if "rev_time" not in d:
                d["rev_time"] = time
            d["initial_rev_time"] = time

    # add authors
    for a in DocumentAuthor.objects.filter(document__states=active_state).order_by("order").select_related("author__person"):
        d = docs_dict.get(a.document_id)
        if d:
            if "authors" not in d:
                d["authors"] = []
            d["authors"].append(a.author.person.plain_ascii()) # This should probably change to .plain_name() when non-ascii names are permitted

    # put docs into groups
    for d in docs_dict.itervalues():
        group = groups_dict.get(d["group_id"])
        if not group:
            continue

        if not hasattr(group, "active_drafts"):
            group.active_drafts = []

        group.active_drafts.append(d)

    groups = [g for g in groups_dict.itervalues() if hasattr(g, "active_drafts")]
    groups.sort(key=lambda g: g.acronym)

    fallback_time = datetime.datetime(1950, 1, 1)
    for g in groups:
        g.active_drafts.sort(key=lambda d: d.get("initial_rev_time", fallback_time))

    return groups
    
def id_index_txt(with_abstracts=False):
    extra_values = ()
    if with_abstracts:
        extra_values = ("abstract",)
    groups = active_drafts_index_by_group(extra_values)

    file_types = file_types_for_drafts()
    for g in groups:
        for d in g.active_drafts:
            # we need to output a multiple extension thing
            types = file_types.get(d["name"] + "-" + d["rev"], "")
            exts = ".txt"
            if ".ps" in types:
                exts += ",.ps"
            if ".pdf" in types:
                exts += ",.pdf"
            d["exts"] = exts

    return render_to_string("idindex/id_index.txt", {
            'groups': groups,
            'time': datetime.datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S %Z"),
            'with_abstracts': with_abstracts,
            })
