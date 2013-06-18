import re, datetime, os

from django.conf import settings

from ietf.group.models import GroupEvent, ChangeStateGroupEvent
from ietf.doc.models import Document, DocAlias, DocHistory, RelatedDocument, DocumentAuthor, DocEvent, NewRevisionDocEvent
from ietf.utils.history import find_history_active_at

def log_state_changed(request, doc, by, prev_state):
    e = DocEvent(doc=doc, by=by)
    e.type = "changed_document"
    e.desc = u"State changed to <b>%s</b> from %s" % (
        doc.get_state().name,
        prev_state.name if prev_state else "None")
    e.save()
    return e

def next_revision(rev):
    if rev == "":
        return "00-00"
    m = re.match(r"(?P<major>[0-9][0-9])(-(?P<minor>[0-9][0-9]))?", rev)
    if m.group('minor'):
        return "%s-%#02d" % (m.group('major'), int(m.group('minor')) + 1)
    else:
        return "%s-00" % (m.group('major'))

def approved_revision(rev):
    if rev == "":
        return ""
    m = re.match(r"(?P<major>[0-9][0-9])(-(?P<minor>[0-9][0-9]))?", rev)
    return m.group('major')

def next_approved_revision(rev):
    if rev == "":
        return "01"
    m = re.match(r"(?P<major>[0-9][0-9])(-(?P<minor>[0-9][0-9]))?", rev)
    return "%#02d" % (int(m.group('major')) + 1)

def read_charter_text(doc):
    filename = os.path.join(settings.CHARTER_PATH, '%s-%s.txt' % (doc.canonical_name(), doc.rev))
    try:
        with open(filename, 'r') as f:
            return f.read()
    except IOError:
        return "Error: couldn't read charter text"

def historic_milestones_for_charter(charter, rev):
    """Return GroupMilestone/GroupMilestoneHistory objects for charter
    document at rev by looking through the history."""

    chartering = "-" in rev
    if chartering:
        need_state = "charter"
    else:
        need_state = "active"

    # slight complication - we can assign milestones to a revision up
    # until the point where the next superseding revision is
    # published, so that time shall be our limit
    revision_event = charter.latest_event(NewRevisionDocEvent, type="new_revision", rev=rev)
    if not revision_event:
        return []

    e = charter.docevent_set.filter(time__gt=revision_event.time, type="new_revision").order_by("time")
    if not chartering:
        e = e.exclude(newrevisiondocevent__rev__contains="-")

    if e:
        # subtract a margen of error to avoid collisions with
        # milestones being published at the same time as the new
        # revision (when approving a charter)
        just_before_next_rev = e[0].time - datetime.timedelta(seconds=5)
    else:
        just_before_next_rev = datetime.datetime.now()

    res = []
    for m in charter.chartered_group.groupmilestone_set.all():
        mh = find_history_active_at(m, just_before_next_rev)
        if mh and mh.state_id == need_state:
            res.append(mh)

    return res
    

def update_telechat(request, doc, by, new_telechat_date):
    # FIXME: reuse function in idrfc/utils.py instead of this one
    # (need to fix auto-setting returning item problem first though)
    from ietf.doc.models import TelechatDocEvent
    
    on_agenda = bool(new_telechat_date)

    prev = doc.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
    prev_telechat = prev.telechat_date if prev else None
    prev_agenda = bool(prev_telechat)
    
    e = TelechatDocEvent()
    e.type = "scheduled_for_telechat"
    e.by = by
    e.doc = doc
    e.telechat_date = new_telechat_date
    
    if on_agenda != prev_agenda:
        if on_agenda:
            e.desc = "Placed on agenda for telechat - %s" % new_telechat_date
        else:
            e.desc = "Removed from agenda for telechat"
        e.save()
    elif on_agenda and new_telechat_date != prev_telechat:
        e.desc = "Telechat date has been changed to <b>%s</b> from <b>%s</b>" % (new_telechat_date, prev_telechat)
        e.save()
