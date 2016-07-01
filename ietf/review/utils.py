import datetime
from collections import defaultdict

from django.contrib.sites.models import Site

from ietf.group.models import Group, Role
from ietf.doc.models import Document, DocEvent, State, LastCallDocEvent
from ietf.iesg.models import TelechatDate
from ietf.ietfauth.utils import has_role, is_authorized_in_doc_stream
from ietf.review.models import ReviewRequest, ReviewRequestStateName, ReviewTypeName
from ietf.utils.mail import send_mail
from ietf.doc.utils import extract_complete_replaces_ancestor_mapping_for_docs

def active_review_teams():
    # if there's a ReviewTeamResult defined, it's a review team
    return Group.objects.filter(state="active").exclude(reviewteamresult=None)

def can_request_review_of_doc(user, doc):
    if not user.is_authenticated():
        return False

    return is_authorized_in_doc_stream(user, doc)

def can_manage_review_requests_for_team(user, team):
    if not user.is_authenticated():
        return False

    return Role.objects.filter(name__in=["secretary", "delegate"], person__user=user, group=team).exists() or has_role(user, "Secretariat")

def make_new_review_request_from_existing(review_req):
    obj = ReviewRequest()
    obj.time = review_req.time
    obj.type = review_req.type
    obj.doc = review_req.doc
    obj.team = review_req.team
    obj.deadline = review_req.deadline
    obj.requested_rev = review_req.requested_rev
    obj.state = ReviewRequestStateName.objects.get(slug="requested")
    return obj

def email_about_review_request(request, review_req, subject, msg, by, notify_secretary, notify_reviewer):
    """Notify possibly both secretary and reviewer about change, skipping
    a party if the change was done by that party."""

    def extract_email_addresses(objs):
        if any(o.person == by for o in objs if o):
            return []
        else:
            return [o.formatted_email() for o in objs if o]

    to = []

    if notify_secretary:
        to += extract_email_addresses(Role.objects.filter(name__in=["secretary", "delegate"], group=review_req.team).distinct())
    if notify_reviewer:
        to += extract_email_addresses([review_req.reviewer])

    if not to:
        return

    send_mail(request, list(set(to)), None, subject, "doc/mail/review_request_changed.txt", {
        "domain": Site.objects.get_current().domain,
        "review_req": review_req,
        "msg": msg,
    })

def assign_review_request_to_reviewer(request, review_req, reviewer):
    assert review_req.state_id in ("requested", "accepted")

    if reviewer == review_req.reviewer:
        return

    if review_req.reviewer:
        email_about_review_request(
            request, review_req,
            "Unassigned from review of %s" % review_req.doc.name,
            "%s has cancelled your assignment to the review." % request.user.person,
            by=request.user.person, notify_secretary=False, notify_reviewer=True)

    review_req.state = ReviewRequestStateName.objects.get(slug="requested")
    review_req.reviewer = reviewer
    review_req.save()

    DocEvent.objects.create(
        type="changed_review_request",
        doc=review_req.doc,
        by=request.user.person,
        desc="Request for {} review by {} is assigned to {}".format(
            review_req.type.name,
            review_req.team.acronym.upper(),
            review_req.reviewer.person if review_req.reviewer else "(None)",
        ),
    )

    email_about_review_request(
        request, review_req,
        "Assigned to review of %s" % review_req.doc.name,
        "%s has assigned you to review the document." % request.user.person,
        by=request.user.person, notify_secretary=False, notify_reviewer=True)

def suggested_review_requests_for_team(team):
    def fixup_deadline(d):
        if d.time() == datetime.time(0):
            d = d - datetime.timedelta(seconds=1) # 23:59:59 is treated specially in the view code
        return d

    seen_deadlines = {}

    requests = {}

    if True:
        # in Last Call
        last_call_type = ReviewTypeName.objects.get(slug="lc")
        last_call_docs = Document.objects.filter(states=State.objects.get(type="draft-iesg", slug="lc", used=True))
        last_call_expires = { e.doc_id: e.expires for e in LastCallDocEvent.objects.order_by("time", "id") }
        for doc in last_call_docs:
            deadline = fixup_deadline(last_call_expires.get(doc.pk)) if doc.pk in last_call_expires else datetime.datetime.now()

            if deadline > seen_deadlines.get(doc.pk, datetime.datetime.max):
                continue

            requests[doc.pk] = ReviewRequest(
                time=None,
                type=last_call_type,
                doc=doc,
                team=team,
                deadline=deadline,
            )

            seen_deadlines[doc.pk] = deadline


    if True:
        # on Telechat Agenda
        telechat_dates = list(TelechatDate.objects.active().order_by('date').values_list("date", flat=True)[:4])

        telechat_type = ReviewTypeName.objects.get(slug="telechat")
        telechat_deadline_delta = datetime.timedelta(days=2)
        telechat_docs = Document.objects.filter(docevent__telechatdocevent__telechat_date__in=telechat_dates)
        for doc in telechat_docs:
            d = doc.telechat_date()
            if d not in telechat_dates:
                continue

            deadline = datetime.datetime.combine(d - telechat_deadline_delta, datetime.time(23, 59, 59))

            if deadline > seen_deadlines.get(doc.pk, datetime.datetime.max):
                continue

            requests[doc.pk] = ReviewRequest(
                time=None,
                type=telechat_type,
                doc=doc,
                team=team,
                deadline=deadline,
            )

            seen_deadlines[doc.pk] = deadline

    # filter those with existing requests
    existing_requests = defaultdict(list)
    for r in ReviewRequest.objects.filter(doc__in=requests.iterkeys()):
        existing_requests[r.doc_id].append(r)

    def blocks(existing, request):
        return (existing.doc_id == request.doc_id
                and existing.reviewed_rev == request.doc.rev
                and existing.state_id not in ("part-completed", "rejected", "overtaken"))

    res = [r for r in requests.itervalues() if not any(blocks(e, r) for e in existing_requests[r.doc_id])]
    res.sort(key=lambda r: (r.deadline, r.doc_id))
    return res

def extract_revision_ordered_review_requests_for_documents(queryset, names):
    names = set(names)

    replaces = extract_complete_replaces_ancestor_mapping_for_docs(names)

    requests_for_each_doc = defaultdict(list)
    for r in queryset.filter(doc__in=set(e for l in replaces.itervalues() for e in l) | names).order_by("-reviewed_rev", "-time", "-id").iterator():
        requests_for_each_doc[r.doc_id].append(r)

    # now collect in breadth-first order to keep the revision order intact
    res = defaultdict(list)
    for name in names:
        front = replaces.get(name, [])
        res[name].extend(requests_for_each_doc.get(name, []))

        while front:
            replaces_reqs = []
            for replaces_name in front:
                reqs = requests_for_each_doc.get(replaces_name, [])
                if reqs:
                    replaces_reqs.append(reqs)

            # in case there are multiple replaces, move the ones with
            # the latest reviews up front
            replaces_reqs.sort(key=lambda l: l[0].time, reverse=True)

            for reqs in replaces_reqs:
                res[name].extend(reqs)

            # move one level down
            front = [n for l in requests_for_each_doc.get(replaces_name, []) for n in l]

    return res
