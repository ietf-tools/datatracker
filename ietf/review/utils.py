import datetime, re
from collections import defaultdict

from django.db.models import Q, Max
from django.core.urlresolvers import reverse as urlreverse

from ietf.group.models import Group, Role
from ietf.doc.models import Document, DocEvent, State, LastCallDocEvent, DocumentAuthor, DocAlias
from ietf.iesg.models import TelechatDate
from ietf.person.models import Person, Email
from ietf.ietfauth.utils import has_role, is_authorized_in_doc_stream
from ietf.review.models import (ReviewRequest, ReviewRequestStateName, ReviewTypeName,
                                ReviewerSettings, UnavailablePeriod, ReviewWish, NextReviewerInTeam)
from ietf.utils.mail import send_mail
from ietf.doc.utils import extract_complete_replaces_ancestor_mapping_for_docs

def active_review_teams():
    # if there's a ReviewTeamResult defined, it's a review team
    return Group.objects.filter(state="active").exclude(reviewteamresult=None)

def close_review_request_states():
    return ReviewRequestStateName.objects.filter(used=True).exclude(slug__in=["requested", "accepted", "rejected", "part-completed", "completed"])

def can_request_review_of_doc(user, doc):
    if not user.is_authenticated():
        return False

    return is_authorized_in_doc_stream(user, doc)

def can_manage_review_requests_for_team(user, team, allow_non_team_personnel=True):
    if not user.is_authenticated():
        return False

    return (Role.objects.filter(name__in=["secr", "delegate"], person__user=user, group=team).exists()
            or (allow_non_team_personnel and has_role(user, "Secretariat")))

def review_requests_to_list_for_doc(doc):
    request_qs = ReviewRequest.objects.filter(
        state__in=["requested", "accepted", "part-completed", "completed"],
    ).prefetch_related("result")

    doc_names = [doc.name]

    return extract_revision_ordered_review_requests_for_documents(request_qs, doc_names).get(doc.pk, [])

def no_review_from_teams_on_doc(doc, rev):
    return Group.objects.filter(
        reviewrequest__doc=doc,
        reviewrequest__reviewed_rev=rev,
        reviewrequest__state="no-review-version",
    ).distinct()

def unavailability_periods_to_list(past_days=30):
    return UnavailablePeriod.objects.filter(
        Q(end_date=None) | Q(end_date__gte=datetime.date.today() - datetime.timedelta(days=past_days)),
    ).order_by("start_date")

def current_unavailable_periods_for_reviewers(team):
    """Return dict with currently active unavailable periods for reviewers."""
    today = datetime.date.today()

    unavailable_period_qs = UnavailablePeriod.objects.filter(
        Q(end_date__gte=today) | Q(end_date=None),
        start_date__lte=today,
        team=team,
    ).order_by("end_date")

    res = defaultdict(list)
    for period in unavailable_period_qs:
        res[period.person_id].append(period)

    return res

def reviewer_rotation_list(team):
    """Returns person id -> index in rotation (next reviewer has index 0)."""
    reviewers = list(Person.objects.filter(role__name="reviewer", role__group=team))
    reviewers.sort(key=lambda p: p.last_name())

    next_reviewer_index = 0

    # now to figure out where the rotation is currently at
    saved_reviewer = NextReviewerInTeam.objects.filter(team=team).select_related("next_reviewer").first()
    if saved_reviewer:
        n = saved_reviewer.next_reviewer

        if n not in reviewers:
            # saved reviewer might not still be here, if not just
            # insert and use that position (Python will wrap around,
            # so no harm done by using the index on the original list
            # afterwards)
            reviewers_with_next = reviewers[:] + [n]
            reviewers_with_next.sort(key=lambda p: p.last_name())
            next_reviewer_index = reviewers_with_next.index(n)
        else:
            next_reviewer_index = reviewers.index(n)

    return reviewers[next_reviewer_index:] + reviewers[:next_reviewer_index]

def days_needed_to_fulfill_min_interval_for_reviewers(team):
    """Returns person_id -> days needed until min_interval is fulfilled for
    reviewer."""
    latest_assignments = dict(ReviewRequest.objects.filter(
        team=team,
    ).values_list("reviewer__person").annotate(Max("time")))

    min_intervals = dict(ReviewerSettings.objects.filter(team=team).values_list("person_id", "min_interval"))

    default_min_interval = ReviewerSettings(team=team).min_interval

    now = datetime.datetime.now()

    res = {}
    for person_id, latest_assignment_time in latest_assignments.iteritems():
        if latest_assignment_time is not None:
            min_interval = min_intervals.get(person_id, default_min_interval)

            days_needed = max(0, min_interval - (now - latest_assignment_time).days)

            if days_needed > 0:
                res[person_id] = days_needed

    return res

def make_new_review_request_from_existing(review_req):
    obj = ReviewRequest()
    obj.time = review_req.time
    obj.type = review_req.type
    obj.doc = review_req.doc
    obj.team = review_req.team
    obj.deadline = review_req.deadline
    obj.requested_rev = review_req.requested_rev
    obj.requested_by = review_req.requested_by
    obj.state = ReviewRequestStateName.objects.get(slug="requested")
    return obj

def email_review_request_change(request, review_req, subject, msg, by, notify_secretary, notify_reviewer, notify_requested_by):
    """Notify stakeholders about change, skipping a party if the change
    was done by that party."""

    system_email = Person.objects.get(name="(System)").formatted_email()

    to = []

    def extract_email_addresses(objs):
        if any(o.person == by for o in objs if o):
            l = []
        else:
            l = []
            for o in objs:
                if o:
                    e = o.formatted_email()
                    if e != system_email:
                        l.append(e)

        for e in l:
            if e not in to:
                to.append(e)

    if notify_secretary:
        extract_email_addresses(Role.objects.filter(name="secr", group=review_req.team).distinct())
    if notify_reviewer:
        extract_email_addresses([review_req.reviewer])
    if notify_requested_by:
        extract_email_addresses([review_req.requested_by.email()])
        
    if not to:
        return

    url = urlreverse("ietf.doc.views_review.review_request", kwargs={ "name": review_req.doc.name, "request_id": review_req.pk })
    url = request.build_absolute_uri(url)
    send_mail(request, to, None, subject, "review/review_request_changed.txt", {
        "review_req_url": url,
        "review_req": review_req,
        "msg": msg,
    })

def email_reviewer_availability_change(request, team, reviewer_role, msg, by):
    """Notify possibly both secretary and reviewer about change, skipping
    a party if the change was done by that party."""

    system_email = Person.objects.get(name="(System)").formatted_email()

    to = []

    def extract_email_addresses(objs):
        if any(o.person == by for o in objs if o):
            l = []
        else:
            l = []
            for o in objs:
                if o:
                    e = o.formatted_email()
                    if e != system_email:
                        l.append(e)

        for e in l:
            if e not in to:
                to.append(e)

    extract_email_addresses(Role.objects.filter(name="secr", group=team).distinct())

    extract_email_addresses([reviewer_role])

    if not to:
        return

    subject = "Reviewer availability of {} changed in {}".format(reviewer_role.person, team.acronym)

    url = urlreverse("ietf.group.views_review.reviewer_overview", kwargs={ "group_type": team.type_id, "acronym": team.acronym })
    url = request.build_absolute_uri(url)
    send_mail(request, to, None, subject, "review/reviewer_availability_changed.txt", {
        "reviewer_overview_url": url,
        "reviewer": reviewer_role.person,
        "team": team,
        "msg": msg,
        "by": by,
    })

def assign_review_request_to_reviewer(request, review_req, reviewer):
    assert review_req.state_id in ("requested", "accepted")

    if reviewer == review_req.reviewer:
        return

    if review_req.reviewer:
        email_review_request_change(
            request, review_req,
            "Unassigned from review of %s" % review_req.doc.name,
            "%s has cancelled your assignment to the review." % request.user.person,
            by=request.user.person, notify_secretary=False, notify_reviewer=True, notify_requested_by=False)

    review_req.state = ReviewRequestStateName.objects.get(slug="requested")
    review_req.reviewer = reviewer
    review_req.save()

    possibly_advance_next_reviewer_for_team(review_req.team, review_req.reviewer.person_id)

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

    email_review_request_change(
        request, review_req,
        "Assigned to review %s" % review_req.doc.name,
        "%s has assigned you to review the document." % request.user.person,
        by=request.user.person, notify_secretary=False, notify_reviewer=True, notify_requested_by=False)

def possibly_advance_next_reviewer_for_team(team, assigned_review_to_person_id):
    # prune reviewers not in the rotation (but not the assigned
    # reviewer who must have been available for assignment anyway)
    reviewers_to_skip = set()

    unavailable_periods = current_unavailable_periods_for_reviewers(team)
    for person_id, periods in unavailable_periods.iteritems():
        if periods and person_id != assigned_review_to_person_id:
            reviewers_to_skip.add(person_id)

    days_needed_for_reviewers = days_needed_to_fulfill_min_interval_for_reviewers(team)
    for person_id, days_needed in days_needed_for_reviewers.iteritems():
        if days_needed > 0 and person_id != assigned_review_to_person_id:
            reviewers_to_skip.add(person_id)

    rotation_list = [p.pk for p in reviewer_rotation_list(team) if p.pk not in reviewers_to_skip]

    if not rotation_list:
        return

    def reviewer_at_index(i):
        return rotation_list[i % len(rotation_list)]

    def reviewer_settings_for(person_id):
        return (ReviewerSettings.objects.filter(team=team, person=person_id).first()
                or ReviewerSettings(team=team, person_id=person_id))

    current_i = 0

    if reviewer_at_index(current_i) == assigned_review_to_person_id:
        # move 1 ahead
        current_i += 1
    else:
        settings = reviewer_settings_for(assigned_review_to_person_id)
        settings.skip_next += 1
        settings.save()

    while True:
        # as a clean-up step go through any with a skip next > 0
        current_reviewer_person_id = reviewer_at_index(current_i)
        settings = reviewer_settings_for(current_reviewer_person_id)
        if settings.skip_next > 0:
            settings.skip_next -= 1
            settings.save()

            current_i += 1
        else:
            nr = NextReviewerInTeam.objects.filter(team=team).first() or NextReviewerInTeam(team=team)
            nr.next_reviewer_id = current_reviewer_person_id
            nr.save()

            break

def close_review_request(request, review_req, close_state):
    suggested_req = review_req.pk is None

    prev_state = review_req.state
    review_req.state = close_state
    if close_state.slug == "no-review-version":
        review_req.reviewed_rev = review_req.requested_rev or review_req.doc.rev # save rev for later reference
    review_req.save()

    if not suggested_req:
        DocEvent.objects.create(
            type="changed_review_request",
            doc=review_req.doc,
            by=request.user.person,
            desc="Closed request for {} review by {} with state '{}'".format(
                review_req.type.name, review_req.team.acronym.upper(), close_state.name),
        )

        if prev_state.slug != "requested":
            email_review_request_change(
                request, review_req,
                "Closed review request for {}: {}".format(review_req.doc.name, close_state.name),
                "Review request has been closed by {}.".format(request.user.person),
                by=request.user.person, notify_secretary=False, notify_reviewer=True, notify_requested_by=True)

def suggested_review_requests_for_team(team):
    system_person = Person.objects.get(name="(System)")

    seen_deadlines = {}

    requests = {}

    requested_state = ReviewRequestStateName.objects.get(slug="requested", used=True)

    if True: # FIXME
        # in Last Call
        last_call_type = ReviewTypeName.objects.get(slug="lc")
        last_call_docs = Document.objects.filter(states=State.objects.get(type="draft-iesg", slug="lc", used=True))
        last_call_expires = { e.doc_id: e.expires for e in LastCallDocEvent.objects.order_by("time", "id") }
        for doc in last_call_docs:
            deadline = last_call_expires[doc.pk].date() if doc.pk in last_call_expires else datetime.date.today()

            if deadline > seen_deadlines.get(doc.pk, datetime.date.max):
                continue

            requests[doc.pk] = ReviewRequest(
                type=last_call_type,
                doc=doc,
                team=team,
                deadline=deadline,
                requested_by=system_person,
                state=requested_state,
            )

            seen_deadlines[doc.pk] = deadline


    if True: # FIXME
        # on Telechat Agenda
        telechat_dates = list(TelechatDate.objects.active().order_by('date').values_list("date", flat=True)[:4])

        telechat_type = ReviewTypeName.objects.get(slug="telechat")
        telechat_deadline_delta = datetime.timedelta(days=2)
        telechat_docs = Document.objects.filter(docevent__telechatdocevent__telechat_date__in=telechat_dates)
        for doc in telechat_docs:
            d = doc.telechat_date()
            if d not in telechat_dates:
                continue

            deadline = d - telechat_deadline_delta

            if deadline > seen_deadlines.get(doc.pk, datetime.date.max):
                continue

            requests[doc.pk] = ReviewRequest(
                type=telechat_type,
                doc=doc,
                team=team,
                deadline=deadline,
                requested_by=system_person,
                state=requested_state,
            )

            seen_deadlines[doc.pk] = deadline

    # filter those with existing requests
    existing_requests = defaultdict(list)
    for r in ReviewRequest.objects.filter(doc__in=requests.iterkeys()):
        existing_requests[r.doc_id].append(r)

    def blocks(existing, request):
        if existing.doc_id != request.doc_id:
            return False

        no_review_document = existing.state_id == "no-review-document"
        pending = (existing.state_id in ("requested", "accepted")
                   and (not existing.requested_rev or existing.requested_rev == request.doc.rev))
        completed_or_closed = (existing.state_id not in ("part-completed", "rejected", "overtaken", "no-response")
                               and existing.reviewed_rev == request.doc.rev)

        return no_review_document or pending or completed_or_closed

    res = [r for r in requests.itervalues()
           if not any(blocks(e, r) for e in existing_requests[r.doc_id])]
    res.sort(key=lambda r: (r.deadline, r.doc_id), reverse=True)
    return res

def extract_revision_ordered_review_requests_for_documents(review_request_queryset, names):
    """Extracts all review requests for document names (including replaced ancestors)."""

    names = set(names)

    replaces = extract_complete_replaces_ancestor_mapping_for_docs(names)

    requests_for_each_doc = defaultdict(list)
    for r in review_request_queryset.filter(doc__in=set(e for l in replaces.itervalues() for e in l) | names).order_by("-reviewed_rev", "-time", "-id").iterator():
        requests_for_each_doc[r.doc_id].append(r)

    # now collect in breadth-first order to keep the revision order intact
    res = defaultdict(list)
    for name in names:
        front = replaces.get(name, [])
        res[name].extend(requests_for_each_doc.get(name, []))

        seen = set()

        while front:
            replaces_reqs = []
            next_front = []
            for replaces_name in front:
                if replaces_name in seen:
                    continue

                seen.add(replaces_name)

                reqs = requests_for_each_doc.get(replaces_name, [])
                if reqs:
                    replaces_reqs.append(reqs)

                next_front.extend(replaces.get(replaces_name, []))

            # in case there are multiple replaces, move the ones with
            # the latest reviews up front
            replaces_reqs.sort(key=lambda l: l[0].time, reverse=True)

            for reqs in replaces_reqs:
                res[name].extend(reqs)

            # move one level down
            front = next_front

    return res

def setup_reviewer_field(field, review_req):
    field.queryset = field.queryset.filter(role__name="reviewer", role__group=review_req.team)
    if review_req.reviewer:
        field.initial = review_req.reviewer_id

    choices = make_assignment_choices(field.queryset, review_req)
    if not field.required:
        choices = [("", field.empty_label)] + choices

    field.choices = choices

def make_assignment_choices(email_queryset, review_req):
    doc = review_req.doc
    team = review_req.team

    possible_emails = list(email_queryset)
    possible_person_ids = [e.person_id for e in possible_emails]

    aliases = DocAlias.objects.filter(document=doc).values_list("name", flat=True)

    # settings
    reviewer_settings = {
        r.person_id: r
        for r in ReviewerSettings.objects.filter(team=team, person__in=possible_person_ids)
    }

    for p in possible_person_ids:
        if p not in reviewer_settings:
            reviewer_settings[p] = ReviewerSettings()

    # frequency
    days_needed_for_reviewers = days_needed_to_fulfill_min_interval_for_reviewers(team)

    # rotation
    rotation_index = { p.pk: i for i, p in enumerate(reviewer_rotation_list(team)) }

    # previous review of document
    has_reviewed_previous = ReviewRequest.objects.filter(
        doc=doc,
        reviewer__in=possible_emails,
        state="completed",
    )

    if review_req.pk is not None:
        has_reviewed_previous = has_reviewed_previous.exclude(pk=review_req.pk)

    has_reviewed_previous = set(has_reviewed_previous.values_list("reviewer", flat=True))

    # review wishes
    wish_to_review = set(ReviewWish.objects.filter(team=team, person__in=possible_person_ids, doc=doc).values_list("person", flat=True))

    # connections
    connections = {}
    # examine the closest connections last to let them override
    for e in Email.objects.filter(pk__in=possible_emails, person=doc.ad_id):
        connections[e] = "is associated Area Director"
    for r in Role.objects.filter(group=doc.group_id, email__in=possible_emails).select_related("name"):
        connections[r.email_id] = "is group {}".format(r.name)
    if doc.shepherd_id:
        connections[doc.shepherd_id] = "is shepherd of document"
    for e in DocumentAuthor.objects.filter(document=doc, author__in=possible_emails).values_list("author", flat=True):
        connections[e] = "is author of document"

    # unavailable periods
    unavailable_periods = current_unavailable_periods_for_reviewers(team)

    ranking = []
    for e in possible_emails:
        settings = reviewer_settings.get(e.person_id)

        # we sort the reviewers by separate axes, listing the most
        # important things first
        scores = []
        explanations = []

        def add_boolean_score(direction, expr, explanation=None):
            scores.append(direction if expr else -direction)
            if expr and explanation:
                explanations.append(explanation)

        # unavailable for review periods
        periods = unavailable_periods.get(e.person_id, [])
        unavailable_at_the_moment = periods and not (e.pk in has_reviewed_previous and all(p.availability == "canfinish" for p in periods))
        add_boolean_score(-1, unavailable_at_the_moment)

        def format_period(p):
            if p.end_date:
                res = "unavailable until {}".format(p.end_date.isoformat())
            else:
                res = "unavailable indefinitely"
            return "{} ({})".format(res, p.get_availability_display())

        if periods:
            explanations.append(", ".join(format_period(p) for p in periods))

        # minimum interval between reviews
        days_needed = days_needed_for_reviewers.get(e.person_id, 0)
        scores.append(-days_needed)
        if days_needed > 0:
            explanations.append("max frequency exceeded, ready in {} {}".format(days_needed, "day" if days_needed == 1 else "days"))

        # misc
        add_boolean_score(+1, e.pk in has_reviewed_previous, "reviewed document before")
        add_boolean_score(+1, e.person_id in wish_to_review, "wishes to review document")
        add_boolean_score(-1, e.pk in connections, connections.get(e.pk)) # reviewer is somehow connected: bad
        add_boolean_score(-1, settings.filter_re and any(re.search(settings.filter_re, n) for n in aliases), "filter regexp matches")

        # skip next
        scores.append(-settings.skip_next)
        if settings.skip_next > 0:
            explanations.append("skip next {}".format(settings.skip_next))

        index = rotation_index.get(e.person_id, 0)
        scores.append(-index)
        explanations.append("#{}".format(index + 1))

        label = unicode(e.person)
        if explanations:
            label = u"{}: {}".format(label, u"; ".join(explanations))

        ranking.append({
            "email": e,
            "scores": scores,
            "label": label,
        })

    ranking.sort(key=lambda r: r["scores"], reverse=True)

    return [(r["email"].pk, r["label"]) for r in ranking]
