import re, datetime, os, shutil

from django.template.loader import render_to_string
from django.conf import settings
from django.utils.encoding import smart_text

from ietf.doc.models import NewRevisionDocEvent, WriteupDocEvent 
from ietf.group.models import ChangeStateGroupEvent
from ietf.name.models import GroupStateName
from ietf.utils.history import find_history_active_at
from ietf.utils.mail import parse_preformatted
from ietf.mailtrigger.utils import gather_address_lists
from ietf.utils.log import log
from ietf.group.utils import save_group_in_history

def charter_name_for_group(group):
    if group.type_id == "rg":
        top_org = "irtf"
    else:
        top_org = "ietf"

    return "charter-%s-%s" % (top_org, group.acronym)

def split_charter_name(charter_name):
    top_org, group_acronym = charter_name.split("-", 2)[1:]
    return top_org, group_acronym

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

def change_group_state_after_charter_approval(group, by):
    new_state = GroupStateName.objects.get(slug="active")
    if group.state == new_state:
        return None

    save_group_in_history(group)
    group.state = new_state
    group.time = datetime.datetime.now()
    group.save()

    # create an event for the group state change, too
    e = ChangeStateGroupEvent(group=group, type="changed_state")
    e.time = group.time
    e.by = by
    e.state_id = "active"
    e.desc = "Charter approved, group active"
    e.save()

    return e

def fix_charter_revision_after_approval(charter, by):
    # according to spec, 00-02 becomes 01, so copy file and record new revision
    try:
        old = os.path.join(charter.get_file_path(), '%s-%s.txt' % (charter.canonical_name(), charter.rev))
        new = os.path.join(charter.get_file_path(), '%s-%s.txt' % (charter.canonical_name(), next_approved_revision(charter.rev)))
        shutil.copy(old, new)
    except IOError:
        log("There was an error copying %s to %s" % (old, new))

    events = []
    e = NewRevisionDocEvent(doc=charter, by=by, type="new_revision")
    e.rev = next_approved_revision(charter.rev)
    e.desc = "New version available: <b>%s-%s.txt</b>" % (charter.canonical_name(), e.rev)
    e.save()
    events.append(e)

    charter.rev = e.rev
    charter.save_with_history(events)

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
    
def generate_ballot_writeup(request, doc):
    e = WriteupDocEvent()
    e.type = "changed_ballot_writeup_text"
    e.by = request.user.person
    e.doc = doc
    e.desc = u"Ballot writeup was generated"
    e.text = unicode(render_to_string("doc/charter/ballot_writeup.txt"))

    # caller is responsible for saving, if necessary
    return e

def default_action_text(group, charter, by):
    if next_approved_revision(group.charter.rev) == "01":
        action = "Formed"
    else:
        action = "Rechartered"

    addrs = gather_address_lists('ballot_approved_charter',doc=charter,group=group).as_strings(compact=False)
    e = WriteupDocEvent(doc=charter, by=by)
    e.by = by
    e.type = "changed_action_announcement"
    e.desc = "%s action text was changed" % group.type.name
    e.text = render_to_string("doc/charter/action_text.txt",
                              dict(group=group,
                                   charter_url=settings.IDTRACKER_BASE_URL + charter.get_absolute_url(),
                                   charter_text=read_charter_text(charter),
                                   chairs=group.role_set.filter(name="chair"),
                                   secr=group.role_set.filter(name="secr"),
                                   techadv=group.role_set.filter(name="techadv"),
                                   ads=group.role_set.filter(name='ad'),
                                   parent_ads=group.parent.role_set.filter(name='ad'),
                                   milestones=group.groupmilestone_set.filter(state="charter"),
                                   action_type=action,
                                   to=addrs.to,
                                   cc=addrs.cc,
                                   ))

    # caller is responsible for saving, if necessary
    return e

def derive_new_work_text(review_text,group):
    addrs= gather_address_lists('charter_external_review_new_work',group=group).as_strings()
    (m,_,_) = parse_preformatted(review_text,
                                 override={'To':addrs.to,
                                           'Cc':addrs.cc,
                                           'From':'The IESG <iesg@ietf.org>',
                                           'Reply_to':'<iesg@ietf.org>'})
    if not addrs.cc:
        del m['Cc']
    return smart_text(m.as_string())

def default_review_text(group, charter, by):
    now = datetime.datetime.now()
    addrs = gather_address_lists('charter_external_review',group=group).as_strings(compact=False)

    e1 = WriteupDocEvent(doc=charter, by=by)
    e1.by = by
    e1.type = "changed_review_announcement"
    e1.desc = "%s review text was changed" % group.type.name
    e1.text = render_to_string("doc/charter/review_text.txt",
                              dict(group=group,
                                    charter_url=settings.IDTRACKER_BASE_URL + charter.get_absolute_url(),
                                    charter_text=read_charter_text(charter),
                                    chairs=group.role_set.filter(name="chair"),
                                    secr=group.role_set.filter(name="secr"),
                                    ads=group.role_set.filter(name='ad'),
                                    parent_ads=group.parent.role_set.filter(name='ad'),
                                    techadv=group.role_set.filter(name="techadv"),
                                    milestones=group.groupmilestone_set.filter(state="charter"),
                                    review_date=(datetime.date.today() + datetime.timedelta(weeks=1)).isoformat(),
                                    review_type="new" if group.state_id == "proposed" else "recharter",
                                    to=addrs.to,
                                    cc=addrs.cc,
                                   )
                              )
    e1.time = now

    e2 = WriteupDocEvent(doc=charter, by=by)
    e2.by = by
    e2.type = "changed_new_work_text"
    e2.desc = "%s review text was changed" % group.type.name
    e2.text = derive_new_work_text(e1.text,group)
    e2.time = now

    # caller is responsible for saving, if necessary
    return (e1, e2)

def generate_issue_ballot_mail(request, doc, ballot):
    
    addrs=gather_address_lists('ballot_issued',doc=doc).as_strings()

    return render_to_string("doc/charter/issue_ballot_mail.txt",
                            dict(doc=doc,
                                 doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                                 to = addrs.to,
                                 cc = addrs.cc,
                                 )
                            )

        
