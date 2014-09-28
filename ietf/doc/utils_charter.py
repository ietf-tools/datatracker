import re, datetime, os

from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

from ietf.doc.models import NewRevisionDocEvent, WriteupDocEvent, BallotPositionDocEvent
from ietf.person.models import Person
from ietf.utils.history import find_history_active_at
from ietf.utils.mail import send_mail_text

def charter_name_for_group(group):
    if group.type_id == "rg":
        top_org = "irtf"
    else:
        top_org = "ietf"

    return "charter-%s-%s" % (top_org, group.acronym)

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
    
def email_state_changed(request, doc, text):
    to = [e.strip() for e in doc.notify.replace(';', ',').split(',')]
    if not to:
        return
    
    text = strip_tags(text)
    text += "\n\n"
    text += "URL: %s" % (settings.IDTRACKER_BASE_URL + doc.get_absolute_url())

    send_mail_text(request, to, None,
                   "State changed: %s-%s" % (doc.canonical_name(), doc.rev),
                   text)

def generate_ballot_writeup(request, doc):
    e = WriteupDocEvent()
    e.type = "changed_ballot_writeup_text"
    e.by = request.user.person
    e.doc = doc
    e.desc = u"Ballot writeup was generated"
    e.text = unicode(render_to_string("doc/charter/ballot_writeup.txt"))
    e.save()
    
    return e

def default_action_text(group, charter, by):
    if next_approved_revision(group.charter.rev) == "01":
        action = "Formed"
    else:
        action = "Rechartered"

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
                                   milestones=group.groupmilestone_set.filter(state="charter"),
                                   ad_email=group.ad.role_email("ad") if group.ad else None,
                                   action_type=action,
                                   ))

    e.save()
    return e

def default_review_text(group, charter, by):
    e = WriteupDocEvent(doc=charter, by=by)
    e.by = by
    e.type = "changed_review_announcement"
    e.desc = "%s review text was changed" % group.type.name
    e.text = render_to_string("doc/charter/review_text.txt",
                              dict(group=group,
                                   charter_url=settings.IDTRACKER_BASE_URL + charter.get_absolute_url(),
                                   charter_text=read_charter_text(charter),
                                   chairs=group.role_set.filter(name="chair"),
                                   secr=group.role_set.filter(name="secr"),
                                   techadv=group.role_set.filter(name="techadv"),
                                   milestones=group.groupmilestone_set.filter(state="charter"),
                                   ad_email=group.ad.role_email("ad") if group.ad else None,
                                   review_date=(datetime.date.today() + datetime.timedelta(weeks=1)).isoformat(),
                                   review_type="new" if group.state_id == "proposed" else "recharter",
                                   )
                              )
    e.save()
    return e

def generate_issue_ballot_mail(request, doc, ballot):
    active_ads = Person.objects.filter(email__role__name="ad", email__role__group__state="active").distinct()
    
    seen = []
    positions = []
    for p in BallotPositionDocEvent.objects.filter(doc=doc, type="changed_ballot_position", ballot=ballot).order_by("-time", '-id').select_related('ad'):
        if p.ad not in seen:
            positions.append(p)
            seen.append(p.ad)

    # format positions and setup blocking and non-blocking comments
    ad_feedback = []
    seen = set()
    active_ad_positions = []
    inactive_ad_positions = []
    for p in positions:
        if p.ad in seen:
            continue

        seen.add(p.ad)
        
        def formatted(val):
            if val:
                return "[ X ]"
            else:
                return "[   ]"

        fmt = u"%-21s%-6s%-6s%-8s%-7s" % (
            p.ad.plain_name(),
            formatted(p.pos_id == "yes"),
            formatted(p.pos_id == "no"),
            formatted(p.pos_id == "block"),
            formatted(p.pos_id == "abstain"),
            )

        if p.ad in active_ads:
            active_ad_positions.append(fmt)
            if not p.pos or not p.pos.blocking:
                p.discuss = ""
            if p.comment or p.discuss:
                ad_feedback.append(p)
        else:
            inactive_ad_positions.append(fmt)
        
    active_ad_positions.sort()
    inactive_ad_positions.sort()
    ad_feedback.sort(key=lambda p: p.ad.plain_name())

    e = doc.latest_event(WriteupDocEvent, type="changed_action_announcement")
    approval_text = e.text if e else ""

    e = doc.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text")
    ballot_writeup = e.text if e else ""

    return render_to_string("doc/charter/issue_ballot_mail.txt",
                            dict(doc=doc,
                                 doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                                 active_ad_positions=active_ad_positions,
                                 inactive_ad_positions=inactive_ad_positions,
                                 ad_feedback=ad_feedback,
                                 approval_text=approval_text,
                                 ballot_writeup=ballot_writeup,
                                 )
                            )

        
