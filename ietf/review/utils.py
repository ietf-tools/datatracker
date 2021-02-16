# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import itertools

from collections import defaultdict, namedtuple

from django.db.models import Q, Max, F
from django.template.defaultfilters import pluralize
from django.template.loader import render_to_string
from django.urls import reverse as urlreverse
from django.contrib.sites.models import Site
from simple_history.utils import update_change_reason

import debug                            # pyflakes:ignore
from ietf.dbtemplate.models import DBTemplate

from ietf.group.models import Group, Role
from ietf.doc.models import (Document, ReviewRequestDocEvent, ReviewAssignmentDocEvent, State,
                             LastCallDocEvent, TelechatDocEvent)
from ietf.iesg.models import TelechatDate
from ietf.mailtrigger.utils import gather_address_lists
from ietf.person.models import Person
from ietf.ietfauth.utils import has_role, is_authorized_in_doc_stream
from ietf.review.models import (ReviewRequest, ReviewAssignment, ReviewRequestStateName, ReviewTypeName, 
                                ReviewerSettings, UnavailablePeriod, ReviewSecretarySettings,
                                ReviewTeamSettings)
from ietf.utils.mail import send_mail
from ietf.doc.utils import extract_complete_replaces_ancestor_mapping_for_docs
from ietf.utils import log

# The origin date is used to have a single reference date for "every X days".
# This date is arbitrarily chosen and has no special meaning, but should be consistent.
ORIGIN_DATE_PERIODIC_REMINDERS = datetime.date(2019, 1, 1)


def active_review_teams():
    return Group.objects.filter(reviewteamsettings__isnull=False,state="active")

def close_review_request_states():
    return ReviewRequestStateName.objects.filter(used=True).exclude(slug__in=["requested", "assigned"])

def can_request_review_of_doc(user, doc):
    if not user.is_authenticated:
        return False

    if doc.type_id == 'draft' and doc.get_state_slug() != 'active':
        return False

    return (is_authorized_in_doc_stream(user, doc)
            or Role.objects.filter(person__user=user, name="secr", group__in=active_review_teams()).exists())

def can_manage_review_requests_for_team(user, team, allow_personnel_outside_team=True):
    if not user.is_authenticated:
        return False

    return (Role.objects.filter(name="secr", person__user=user, group=team).exists()
            or (allow_personnel_outside_team and has_role(user, "Secretariat")))

def can_access_review_stats_for_team(user, team):
    if not user.is_authenticated:
        return False

    return (Role.objects.filter(name__in=("secr", "reviewer"), person__user=user, group=team).exists()
            or has_role(user, ["Secretariat", "Area Director"]))

def review_assignments_to_list_for_docs(docs):
    assignment_qs = ReviewAssignment.objects.filter(
        state__in=["assigned", "accepted", "part-completed", "completed"],
    ).prefetch_related("result")

    doc_names = [d.name for d in docs]

    return extract_revision_ordered_review_assignments_for_documents_and_replaced(assignment_qs, doc_names)

def augment_review_requests_with_events(review_reqs):
    req_dict = { r.pk: r for r in review_reqs }
    for e in ReviewRequestDocEvent.objects.filter(review_request__in=review_reqs, type__in=["assigned_review_request", "closed_review_request"]).order_by("time"):
        setattr(req_dict[e.review_request_id], e.type + "_event", e)

def no_review_from_teams_on_doc(doc, rev):
    return Group.objects.filter(
        reviewrequest__doc__name=doc.name,
        reviewrequest__requested_rev=rev,
        reviewrequest__state__slug="no-review-version",
    ).distinct()

def unavailable_periods_to_list(past_days=14):
    return UnavailablePeriod.objects.filter(
        Q(end_date=None) | Q(end_date__gte=datetime.date.today() - datetime.timedelta(days=past_days)),
    ).order_by("start_date")

def current_unavailable_periods_for_reviewers(team):
    """Return dict with currently active unavailable periods for reviewers."""
    today = datetime.date.today()

    unavailable_period_qs = UnavailablePeriod.objects.filter(
        Q(end_date__gte=today) | Q(end_date=None),
        Q(start_date__lte=today) | Q(start_date=None),
        team=team,
    ).order_by("end_date")

    res = defaultdict(list)
    for period in unavailable_period_qs:
        res[period.person_id].append(period)

    return res


def days_needed_to_fulfill_min_interval_for_reviewers(team):
    """Returns person_id -> days needed until min_interval is fulfilled
    for reviewer (in case it is necessary to wait, otherwise reviewer
    is absent in result)."""
    latest_assignments = dict(ReviewAssignment.objects.filter(
        review_request__team=team,
    ).values_list("reviewer__person").annotate(Max("assigned_on")))

    min_intervals = dict(ReviewerSettings.objects.filter(team=team).values_list("person_id", "min_interval"))

    now = datetime.datetime.now()

    res = {}
    for person_id, latest_assignment_time in latest_assignments.items():
        if latest_assignment_time is not None:
            min_interval = min_intervals.get(person_id)
            if min_interval is None:
                continue

            days_needed = max(0, min_interval - (now - latest_assignment_time).days)
            if days_needed > 0:
                res[person_id] = days_needed

    return res

ReviewAssignmentData = namedtuple("ReviewAssignmentData", [
    "assignment_pk", "request_pk", "doc_name", "doc_pages", "req_time", "state", "assigned_time", "deadline", "reviewed_rev", "result", "team", "reviewer",
    "late_days",
    "request_to_assignment_days", "assignment_to_closure_days", "request_to_closure_days"])


def extract_review_assignment_data(teams=None, reviewers=None, time_from=None, time_to=None, ordering=[]):
    """Yield data on each review assignment, sorted by (*ordering, assigned_on)
    for easy use with itertools.groupby. Valid entries in *ordering are "team" and "reviewer"."""

    filters = Q()

    if teams:
        filters &= Q(review_request__team__in=teams)

    if reviewers:
        filters &= Q(reviewer__person__in=reviewers)

    if time_from:
        filters &= Q(review_request__time__gte=time_from)

    if time_to:
        filters &= Q(review_request__time__lte=time_to)

    # This doesn't do the left-outer join on docevent that the previous code did. These variables could be renamed
    event_qs = ReviewAssignment.objects.filter(filters)

    event_qs = event_qs.values_list(
        "pk", "review_request__pk", "review_request__doc__name", "review_request__doc__pages", "review_request__time", "state", "review_request__deadline", "reviewed_rev", "result", "review_request__team",
        "reviewer__person", "assigned_on", "completed_on"
    )

    event_qs = event_qs.order_by(*[o.replace("reviewer", "reviewer__person").replace("team","review_request__team") for o in ordering] + ["review_request__time", "assigned_on", "pk", "completed_on"])

    def positive_days(time_from, time_to):
        if time_from is None or time_to is None:
            return None

        delta = time_to - time_from
        seconds = delta.total_seconds()
        if seconds > 0:
            return seconds / float(24 * 60 * 60)
        else:
            return 0.0

    requested_time = assigned_time = closed_time = None

    for assignment in event_qs:

        assignment_pk, request_pk, doc_name, doc_pages, req_time, state, deadline, reviewed_rev, result, team, reviewer, assigned_on, completed_on = assignment

        requested_time = req_time
        assigned_time = assigned_on
        closed_time = completed_on

        late_days = positive_days(datetime.datetime.combine(deadline, datetime.time.max), closed_time)
        request_to_assignment_days = positive_days(requested_time, assigned_time)
        assignment_to_closure_days = positive_days(assigned_time, closed_time)
        request_to_closure_days = positive_days(requested_time, closed_time)

        d = ReviewAssignmentData(assignment_pk, request_pk, doc_name, doc_pages, req_time, state, assigned_time, deadline, reviewed_rev, result, team, reviewer,
                              late_days, request_to_assignment_days, assignment_to_closure_days,
                              request_to_closure_days)

        yield d


def aggregate_raw_period_review_assignment_stats(review_assignment_data, count=None):
    """Take a sequence of review request data from
    extract_review_assignment_data and aggregate them."""

    state_dict = defaultdict(int)
    late_state_dict = defaultdict(int)
    result_dict = defaultdict(int)
    assignment_to_closure_days_list = []
    assignment_to_closure_days_count = 0

    for (assignment_pk, request_pk, doc, doc_pages, req_time, state, assigned_time, deadline, reviewed_rev, result, team, reviewer,
         late_days, request_to_assignment_days, assignment_to_closure_days, request_to_closure_days) in review_assignment_data:
        if count == "pages":
            c = doc_pages
        else:
            c = 1

        state_dict[state] += c

        if late_days is not None and late_days > 0:
            late_state_dict[state] += c

        if state in ("completed", "part-completed"):
            result_dict[result] += c
            if assignment_to_closure_days is not None:
                assignment_to_closure_days_list.append(assignment_to_closure_days)
                assignment_to_closure_days_count += c

    return state_dict, late_state_dict, result_dict, assignment_to_closure_days_list, assignment_to_closure_days_count

def sum_period_review_assignment_stats(raw_aggregation):
    """Compute statistics from aggregated review request data for one aggregation point."""
    state_dict, late_state_dict, result_dict, assignment_to_closure_days_list, assignment_to_closure_days_count = raw_aggregation

    res = {}
    res["state"] = state_dict
    res["result"] = result_dict

    res["open"] = sum(state_dict.get(s, 0) for s in ("assigned", "accepted"))
    res["completed"] = sum(state_dict.get(s, 0) for s in ("completed", "part-completed"))
    res["not_completed"] = sum(state_dict.get(s, 0) for s in state_dict if s in ("rejected", "withdrawn", "overtaken", "no-response"))

    res["open_late"] = sum(late_state_dict.get(s, 0) for s in ("assigned", "accepted"))
    res["open_in_time"] = res["open"] - res["open_late"]
    res["completed_late"] = sum(late_state_dict.get(s, 0) for s in ("completed", "part-completed"))
    res["completed_in_time"] = res["completed"] - res["completed_late"]

    res["average_assignment_to_closure_days"] = float(sum(assignment_to_closure_days_list)) / (assignment_to_closure_days_count or 1) if assignment_to_closure_days_list else None

    return res

def sum_raw_review_assignment_aggregations(raw_aggregations):
    """Collapse a sequence of aggregations into one aggregation."""
    state_dict = defaultdict(int)
    late_state_dict = defaultdict(int)
    result_dict = defaultdict(int)
    assignment_to_closure_days_list = []
    assignment_to_closure_days_count = 0

    for raw_aggr in raw_aggregations:
        i_state_dict, i_late_state_dict, i_result_dict, i_assignment_to_closure_days_list, i_assignment_to_closure_days_count = raw_aggr
        for s, v in i_state_dict.items():
            state_dict[s] += v
        for s, v in i_late_state_dict.items():
            late_state_dict[s] += v
        for r, v in i_result_dict.items():
            result_dict[r] += v

        assignment_to_closure_days_list.extend(i_assignment_to_closure_days_list)
        assignment_to_closure_days_count += i_assignment_to_closure_days_count

    return state_dict, late_state_dict, result_dict, assignment_to_closure_days_list, assignment_to_closure_days_count

def latest_review_assignments_for_reviewers(team, days_back=365):
    """Collect and return stats for reviewers on latest assignments, in
    extract_review_assignment_data format."""

    extracted_data = extract_review_assignment_data(
        teams=[team],
        time_from=datetime.date.today() - datetime.timedelta(days=days_back),
        ordering=["reviewer"],
    )

    assignment_data_for_reviewers = {
        reviewer: list(reversed(list(req_data_items)))
        for reviewer, req_data_items in itertools.groupby(extracted_data, key=lambda data: data.reviewer)
    }

    return assignment_data_for_reviewers

def email_review_assignment_change(request, review_assignment, subject, msg, by, notify_secretary, notify_reviewer, notify_requested_by):
    to, cc = gather_address_lists(
        'review_assignment_changed',
        skipped_recipients=[Person.objects.get(name="(System)").formatted_email(), by.email_address()],
        doc=review_assignment.review_request.doc,
        group=review_assignment.review_request.team,
        review_assignment=review_assignment,
        skip_review_secretary=not notify_secretary,
        skip_review_reviewer=not notify_reviewer,
        skip_review_requested_by=not notify_requested_by,
    )

    if to or cc:
        url = urlreverse("ietf.doc.views_review.review_request_forced_login", kwargs={ "name": review_assignment.review_request.doc.name, "request_id": review_assignment.review_request.pk })
        url = request.build_absolute_uri(url)
        send_mail(request, to, request.user.person.formatted_email(), subject, "review/review_request_changed.txt", {
            "review_req_url": url,
            "review_req": review_assignment.review_request,
            "msg": msg,
        }, cc=cc)
 

def email_review_request_change(request, review_req, subject, msg, by, notify_secretary, notify_reviewer, notify_requested_by):
    """Notify stakeholders about change, skipping a party if the change
    was done by that party."""    
    (to, cc) = gather_address_lists(
        'review_req_changed',
        skipped_recipients=[Person.objects.get(name="(System)").formatted_email(), by.email_address()],
        doc=review_req.doc,
        group=review_req.team,
        review_request=review_req,
        skip_review_secretary=not notify_secretary,
        skip_review_reviewer=not notify_reviewer,
        skip_review_requested_by=not notify_requested_by,
    )
    
    if cc and not to:
        to = cc
        cc = []
    if to or cc:
        url = urlreverse("ietf.doc.views_review.review_request_forced_login", kwargs={ "name": review_req.doc.name, "request_id": review_req.pk })
        url = request.build_absolute_uri(url)
        send_mail(request, to, request.user.person.formatted_email(), subject, "review/review_request_changed.txt", {
                    "review_req_url": url,
                    "review_req": review_req,
                    "msg": msg,
                },
                cc=cc,
            )

def email_reviewer_availability_change(request, team, reviewer_role, msg, by):
    """Notify possibly both secretary and reviewer about change, skipping
    a party if the change was done by that party."""
    (to, cc) = gather_address_lists(
        'review_availability_changed',
        skipped_recipients=[Person.objects.get(name="(System)").formatted_email(), by.email_address()],
        group=team,
        reviewer=reviewer_role,
    )

    if to or cc:
        subject = "Reviewer availability of {} changed in {}".format(reviewer_role.person, team.acronym)
    
        url = urlreverse("ietf.group.views.reviewer_overview", kwargs={ "group_type": team.type_id, "acronym": team.acronym })
        url = request.build_absolute_uri(url)
        send_mail(request, to, None, subject, "review/reviewer_availability_changed.txt", {
            "reviewer_overview_url": url,
            "reviewer": reviewer_role.person,
            "team": team,
            "msg": msg,
            "by": by,
        }, cc=cc)


def assign_review_request_to_reviewer(request, review_req, reviewer, add_skip=False):
    assert review_req.state_id in ("requested", "assigned")
    # In the original implementation, review unassignments could be made on formsets by setting reviewers to None.
    # After refactoring to explicitly model ReviewAssignments, this no longer makes sense. Unassignment is now done
    # with a different view on a ReviewAssignment.
    log.assertion('reviewer is not None')

    if review_req.reviewassignment_set.filter(reviewer=reviewer).exists():
        return

    # Note that assigning a review no longer unassigns other reviews

    if review_req.state_id != 'assigned':
        review_req.state_id = 'assigned'
        review_req.save()
        
    from ietf.review.policies import get_reviewer_queue_policy
    assignment = get_reviewer_queue_policy(review_req.team).assign_reviewer(review_req, reviewer, add_skip)
    descr = "Request for {} review by {} is assigned to {}".format(
            review_req.type.name,
            review_req.team.acronym.upper(),
            reviewer.person if reviewer else "(None)")
    update_change_reason(assignment, descr)
    ReviewRequestDocEvent.objects.create(
        type="assigned_review_request",
        doc=review_req.doc,
        rev=review_req.doc.rev,
        by=request.user.person,
        desc=descr,
        review_request=review_req,
        state_id='assigned',
    )

    ReviewAssignmentDocEvent.objects.create(
        type="assigned_review_request",
        doc=review_req.doc,
        rev=review_req.doc.rev,
        by=request.user.person,
        desc="Request for {} review by {} is assigned to {}".format(
            review_req.type.name,
            review_req.team.acronym.upper(),
            reviewer.person,
        ),
        review_assignment=assignment,
        state_id='assigned',
    )

    prev_team_reviews = ReviewAssignment.objects.filter(
        review_request__doc=review_req.doc,
        state="completed",
        review_request__team=review_req.team,
    )

    try:
        template = DBTemplate.objects.get(
            path="/group/%s/email/review_assigned.txt" % review_req.team.acronym)
    except DBTemplate.DoesNotExist:
        template = DBTemplate.objects.get(path="/group/defaults/email/review_assigned.txt")

    context = {'assigner': request.user.person, 'reviewer': reviewer, 'prev_team_reviews': prev_team_reviews}
    msg = render_to_string(template.path, context, request=request)

    email_review_request_change(
        request, review_req,
        "%s %s assignment: %s" % (review_req.team.acronym.capitalize(), review_req.type.name,review_req.doc.name),
        msg ,
        by=request.user.person, notify_secretary=False, notify_reviewer=True, notify_requested_by=False)


def close_review_request(request, review_req, close_state, close_comment=''):
    suggested_req = review_req.pk is None

    review_req.state = close_state
# This field no longer exists, and it's not clear what the later reference was...
#    if close_state.slug == "no-review-version":
#        review_req.reviewed_rev = review_req.requested_rev or review_req.doc.rev # save rev for later reference
    review_req.save()

    if not suggested_req:
        descr = "Closed request for {} review by {} with state '{}'".format(
            review_req.type.name, review_req.team.acronym.upper(), close_state.name)
        if close_comment:
            descr += ': ' + close_comment
        update_change_reason(review_req, descr)
        ReviewRequestDocEvent.objects.create(
            type="closed_review_request",
            doc=review_req.doc,
            rev=review_req.doc.rev,
            by=request.user.person,
            desc=descr,
            review_request=review_req,
            state=review_req.state,
        )

        for assignment in review_req.reviewassignment_set.filter(state_id__in=['assigned','accepted']):
            assignment.state_id = 'withdrawn'
            assignment.save()
            ReviewAssignmentDocEvent.objects.create(
                type='closed_review_assignment',
                doc=review_req.doc,
                rev=review_req.doc.rev,
                by=request.user.person,
                desc="Request closed, assignment withdrawn: {} {} {} review".format(assignment.reviewer.person.plain_name(), assignment.review_request.type.name, assignment.review_request.team.acronym.upper()),
                review_assignment=assignment,
                state=assignment.state,
            )

        msg = "Review request has been closed by {}.".format(request.user.person)
        if close_comment:
            msg += "\nComment: {}".format(close_comment)
        email_review_request_change(
            request, review_req,
            "Closed review request for {}: {}".format(review_req.doc.name, close_state.name),
            msg=msg, by=request.user.person, notify_secretary=True,
            notify_reviewer=True, notify_requested_by=True)

def suggested_review_requests_for_team(team):

    if not team.reviewteamsettings.autosuggest:
        return []

    system_person = Person.objects.get(name="(System)")

    seen_deadlines = {}

    requests = {}

    now = datetime.datetime.now()

    reviewable_docs_qs = Document.objects.filter(type="draft").exclude(stream="ise")

    requested_state = ReviewRequestStateName.objects.get(slug="requested", used=True)

    last_call_type = ReviewTypeName.objects.get(slug="lc")
    if last_call_type in team.reviewteamsettings.review_types.all():
        # in Last Call
        last_call_docs = reviewable_docs_qs.filter(
            states=State.objects.get(type="draft-iesg", slug="lc", used=True)
        )
        last_call_expiry_events = { e.doc_id: e for e in LastCallDocEvent.objects.order_by("time", "id") }
        for doc in last_call_docs:
            e = last_call_expiry_events[doc.pk] if doc.pk in last_call_expiry_events else LastCallDocEvent(expires=now, time=now)

            deadline = e.expires.date()

            if deadline > seen_deadlines.get(doc.pk, datetime.date.max) or deadline < now.date():
                continue

            requests[doc.pk] = ReviewRequest(
                time=e.time,
                type=last_call_type,
                doc=doc,
                team=team,
                deadline=deadline,
                requested_by=system_person,
                state=requested_state,
            )
            seen_deadlines[doc.pk] = deadline


    telechat_type = ReviewTypeName.objects.get(slug="telechat")
    if telechat_type in team.reviewteamsettings.review_types.all():
        # on Telechat Agenda
        telechat_dates = list(TelechatDate.objects.active().order_by('date').values_list("date", flat=True)[:4])

        telechat_deadline_delta = datetime.timedelta(days=2)

        telechat_docs = reviewable_docs_qs.filter(
            docevent__telechatdocevent__telechat_date__in=telechat_dates
        )

        # we need to check the latest telechat event for each document
        # scheduled for the telechat, as the appearance might have been
        # cancelled/moved
        telechat_events = TelechatDocEvent.objects.filter(
            # turn into list so we don't get a complex and slow join sent down to the DB
            doc__id__in=list(telechat_docs.values_list("pk", flat=True)),
        ).values_list(
            "doc", "pk", "time", "telechat_date"
        ).order_by("doc", "-time", "-id").distinct()

        for doc_pk, events in itertools.groupby(telechat_events, lambda t: t[0]):
            _, _, event_time, event_telechat_date = list(events)[0]

            deadline = None
            if event_telechat_date in telechat_dates:
                deadline = event_telechat_date - telechat_deadline_delta

            if not deadline or deadline > seen_deadlines.get(doc_pk, datetime.date.max):
                continue
                
            if doc_pk in requests:
                # Document was already added in last call, i.e. it is both in last call and telechat
                requests[doc_pk].in_lc_and_telechat = True
            else:
                requests[doc_pk] = ReviewRequest(
                    time=event_time,
                    type=telechat_type,
                    doc_id=doc_pk,
                    team=team,
                    deadline=deadline,
                    requested_by=system_person,
                    state=requested_state,
                )

            seen_deadlines[doc_pk] = deadline

    # filter those with existing explicit requests 
    existing_requests = defaultdict(list)
    for r in ReviewRequest.objects.filter(doc__id__in=iter(requests.keys()), team=team):
        existing_requests[r.doc_id].append(r)

    def blocks(existing, request):
        if existing.doc_id != request.doc_id:
            return False

        no_review_document = existing.state_id == "no-review-document"
        no_review_rev = ( existing.state_id == "no-review-version") and (not existing.requested_rev or existing.requested_rev == request.doc.rev)
        pending = (existing.state_id == "assigned" 
                   and existing.reviewassignment_set.filter(state_id__in=("assigned", "accepted")).exists()
                   and (not existing.requested_rev or existing.requested_rev == request.doc.rev))
        request_closed = existing.state_id not in ('requested','assigned')
        # at least one assignment was completed for the requested version or the current doc version if no specific version was requested:
        some_assignment_completed = existing.reviewassignment_set.filter(reviewed_rev=existing.requested_rev or existing.doc.rev, state_id='completed').exists()

        return any([no_review_document, no_review_rev, pending, request_closed, some_assignment_completed])

    res = [r for r in requests.values()
           if not any(blocks(e, r) for e in existing_requests[r.doc_id])]
    res.sort(key=lambda r: (r.deadline, r.doc_id), reverse=True)
    return res

def extract_revision_ordered_review_assignments_for_documents_and_replaced(review_assignment_queryset, names):
    """Extracts all review assignments for document names (including replaced ancestors), return them neatly sorted."""

    names = set(names)

    replaces = extract_complete_replaces_ancestor_mapping_for_docs(names)

    assignments_for_each_doc = defaultdict(list)
    replacement_name_set = set(e for l in replaces.values() for e in l) | names
    for r in ( review_assignment_queryset.filter(review_request__doc__name__in=replacement_name_set)
                                        .order_by("-reviewed_rev","-assigned_on", "-id").iterator()):
        assignments_for_each_doc[r.review_request.doc.name].append(r)

    # now collect in breadth-first order to keep the revision order intact
    res = defaultdict(list)
    for name in names:
        front = replaces.get(name, [])
        res[name].extend(assignments_for_each_doc.get(name, []))

        seen = set()

        while front:
            replaces_assignments = []
            next_front = []
            for replaces_name in front:
                if replaces_name in seen:
                    continue

                seen.add(replaces_name)

                assignments = assignments_for_each_doc.get(replaces_name, [])
                if assignments:
                    replaces_assignments.append(assignments)

                next_front.extend(replaces.get(replaces_name, []))

            # in case there are multiple replaces, move the ones with
            # the latest reviews up front
            replaces_assignments.sort(key=lambda l: l[0].assigned_on, reverse=True)

            for assignments in replaces_assignments:
                res[name].extend(assignments)

            # move one level down
            front = next_front

    return res

def extract_revision_ordered_review_requests_for_documents_and_replaced(review_request_queryset, names):
    """Extracts all review requests for document names (including replaced ancestors), return them neatly sorted."""

    names = set(names)

    replaces = extract_complete_replaces_ancestor_mapping_for_docs(names)

    requests_for_each_doc = defaultdict(list)
    for r in review_request_queryset.filter(doc__name__in=set(e for l in replaces.values() for e in l) | names).order_by("-time", "-id").iterator():
        requests_for_each_doc[r.doc.name].append(r)

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


def get_default_filter_re(person):
    if type(person) != Person:
        person = Person.objects.get(id=person)
    groups_to_avoid =  [ r.group for r in person.role_set.all() if r.name in r.group.features.groupman_roles and r.group.features.acts_like_wg ]
    if not groups_to_avoid:
        return '^draft-%s-.*$' % ( person.last_name().lower(), )
    else:
        return '^draft-(%s|%s)-.*$' % ( person.last_name().lower(), '|'.join(['ietf-%s' % g.acronym for g in groups_to_avoid]))


def send_unavaibility_period_ending_reminder(remind_date):
    reminder_days = 3
    end_date = remind_date + datetime.timedelta(days=reminder_days)
    min_start_date = end_date - datetime.timedelta(days=30)
    periods = UnavailablePeriod.objects.filter(start_date__lte=min_start_date, end_date=end_date)
    log = []
    for period in periods:
        (to, cc) = gather_address_lists('review_availability_changed', group=period.team, reviewer=period.person)
        domain = Site.objects.get_current().domain
        url = urlreverse("ietf.group.views.reviewer_overview", kwargs={ "group_type": period.team.type_id, "acronym": period.team.acronym })
        
        subject = "Reminder: unavailability period of {} is ending soon".format(period.person)
        send_mail(None, to, None, subject, "review/reviewer_unavailability_ending.txt", {
            "reviewer_overview_url": "https://{}{}".format(domain, url),
            "reviewer": period.person,
            "team": period.team,
            "reminder_days": reminder_days,
            "period_start": period.start_date.isoformat(),
            "period_end": period.end_date.isoformat(),
        }, cc=cc)
        log.append("Emailed reminder to {} for ending of unavailability "
                   "of {} in {} soon (unavailability period id {})".format(
            to, period.person, period.team.acronym,period.pk))
    return log


def send_review_reminder_overdue_assignment(remind_date):
    min_overdue_days = 5
    min_deadline = remind_date - datetime.timedelta(days=min_overdue_days)
    teams = Group.objects.exclude(reviewteamsettings=None)
    log = []
    for team in teams:
        assignments = ReviewAssignment.objects.filter(
            state__in=("assigned", "accepted"),
            review_request__deadline__lte=min_deadline,
            review_request__team=team,
        )
        if not assignments:
            continue
            
        (to, cc) = gather_address_lists('review_reminder_overdue_assignment', group=team)
        domain = Site.objects.get_current().domain
        subject = "{} Overdue review{} for team {}".format(
            len(assignments), pluralize(len(assignments)), team.acronym)
        
        send_mail(None, to, None, subject, "review/review_reminder_overdue_assignment.txt", {
            "domain": domain,
            "assignments": assignments,
            "team": team,
            "min_overdue_days": min_overdue_days,
        }, cc=cc)
        log.append("Emailed reminder to {} about {} overdue reviews in {}".format(
            to, assignments.count(), team.acronym,
        ))
    return log


def send_reminder_all_open_reviews(remind_date):
    log = []
    days_since_origin = (remind_date - ORIGIN_DATE_PERIODIC_REMINDERS).days
    relevant_reviewer_settings = ReviewerSettings.objects.filter(remind_days_open_reviews__isnull=False)
    
    for reviewer_settings in relevant_reviewer_settings:
        if days_since_origin % reviewer_settings.remind_days_open_reviews != 0:
            continue
            
        assignments = ReviewAssignment.objects.filter(
            state__in=("assigned", "accepted"),
            reviewer__person=reviewer_settings.person,
        )
        if not assignments:
            continue

        to = reviewer_settings.person.formatted_email()
        subject = "Reminder: you have {} open review assignment{}".format(len(assignments), pluralize(len(assignments)))

        domain = Site.objects.get_current().domain
        url = urlreverse("ietf.group.views.reviewer_overview",
                         kwargs={"group_type": reviewer_settings.team.type_id,
                                 "acronym": reviewer_settings.team.acronym})

        send_mail(None, to, None, subject, "review/reviewer_reminder_all_open_reviews.txt", {
            "reviewer_overview_url": "https://{}{}".format(domain, url),
            "assignments": assignments,
            "team": reviewer_settings.team,
            "remind_days": reviewer_settings.remind_days_open_reviews,
        })
        log.append("Emailed reminder to {} of their {} open reviews".format(to, len(assignments)))

    return log


def send_reminder_unconfirmed_assignments(remind_date):
    """
    Remind reviewers of any assigned ReviewAssignments which they have not
    accepted or rejected, if enabled in ReviewTeamSettings.
    """
    log = []
    days_since_origin = (remind_date - ORIGIN_DATE_PERIODIC_REMINDERS).days
    relevant_review_team_settings = ReviewTeamSettings.objects.filter(
        remind_days_unconfirmed_assignments__isnull=False)

    for review_team_settings in relevant_review_team_settings:
        if days_since_origin % review_team_settings.remind_days_unconfirmed_assignments != 0:
            continue

        assignments = ReviewAssignment.objects.filter(
            state='assigned',
            review_request__team=review_team_settings.group,
        )
        if not assignments:
            continue

        for assignment in assignments:
            to = assignment.reviewer.formatted_email()
            subject = "Reminder: you have not responded to a review assignment"
            domain = Site.objects.get_current().domain
            review_request_url = urlreverse("ietf.doc.views_review.review_request", kwargs={
                "name": assignment.review_request.doc.name,
                "request_id": assignment.review_request.pk
            })

            send_mail(None, to, None, subject, "review/reviewer_reminder_unconfirmed_assignments.txt", {
                "review_request_url": "https://{}{}".format(domain, review_request_url),
                "assignment": assignment,
                "team": assignment.review_request.team,
                "remind_days": review_team_settings.remind_days_unconfirmed_assignments,
            })
            log.append("Emailed reminder to {} about not accepted/rejected review assignment {}".format(to, assignment.pk))

    return log


def review_assignments_needing_reviewer_reminder(remind_date):
    assignment_qs = ReviewAssignment.objects.filter(
        state__in=("assigned", "accepted"),
        reviewer__person__reviewersettings__remind_days_before_deadline__isnull=False,
        reviewer__person__reviewersettings__team=F("review_request__team"),
    ).values_list("pk", "review_request__deadline", "reviewer__person__reviewersettings__remind_days_before_deadline").distinct()

    assignment_pks = []
    for a_pk, deadline, remind_days in assignment_qs:
        if (deadline - remind_date).days == remind_days:
            assignment_pks.append(a_pk)

    return ReviewAssignment.objects.filter(pk__in=assignment_pks).select_related("reviewer", "reviewer__person", "state", "review_request__team")

def email_reviewer_reminder(assignment):
    review_request = assignment.review_request
    team = review_request.team

    deadline_days = (review_request.deadline - datetime.date.today()).days

    subject = "Reminder: deadline for review of {} in {} is {}".format(review_request.doc.name, team.acronym, review_request.deadline.isoformat())

    import ietf.ietfauth.views
    overview_url = urlreverse(ietf.ietfauth.views.review_overview)
    import ietf.doc.views_review
    request_url = urlreverse(ietf.doc.views_review.review_request, kwargs={ "name": review_request.doc.name, "request_id": review_request.pk })

    domain = Site.objects.get_current().domain

    settings = ReviewerSettings.objects.filter(person=assignment.reviewer.person, team=team).first()
    remind_days = settings.remind_days_before_deadline if settings else 0

    send_mail(None, [assignment.reviewer.formatted_email()], None, subject, "review/reviewer_reminder.txt", {
        "reviewer_overview_url": "https://{}{}".format(domain, overview_url),
        "review_request_url": "https://{}{}".format(domain, request_url),
        "review_request": review_request,
        "deadline_days": deadline_days,
        "remind_days": remind_days,
    })

def review_assignments_needing_secretary_reminder(remind_date):
    assignment_qs = ReviewAssignment.objects.filter(
        state__in=("assigned", "accepted"),
        review_request__team__role__person__reviewsecretarysettings__remind_days_before_deadline__isnull=False,
        review_request__team__role__person__reviewsecretarysettings__team=F("review_request__team"),
    ).exclude(
        reviewer=None
    ).values_list("pk", "review_request__deadline", "review_request__team__role", "review_request__team__role__person__reviewsecretarysettings__remind_days_before_deadline").distinct()

    assignment_pks = {}
    for a_pk, deadline, secretary_role_pk, remind_days in assignment_qs:
        if (deadline - remind_date).days == remind_days:
            assignment_pks[a_pk] = secretary_role_pk

    review_assignments = { a.pk: a for a in ReviewAssignment.objects.filter(pk__in=list(assignment_pks.keys())).select_related("reviewer", "reviewer__person", "state", "review_request__team") }
    secretary_roles = { r.pk: r for r in Role.objects.filter(pk__in=list(assignment_pks.values())).select_related("email", "person") }

    return [ (review_assignments[a_pk], secretary_roles[secretary_role_pk]) for a_pk, secretary_role_pk in assignment_pks.items() ]

def email_secretary_reminder(assignment, secretary_role):
    review_request = assignment.review_request
    team = review_request.team

    deadline_days = (review_request.deadline - datetime.date.today()).days

    subject = "Reminder: deadline for review of {} in {} is {}".format(review_request.doc.name, team.acronym, review_request.deadline.isoformat())

    import ietf.group.views
    settings_url = urlreverse(ietf.group.views.change_review_secretary_settings, kwargs={ "acronym": team.acronym, "group_type": team.type_id })
    import ietf.doc.views_review
    request_url = urlreverse(ietf.doc.views_review.review_request, kwargs={ "name": review_request.doc.name, "request_id": review_request.pk })

    domain = Site.objects.get_current().domain

    settings = ReviewSecretarySettings.objects.filter(person=secretary_role.person_id, team=team).first()
    remind_days = settings.remind_days_before_deadline if settings else 0

    send_mail(None, [assignment.reviewer.formatted_email()], None, subject, "review/secretary_reminder.txt", {
        "review_request_url": "https://{}{}".format(domain, request_url),
        "settings_url": "https://{}{}".format(domain, settings_url),
        "review_request": review_request,
        "deadline_days": deadline_days,
        "remind_days": remind_days,
    })
