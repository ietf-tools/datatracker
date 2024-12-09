# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import calendar
import datetime
import itertools
import json
import dateutil.relativedelta
from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse as urlreverse


import debug                            # pyflakes:ignore

from ietf.review.utils import (extract_review_assignment_data,
                               aggregate_raw_period_review_assignment_stats,
                               ReviewAssignmentData,
                               sum_period_review_assignment_stats,
                               sum_raw_review_assignment_aggregations)
from ietf.group.models import Role, Group
from ietf.person.models import Person
from ietf.name.models import ReviewResultName, CountryName, ReviewAssignmentStateName
from ietf.ietfauth.utils import has_role
from ietf.utils.response import permission_denied
from ietf.utils.timezone import date_today, DEADLINE_TZINFO


def stats_index(request):
    return render(request, "stats/index.html")

def generate_query_string(query_dict, overrides):
    query_part = ""

    if query_dict or overrides:
        d = query_dict.copy()
        for k, v in overrides.items():
            if type(v) in (list, tuple):
                if not v:
                    if k in d:
                        del d[k]
                else:
                    d.setlist(k, v)
            else:
                if v is None or v == "":
                    if k in d:
                        del d[k]
                else:
                    d[k] = v

        if d:
            query_part = "?" + d.urlencode()

    return query_part

def get_choice(request, get_parameter, possible_choices, multiple=False):
    # the statistics are built with links to make navigation faster,
    # so we don't really have a form in most cases, so just use this
    # helper instead to select between the choices
    values = request.GET.getlist(get_parameter)
    found = [t[0] for t in possible_choices if t[0] in values]

    if multiple:
        return found
    else:
        if found:
            return found[0]
        else:
            return None

def add_url_to_choices(choices, url_builder):
    return [ (slug, label, url_builder(slug)) for slug, label in choices]

def put_into_bin(value, bin_size):
    if value is None:
        return (0, '')

    v = (value // bin_size) * bin_size
    return (v, "{} - {}".format(v, v + bin_size - 1))

def prune_unknown_bin_with_known(bins):
    # remove from the unknown bin all authors within the
    # named/known bins
    all_known = { n for b, names in bins.items() if b for n in names }
    bins[""] = [name for name in bins[""] if name not in all_known]
    if not bins[""]:
        del bins[""]

def count_bins(bins):
    return len({ n for b, names in bins.items() if b for n in names })

def add_labeled_top_series_from_bins(chart_data, bins, limit):
    """Take bins on the form (x, label): [name1, name2, ...], figure out
    how many there are per label, take the overall top ones and put
    them into sorted series like [(x1, len(names1)), (x2, len(names2)), ...]."""
    aggregated_bins = defaultdict(set)
    xs = set()
    for (x, label), names in bins.items():
        xs.add(x)
        aggregated_bins[label].update(names)

    xs = list(sorted(xs))

    sorted_bins = sorted(aggregated_bins.items(), key=lambda t: len(t[1]), reverse=True)
    top = [ label for label, names in list(sorted_bins)[:limit]]

    for label in top:
        series_data = []

        for x in xs:
            names = bins.get((x, label), set())

            series_data.append((x, len(names)))

        chart_data.append({
            "data": series_data,
            "name": label
        })

def document_stats(request, stats_type=None):
    return HttpResponseRedirect(urlreverse("ietf.stats.views.stats_index"))


def known_countries_list(request, stats_type=None, acronym=None):
    countries = CountryName.objects.prefetch_related("countryalias_set")
    for c in countries:
        # the sorting is a bit of a hack - it puts the ISO code first
        # since it was added in a migration
        c.aliases = sorted(c.countryalias_set.all(), key=lambda a: a.pk)

    return render(request, "stats/known_countries_list.html", {
        "countries": countries,
    })

def meeting_stats(request, num=None, stats_type=None):
    return HttpResponseRedirect(urlreverse("ietf.stats.views.stats_index"))


@login_required
def review_stats(request, stats_type=None, acronym=None):
    # This view is a bit complex because we want to show a bunch of
    # tables with various filtering options, and both a team overview
    # and a reviewers-within-team overview - and a time series chart.
    # And in order to make the UI quick to navigate, we're not using
    # one big form but instead presenting a bunch of immediate
    # actions, with a URL scheme where the most common options (level
    # and statistics type) are incorporated directly into the URL to
    # be a bit nicer.

    def build_review_stats_url(stats_type_override=Ellipsis, acronym_override=Ellipsis, get_overrides=None):
        if get_overrides is None:
            get_overrides = {}
        kwargs = {
            "stats_type": stats_type if stats_type_override is Ellipsis else stats_type_override,
        }
        acr = acronym if acronym_override is Ellipsis else acronym_override
        if acr:
            kwargs["acronym"] = acr

        return urlreverse(review_stats, kwargs=kwargs) + generate_query_string(request.GET, get_overrides)

    # which overview - team or reviewer
    if acronym:
        level = "reviewer"
    else:
        level = "team"

    # statistics type - one of the tables or the chart
    possible_stats_types = [
        ("completion", "Completion status"),
        ("results", "Review results"),
        ("states", "Assignment states"),
    ]

    if level == "team":
        possible_stats_types.append(("time", "Changes over time"))

    possible_stats_types = add_url_to_choices(possible_stats_types,
                                              lambda slug: build_review_stats_url(stats_type_override=slug))

    if not stats_type:
        return HttpResponseRedirect(build_review_stats_url(stats_type_override=possible_stats_types[0][0]))

    # what to count
    possible_count_choices = add_url_to_choices([
        ("", "Review requests"),
        ("pages", "Reviewed pages"),
    ], lambda slug: build_review_stats_url(get_overrides={ "count": slug }))

    count = get_choice(request, "count", possible_count_choices) or ""

    # time range
    def parse_date(s):
        if not s:
            return None
        try:
            return datetime.datetime.strptime(s.strip(), "%Y-%m-%d").date()
        except ValueError:
            return None

    today = date_today(DEADLINE_TZINFO)
    from_date = parse_date(request.GET.get("from")) or today - dateutil.relativedelta.relativedelta(years=1)
    to_date = parse_date(request.GET.get("to")) or today

    from_time = datetime.datetime.combine(from_date, datetime.time.min, tzinfo=DEADLINE_TZINFO)
    to_time = datetime.datetime.combine(to_date, datetime.time.max, tzinfo=DEADLINE_TZINFO)

    # teams/reviewers
    teams = list(Group.objects.exclude(reviewrequest=None).distinct().order_by("name"))

    reviewer_filter_args = {}

    # - interlude: access control
    if has_role(request.user, ["Secretariat", "Area Director"]):
        pass
    else:
        secr_access = set()
        reviewer_only_access = set()

        for r in Role.objects.filter(person__user=request.user, name__in=["secr", "reviewer"], group__in=teams).distinct():
            if r.name_id == "secr":
                secr_access.add(r.group_id)
                reviewer_only_access.discard(r.group_id)
            elif r.name_id == "reviewer":
                if not r.group_id in secr_access:
                    reviewer_only_access.add(r.group_id)

        if not secr_access and not reviewer_only_access:
            permission_denied(request, "You do not have the necessary permissions to view this page")

        teams = [t for t in teams if t.pk in secr_access or t.pk in reviewer_only_access]

        for t in reviewer_only_access:
            reviewer_filter_args[t] = { "user": request.user }

    reviewers_for_team = None

    if level == "team":
        for t in teams:
            t.reviewer_stats_url = build_review_stats_url(acronym_override=t.acronym)

        query_teams = teams
        query_reviewers = None

        group_by_objs = { t.pk: t for t in query_teams }
        group_by_index = ReviewAssignmentData._fields.index("team")

    elif level == "reviewer":
        for t in teams:
            if t.acronym == acronym:
                reviewers_for_team = t
                break
        else:
            return HttpResponseRedirect(urlreverse(review_stats))

        query_reviewers = list(Person.objects.filter(
            email__reviewassignment__review_request__time__gte=from_time,
            email__reviewassignment__review_request__time__lte=to_time,
            email__reviewassignment__review_request__team=reviewers_for_team,
            **reviewer_filter_args.get(t.pk, {})
        ).distinct())
        query_reviewers.sort(key=lambda p: p.last_name())

        query_teams = [t]

        group_by_objs = { r.pk: r for r in query_reviewers }
        group_by_index = ReviewAssignmentData._fields.index("reviewer")

    # now filter and aggregate the data
    possible_teams = possible_completion_types = possible_results = possible_states = None
    selected_teams = selected_completion_type = selected_result = selected_state = None

    if stats_type == "time":
        possible_teams = [(t.acronym, t.acronym) for t in teams]
        selected_teams = get_choice(request, "team", possible_teams, multiple=True)

        def add_if_exists_else_subtract(element, l):
            if element in l:
                return [x for x in l if x != element]
            else:
                return l + [element]

        possible_teams = add_url_to_choices(
            possible_teams,
            lambda slug: build_review_stats_url(get_overrides={
                "team": add_if_exists_else_subtract(slug, selected_teams)
            })
        )
        query_teams = [t for t in query_teams if t.acronym in selected_teams]

        extracted_data = extract_review_assignment_data(query_teams, query_reviewers, from_time, to_time)

        req_time_index = ReviewAssignmentData._fields.index("req_time")

        def time_key_fn(t):
            d = t[req_time_index].date()
            #d -= datetime.timedelta(days=d.weekday()) # weekly
            # NOTE: Earlier releases had an off-by-one error here - some stat counts may move a month.
            d -= datetime.timedelta(days=d.day-1) # monthly 
            return d

        found_results = set()
        found_states = set()
        aggrs = []
        for d, request_data_items in itertools.groupby(extracted_data, key=time_key_fn):
            raw_aggr = aggregate_raw_period_review_assignment_stats(request_data_items, count=count)
            aggr = sum_period_review_assignment_stats(raw_aggr)

            aggrs.append((d, aggr))

            for slug in aggr["result"]:
                found_results.add(slug)
            for slug in aggr["state"]:
                found_states.add(slug)

        results = ReviewResultName.objects.filter(slug__in=found_results)
        states = ReviewAssignmentStateName.objects.filter(slug__in=found_states)

        # choice

        possible_completion_types = add_url_to_choices([
            ("completed_in_time_or_late", "Completed (in time or late)"),
            ("not_completed", "Not completed"),
            ("average_assignment_to_closure_days", "Avg. compl. days"),
        ], lambda slug: build_review_stats_url(get_overrides={ "completion": slug, "result": None, "state": None }))

        selected_completion_type = get_choice(request, "completion", possible_completion_types)

        possible_results = add_url_to_choices(
            [(r.slug, r.name) for r in results],
            lambda slug: build_review_stats_url(get_overrides={ "completion": None, "result": slug, "state": None })
        )

        selected_result = get_choice(request, "result", possible_results)
        
        possible_states = add_url_to_choices(
            [(s.slug, s.name) for s in states],
            lambda slug: build_review_stats_url(get_overrides={ "completion": None, "result": None, "state": slug })
        )

        selected_state = get_choice(request, "state", possible_states)

        if not selected_completion_type and not selected_result and not selected_state:
            selected_completion_type = "completed_in_time_or_late"

        standard_color = '#3d22b3'
        if selected_completion_type == 'completed_in_time_or_late':
            graph_data = [
                {'label': 'in time', 'color': standard_color, 'data': []},
                {'label': 'late', 'color': '#b42222', 'data': []}
            ]
        else:
            graph_data = [{'color': standard_color, 'data': []}]
        if selected_completion_type == "completed_combined":
                pass
        else:
            for d, aggr in aggrs:
                v1 = 0
                v2 = None
                js_timestamp = calendar.timegm(d.timetuple()) * 1000
                if selected_completion_type == 'completed_in_time_or_late':
                    v1 = aggr['completed_in_time']
                    v2 = aggr['completed_late']
                elif selected_completion_type is not None:
                    v1 = aggr[selected_completion_type]
                elif selected_result is not None:
                    v1 = aggr["result"][selected_result]
                elif selected_state is not None:
                    v1 = aggr["state"][selected_state]

                graph_data[0]['data'].append((js_timestamp, v1))
                if v2 is not None:
                    graph_data[1]['data'].append((js_timestamp, v2))
            data = json.dumps(graph_data)

    else: # tabular data
        extracted_data = extract_review_assignment_data(query_teams, query_reviewers, from_time, to_time, ordering=[level])

        data = []

        found_results = set()
        found_states = set()
        raw_aggrs = []
        for group_pk, request_data_items in itertools.groupby(extracted_data, key=lambda t: t[group_by_index]):
            raw_aggr = aggregate_raw_period_review_assignment_stats(request_data_items, count=count)
            raw_aggrs.append(raw_aggr)

            aggr = sum_period_review_assignment_stats(raw_aggr)

            # skip zero-valued rows
            if aggr["open"] == 0 and aggr["completed"] == 0 and aggr["not_completed"] == 0:
                continue

            aggr["obj"] = group_by_objs.get(group_pk)

            for slug in aggr["result"]:
                found_results.add(slug)
            for slug in aggr["state"]:
                found_states.add(slug)
            
            data.append(aggr)

        # add totals row
        if len(raw_aggrs) > 1:
            totals = sum_period_review_assignment_stats(sum_raw_review_assignment_aggregations(raw_aggrs))
            totals["obj"] = "Totals"
            data.append(totals)

        results = ReviewResultName.objects.filter(slug__in=found_results)
        states = ReviewAssignmentStateName.objects.filter(slug__in=found_states)

        # massage states/results breakdowns for template rendering
        for aggr in data:
            aggr["state_list"] = [aggr["state"].get(x.slug, 0) for x in states]
            aggr["result_list"] = [aggr["result"].get(x.slug, 0) for x in results]


    return render(request, 'stats/review_stats.html', {
        "team_level_url": build_review_stats_url(acronym_override=None),
        "level": level,
        "reviewers_for_team": reviewers_for_team,
        "teams": teams,
        "data": data,
        "states": states,
        "results": results,

        # options
        "possible_stats_types": possible_stats_types,
        "stats_type": stats_type,

        "possible_count_choices": possible_count_choices,
        "count": count,

        "from_date": from_date,
        "to_date": to_date,
        "today": today,

        # time options
        "possible_teams": possible_teams,
        "selected_teams": selected_teams,
        "possible_completion_types": possible_completion_types,
        "selected_completion_type": selected_completion_type,
        "possible_results": possible_results,
        "selected_result": selected_result,
        "possible_states": possible_states,
        "selected_state": selected_state,
    })
