from django.conf import settings
import re

from redesign.group.models import GroupEvent
from ietf.utils.history import find_history_active_at

def add_wg_comment(request, wg, text, ballot=None):
    if request:
        login = request.user.get_profile()
    else:
        login = None

    e = GroupEvent(group=wg, type="added_comment", by=login)
    e.desc = text
    e.save()

def log_state_changed(request, doc, by, prev_state, note=''):
    from doc.models import DocEvent

    e = DocEvent(doc=doc, by=by)
    e.type = "changed_document"
    e.desc = u"State changed to <b>%s</b> from %s" % (
        doc.charter_state.name,
        prev_state.name if prev_state else "None")

    if note:
        e.desc += "<br>%s" % note

    e.save()
    return e

def log_info_changed(request, wg, by, type=None, note=''):
    from group.models import GroupEvent

    e = GroupEvent(group=wg, by=by)
    e.type = "changed_record"
    e.desc = u"Info changed"
    if note:
        e.desc += "<br>%s" % note

    e.save()
    return e

def get_charter_for_revision(charter, r):
    if r == None:
        return None
    else:
        l = list(charter.history_set.filter(rev=r).order_by('-time'))
        if l != []:
            return l[0]
        else:
            return charter

def get_group_for_revision(wg, r):
    if r == None:
        return None
    else:
        l = list(wg.charter.history_set.filter(rev=r).order_by('-time'))
        if l != []:
            o = list(wg.history_set.filter(time__lte=l[0].time).order_by('-time'))
            if o != []:
                return o[0]
            else:
                return wg
        else:
            return wg

def prev_revision(rev):
    m = re.match(r"(?P<major>[0-9][0-9])(-(?P<minor>[0-9][0-9]))?", rev)
    if m.group('minor') and m.group('minor') != "00":
        return "%s-%#02d" % (m.group('major'), int(m.group('minor')) - 1)
    else:
        return None

def next_revision(rev):
    if rev == "":
        return "00-00"
    m = re.match(r"(?P<major>[0-9][0-9])(-(?P<minor>[0-9][0-9]))?", rev)
    if m.group('minor'):
        return "%s-%#02d" % (m.group('major'), int(m.group('minor')) + 1)
    else:
        return "%s-00" % (m.group('major'))

def next_approved_revision(rev):
    if rev == "":
        return "01"
    m = re.match(r"(?P<major>[0-9][0-9])(-(?P<minor>[0-9][0-9]))?", rev)
    return "%#02d" % (int(m.group('major')) + 1)

def update_telechat(request, doc, by, new_telechat_date):
    from doc.models import TelechatDocEvent
    
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
            e.desc = "Placed on agenda for telechat - %s by %s" % (
                new_telechat_date, by.name)
        else:
            e.desc = "Removed from agenda for telechat by %s" % by.name
    elif on_agenda and new_telechat_date != prev_telechat:
        e.desc = "Telechat date has been changed to <b>%s</b> from <b>%s</b> by %s" % (new_telechat_date, prev_telechat, by.name)

    e.save()
