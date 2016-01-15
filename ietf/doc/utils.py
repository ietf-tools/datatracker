import os
import re
import urllib
import math
import datetime

from django.conf import settings
from django.db.models.query import EmptyQuerySet
from django.forms import ValidationError
from django.utils.html import strip_tags, escape
from django.core.urlresolvers import reverse as urlreverse

from ietf.doc.models import Document, DocHistory, State
from ietf.doc.models import DocAlias, RelatedDocument, BallotType, DocReminder
from ietf.doc.models import DocEvent, BallotDocEvent, NewRevisionDocEvent, StateDocEvent
from ietf.doc.models import save_document_in_history
from ietf.name.models import DocReminderTypeName, DocRelationshipName
from ietf.group.models import Role
from ietf.ietfauth.utils import has_role
from ietf.utils import draft, markup_txt
from ietf.utils.mail import send_mail
from ietf.mailtrigger.utils import gather_address_lists

import debug              # pyflakes:ignore

#TODO FIXME - it would be better if this lived in ietf/doc/mails.py, but there's
#        an import order issue to work out.
def email_update_telechat(request, doc, text):
    (to, cc) = gather_address_lists('doc_telechat_details_changed',doc=doc)

    if not to:
        return

    text = strip_tags(text)
    send_mail(request, to, None,
              "Telechat update notice: %s" % doc.file_tag(),
              "doc/mail/update_telechat.txt",
              dict(text=text,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()),
              cc=cc)

def get_state_types(doc):
    res = []

    if not doc:
        return res

    res.append(doc.type_id)

    if doc.type_id == "draft":
        if doc.stream_id and doc.stream_id != "legacy":
            res.append("draft-stream-%s" % doc.stream_id)

        res.append("draft-iesg")
        res.append("draft-iana-review")
        res.append("draft-iana-action")
        res.append("draft-rfceditor")

    return res

def get_tags_for_stream_id(stream_id):
    if stream_id == "ietf":
        return ["w-expert", "w-extern", "w-merge", "need-aut", "w-refdoc", "w-refing", "rev-wg", "rev-wglc", "rev-ad", "rev-iesg", "sheph-u", "no-adopt", "other"]
    elif stream_id == "iab":
        return ["need-ed", "w-part", "w-review", "need-rev", "sh-f-up"]
    elif stream_id == "irtf":
        return ["need-ed", "need-sh", "w-dep", "need-rev", "iesg-com"]
    elif stream_id == "ise":
        return ["w-dep", "w-review", "need-rev", "iesg-com"]
    else:
        return []

def can_adopt_draft(user, doc):
    if not user.is_authenticated():
        return False

    if has_role(user, "Secretariat"):
        return True

    #The IRTF chair can adopt a draft into any RG
    if has_role(user, "IRTF Chair"):
        return (doc.stream_id in (None, "irtf")
                and doc.group.type_id == "individ")

    return (doc.stream_id in (None, "ietf", "irtf")
            and doc.group.type_id == "individ"
            and Role.objects.filter(name__in=("chair", "delegate", "secr"),
                                    group__type__in=("wg", "rg"),
                                    group__state="active",
                                    person__user=user).exists())


def two_thirds_rule( recused=0 ):
    # For standards-track, need positions from 2/3 of the non-recused current IESG.
    active = Role.objects.filter(name="ad",group__type="area",group__state="active").count()
    return int(math.ceil((active - recused) * 2.0/3.0))

def needed_ballot_positions(doc, active_positions):
    '''Returns text answering the question "what does this document
    need to pass?".  The return value is only useful if the document
    is currently in IESG evaluation.'''
    yes = [p for p in active_positions if p and p.pos_id == "yes"]
    noobj = [p for p in active_positions if p and p.pos_id == "noobj"]
    blocking = [p for p in active_positions if p and p.pos.blocking]
    recuse = [p for p in active_positions if p and p.pos_id == "recuse"]

    answer = []
    if len(yes) < 1:
        answer.append("Needs a YES.")
    if blocking:
        if len(blocking) == 1:
            answer.append("Has a %s." % blocking[0].pos.name.upper())
        else:
            if blocking[0].pos.name.upper().endswith('S'):
                answer.append("Has %d %ses." % (len(blocking), blocking[0].pos.name.upper()))
            else:
                answer.append("Has %d %ss." % (len(blocking), blocking[0].pos.name.upper()))
    needed = 1
    if doc.type_id == "draft" and doc.intended_std_level_id in ("bcp", "ps", "ds", "std"):
        needed = two_thirds_rule(recused=len(recuse))
    elif doc.type_id == "statchg":
        if isinstance(doc,Document):
            related_set = doc.relateddocument_set
        elif isinstance(doc,DocHistory):
            related_set = doc.relateddochistory_set
        else:
            related_set = EmptyQuerySet()
        for rel in related_set.filter(relationship__slug__in=['tops', 'tois', 'tohist', 'toinf', 'tobcp', 'toexp']):
            if (rel.target.document.std_level.slug in ['bcp','ps','ds','std']) or (rel.relationship.slug in ['tops','tois','tobcp']):
                needed = two_thirds_rule(recused=len(recuse))
                break
    else:
        if len(yes) < 1:
            return " ".join(answer)

    have = len(yes) + len(noobj)
    if have < needed:
        more = needed - have
        if more == 1:
            answer.append("Needs one more YES or NO OBJECTION position to pass.")
        else:
            answer.append("Needs %d more YES or NO OBJECTION positions to pass." % more)
    else:
        if blocking:
            answer.append("Has enough positions to pass once %s positions are resolved." % blocking[0].pos.name.upper())
        else:
            answer.append("Has enough positions to pass.")

    return " ".join(answer)

def create_ballot_if_not_open(doc, by, ballot_slug, time=None):
    if not doc.ballot_open(ballot_slug):
        if time:
            e = BallotDocEvent(type="created_ballot", by=by, doc=doc, time=time)
        else:
            e = BallotDocEvent(type="created_ballot", by=by, doc=doc)
        e.ballot_type = BallotType.objects.get(doc_type=doc.type, slug=ballot_slug)
        e.desc = u'Created "%s" ballot' % e.ballot_type.name
        e.save()

def close_ballot(doc, by, ballot_slug):
    if doc.ballot_open(ballot_slug):
        e = BallotDocEvent(type="closed_ballot", doc=doc, by=by)
        e.ballot_type = BallotType.objects.get(doc_type=doc.type,slug=ballot_slug)
        e.desc = 'Closed "%s" ballot' % e.ballot_type.name
        e.save()

def close_open_ballots(doc, by):
    for t in BallotType.objects.filter(doc_type=doc.type_id):
        close_ballot(doc, by, t.slug )

def augment_with_start_time(docs):
    """Add a started_time attribute to each document with the time of
    the first revision."""
    docs = list(docs)

    docs_dict = {}
    for d in docs:
        docs_dict[d.pk] = d
        d.start_time = None

    seen = set()

    for e in DocEvent.objects.filter(type="new_revision", doc__in=docs).order_by('time'):
        if e.doc_id in seen:
            continue

        docs_dict[e.doc_id].start_time = e.time
        seen.add(e.doc_id)

    return docs

def get_chartering_type(doc):
    chartering = ""
    if doc.get_state_slug() not in ("notrev", "approved"):
        if doc.group.state_id in ("proposed", "bof"):
            chartering = "initial"
        elif doc.group.state_id == "active":
            chartering = "rechartering"

    return chartering

def augment_events_with_revision(doc, events):
    """Take a set of events for doc and add a .rev attribute with the
    revision they refer to by checking NewRevisionDocEvents."""

    event_revisions = list(NewRevisionDocEvent.objects.filter(doc=doc).order_by('time', 'id').values('id', 'rev', 'time'))

    if doc.type_id == "draft" and doc.get_state_slug() == "rfc":
        # add fake "RFC" revision
        e = doc.latest_event(type="published_rfc")
        if e:
            event_revisions.append(dict(id=e.id, time=e.time, rev="RFC"))
            event_revisions.sort(key=lambda x: (x["time"], x["id"]))

    for e in sorted(events, key=lambda e: (e.time, e.id), reverse=True):
        while event_revisions and (e.time, e.id) < (event_revisions[-1]["time"], event_revisions[-1]["id"]):
            event_revisions.pop()

        if event_revisions:
            cur_rev = event_revisions[-1]["rev"]
        else:
            cur_rev = "00"

        e.rev = cur_rev

def add_links_in_new_revision_events(doc, events, diff_revisions):
    """Add direct .txt links and diff links to new_revision events."""
    prev = None

    diff_urls = dict(((name, revision), url) for name, revision, time, url in diff_revisions)

    for e in sorted(events, key=lambda e: (e.time, e.id)):
        if not e.type == "new_revision":
            continue

        if not (e.doc.name, e.rev) in diff_urls:
            continue

        full_url = diff_url = diff_urls[(e.doc.name, e.rev)]

        if doc.type_id in "draft": # work around special diff url for drafts
            full_url = "https://tools.ietf.org/id/" + diff_url + ".txt"

        # build links
        links = r'<a href="%s">\1</a>' % full_url
        if prev:
            links += ""

        if prev != None:
            links += ' (<a href="%s?url1=%s&url2=%s">diff from previous</a>)' % (settings.RFCDIFF_BASE_URL, urllib.quote(prev, safe="~"), urllib.quote(diff_url, safe="~"))

        # replace the bold filename part
        e.desc = re.sub(r"<b>(.+-[0-9][0-9].txt)</b>", links, e.desc)

        prev = diff_url


def get_document_content(key, filename, split=True, markup=True):
    try:
        with open(filename, 'rb') as f:
            raw_content = f.read()
    except IOError:
        error = "Error; cannot read ("+key+")"
        return error

    if markup:
        return markup_txt.markup(raw_content, split)
    else:
        return raw_content

def add_state_change_event(doc, by, prev_state, new_state, prev_tags=[], new_tags=[], timestamp=None):
    """Add doc event to explain that state change just happened."""
    if prev_state and new_state:
        assert prev_state.type_id == new_state.type_id

    if prev_state == new_state and set(prev_tags) == set(new_tags):
        return None

    def tags_suffix(tags):
        return (u"::" + u"::".join(t.name for t in tags)) if tags else u""

    e = StateDocEvent(doc=doc, by=by)
    e.type = "changed_state"
    e.state_type = (prev_state or new_state).type
    e.state = new_state
    e.desc = "%s changed to <b>%s</b>" % (e.state_type.label, new_state.name + tags_suffix(new_tags))
    if prev_state:
        e.desc += " from %s" % (prev_state.name + tags_suffix(prev_tags))
    if timestamp:
        e.time = timestamp
    e.save()
    return e

def update_reminder(doc, reminder_type_slug, event, due_date):
    reminder_type = DocReminderTypeName.objects.get(slug=reminder_type_slug)

    try:
        reminder = DocReminder.objects.get(event__doc=doc, type=reminder_type, active=True)
    except DocReminder.DoesNotExist:
        reminder = None

    if due_date:
        # activate/update reminder
        if not reminder:
            reminder = DocReminder(type=reminder_type)

        reminder.event = event
        reminder.due = due_date
        reminder.active = True
        reminder.save()
    else:
        # deactivate reminder
        if reminder:
            reminder.active = False
            reminder.save()

def prettify_std_name(n, spacing=" "):
    if re.match(r"(rfc|bcp|fyi|std)[0-9]+", n):
        return n[:3].upper() + spacing + n[3:]
    else:
        return n

def nice_consensus(consensus):
    mapping = {
        None: "Unknown",
        True: "Yes",
        False: "No"
        }
    return mapping[consensus]

def has_same_ballot(doc, date1, date2=datetime.date.today()):
    """ Test if the most recent ballot created before the end of date1
        is the same as the most recent ballot created before the
        end of date 2. """
    ballot1 = doc.latest_event(BallotDocEvent,type='created_ballot',time__lt=date1+datetime.timedelta(days=1))
    ballot2 = doc.latest_event(BallotDocEvent,type='created_ballot',time__lt=date2+datetime.timedelta(days=1))
    return ballot1==ballot2

def make_notify_changed_event(request, doc, by, new_notify, time=None):

    # FOR REVIEW: This preserves the behavior from when
    # drafts and charters had separate edit_notify
    # functions. If it should be unified, there should
    # also be a migration function cause historic
    # events to match
    if doc.type.slug=='charter':
        event_type = 'changed_document'
        save_document_in_history(doc)
    else:
        event_type = 'added_comment'

    e = DocEvent(type=event_type, doc=doc, by=by)
    e.desc = "Notification list changed to %s" % (escape(new_notify) or "none")
    if doc.notify:
        e.desc += " from %s" % escape(doc.notify)
    if time:
        e.time = time
    e.save()

    return e

def update_telechat(request, doc, by, new_telechat_date, new_returning_item=None):
    from ietf.doc.models import TelechatDocEvent

    on_agenda = bool(new_telechat_date)

    prev = doc.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
    prev_returning = bool(prev and prev.returning_item)
    prev_telechat = prev.telechat_date if prev else None
    prev_agenda = bool(prev_telechat)

    if new_returning_item == None:
        returning = prev_returning
    else:
        returning = new_returning_item

    if returning == prev_returning and new_telechat_date == prev_telechat:
        # fully updated, nothing to do
        return

    # auto-set returning item _ONLY_ if the caller did not provide a value
    if (     new_returning_item != None
         and on_agenda
         and prev_agenda
         and new_telechat_date != prev_telechat
         and prev_telechat < datetime.date.today()
         and has_same_ballot(doc,prev.telechat_date)
       ):
        returning = True

    e = TelechatDocEvent()
    e.type = "scheduled_for_telechat"
    e.by = by
    e.doc = doc
    e.returning_item = returning
    e.telechat_date = new_telechat_date

    if on_agenda != prev_agenda:
        if on_agenda:
            e.desc = "Placed on agenda for telechat - %s" % (new_telechat_date)
        else:
            e.desc = "Removed from agenda for telechat"
    elif on_agenda and new_telechat_date != prev_telechat:
        e.desc = "Telechat date has been changed to <b>%s</b> from <b>%s</b>" % (
            new_telechat_date, prev_telechat)
    else:
        # we didn't reschedule but flipped returning item bit - let's
        # just explain that
        if returning:
            e.desc = "Set telechat returning item indication"
        else:
            e.desc = "Removed telechat returning item indication"

    e.save()
    email_update_telechat(request, doc, e.desc)

def rebuild_reference_relations(doc,filename=None):
    if doc.type.slug != 'draft':
        return None

    if not filename:
        if doc.get_state_slug() == 'rfc':
            filename=os.path.join(settings.RFC_PATH,doc.canonical_name()+".txt")
        else:
            filename=os.path.join(settings.INTERNET_DRAFT_PATH,doc.filename_with_rev())

    try:
       refs = draft.Draft(draft._gettext(filename), filename).get_refs()
    except IOError as e:
       return { 'errors': ["%s :%s" %  (e.strerror, filename)] }

    doc.relateddocument_set.filter(relationship__slug__in=['refnorm','refinfo','refold','refunk']).delete()

    warnings = []
    errors = []
    unfound = set()
    for ( ref, refType ) in refs.iteritems():
        refdoc = DocAlias.objects.filter( name=ref )
        count = refdoc.count()
        if count == 0:
            unfound.add( "%s" % ref )
            continue
        elif count > 1:
            errors.append("Too many DocAlias objects found for %s"%ref)
        else:
            # Don't add references to ourself
            if doc != refdoc[0].document:
                RelatedDocument.objects.get_or_create( source=doc, target=refdoc[ 0 ], relationship=DocRelationshipName.objects.get( slug='ref%s' % refType ) )
    if unfound:
        warnings.append('There were %d references with no matching DocAlias'%len(unfound))

    ret = {}
    if errors:
        ret['errors']=errors
    if warnings:
        ret['warnings']=warnings
    if unfound:
        ret['unfound']=list(unfound)

    return ret

def set_replaces_for_document(request, doc, new_replaces, by, email_subject, email_comment=""):
    addrs = gather_address_lists('doc_replacement_changed',doc=doc)
    to = set(addrs.to)
    cc = set(addrs.cc)

    relationship = DocRelationshipName.objects.get(slug='replaces')
    old_replaces = doc.related_that_doc("replaces")

    for d in old_replaces:
        if d not in new_replaces:
            other_addrs = gather_address_lists('doc_replacement_changed',doc=d.document)
            to.update(other_addrs.to)
            cc.update(other_addrs.cc)
            RelatedDocument.objects.filter(source=doc, target=d, relationship=relationship).delete()
            if not RelatedDocument.objects.filter(target=d, relationship=relationship):
                s = 'active' if d.document.expires > datetime.datetime.now() else 'expired'
                d.document.set_state(State.objects.get(type='draft', slug=s))

    for d in new_replaces:
        if d not in old_replaces:
            other_addrs = gather_address_lists('doc_replacement_changed',doc=d.document)
            to.update(other_addrs.to)
            cc.update(other_addrs.cc)
            RelatedDocument.objects.create(source=doc, target=d, relationship=relationship)
            d.document.set_state(State.objects.get(type='draft', slug='repl'))

    e = DocEvent(doc=doc, by=by, type='changed_document')
    new_replaces_names = u", ".join(d.name for d in new_replaces) or u"None"
    old_replaces_names = u", ".join(d.name for d in old_replaces) or u"None"
    e.desc = u"This document now replaces <b>%s</b> instead of %s" % (new_replaces_names, old_replaces_names)
    e.save()

    # make sure there are no lingering suggestions duplicating new replacements
    RelatedDocument.objects.filter(source=doc, target__in=new_replaces, relationship="possibly-replaces").delete()

    email_desc = e.desc.replace(", ", "\n    ")

    if email_comment:
        email_desc += "\n" + email_comment

    from ietf.doc.mails import html_to_text

    send_mail(request, list(to),
              "DraftTracker Mail System <iesg-secretary@ietf.org>",
              email_subject,
              "doc/mail/change_notice.txt",
              dict(text=html_to_text(email_desc),
                   doc=doc,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()),
              cc=list(cc))

def check_common_doc_name_rules(name):
    """Check common rules for document names for use in forms, throws
    ValidationError in case there's a problem."""

    errors = []
    if re.search("[^a-z0-9-]", name):
        errors.append("The name may only contain digits, lowercase letters and dashes.")
    if re.search("--", name):
        errors.append("Please do not put more than one hyphen between any two words in the name.")
    if re.search("-[0-9]{2}$", name):
        errors.append("This name looks like ends in a version number. -00 will be added automatically. Please adjust the end of the name.")

    if errors:
        raise ValidationError(errors)

def get_initial_notify(doc,extra=None):
    # With the mailtrigger based changes, a document's notify should start empty
    receivers = []

    if extra:
        if isinstance(extra,basestring):
            extra = extra.split(', ')
        receivers.extend(extra)

    return ", ".join(set([x.strip() for x in receivers]))

def uppercase_std_abbreviated_name(name):
    if re.match('(rfc|bcp|std|fyi) ?[0-9]+$', name):
        return name.upper()
    else:
        return name

def crawl_history(doc):
    # return document history data for inclusion in doc.json (used by timeline)
    def get_ancestors(doc):
        ancestors = []
        if hasattr(doc, 'relateddocument_set'):
            for rel in doc.relateddocument_set.filter(relationship__slug='replaces'):
                if rel.target.document not in ancestors:
                    ancestors.append(rel.target.document)
                    ancestors.extend(get_ancestors(rel.target.document))
            return ancestors

    history = {}
    docs = get_ancestors(doc)
    if docs is not None:
        docs.append(doc)
        for d in docs:
            for e in d.docevent_set.filter(type='new_revision').distinct():
                if hasattr(e, 'newrevisiondocevent'):
                    url = urlreverse("doc_view", kwargs=dict(name=d)) + e.newrevisiondocevent.rev + "/"
                    history[url] = {
                        'name': d.name,
                        'rev': e.newrevisiondocevent.rev,
                        'published': e.time.isoformat(),
                        'url': url,
                    }

    if doc.type_id == "draft":
        e = doc.latest_event(type='published_rfc')
    else:
        e = doc.latest_event(type='iesg_approved')
    if e:
        url = urlreverse("doc_view", kwargs=dict(name=e.doc))
        history[url] = {
            'name': e.doc.canonical_name(),
            'rev': e.doc.canonical_name(),
            'published': e.time.isoformat(),
            'url': url
        }
    history = history.values()
    return sorted(history, key=lambda x: x['published'])
