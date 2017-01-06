import datetime, itertools, json, calendar
from collections import defaultdict

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse as urlreverse
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.db.models import Count
from django.utils.safestring import mark_safe

import dateutil.relativedelta

from ietf.review.utils import (extract_review_request_data,
                               aggregate_raw_review_request_stats,
                               ReviewRequestData,
                               compute_review_request_stats,
                               sum_raw_review_request_aggregations)
from ietf.group.models import Role, Group
from ietf.person.models import Person
from ietf.name.models import ReviewRequestStateName, ReviewResultName
from ietf.doc.models import Document
from ietf.ietfauth.utils import has_role

def stats_index(request):
    return render(request, "stats/index.html")

def generate_query_string(query_dict, overrides):
    query_part = u""

    if query_dict or overrides:
        d = query_dict.copy()
        for k, v in overrides.iteritems():
            if type(v) in (list, tuple):
                if not v:
                    if k in d:
                        del d[k]
                else:
                    d.setlist(k, v)
            else:
                if v is None or v == u"":
                    if k in d:
                        del d[k]
                else:
                    d[k] = v

        if d:
            query_part = u"?" + d.urlencode()

    return query_part


def document_stats(request, stats_type=None, document_state=None):
    def build_document_stats_url(stats_type_override=Ellipsis, document_state_override=Ellipsis, get_overrides={}):
        kwargs = {
            "stats_type": stats_type if stats_type_override is Ellipsis else stats_type_override,
            "document_state": document_state if document_state_override is Ellipsis else document_state_override,
        }

        return urlreverse(document_stats, kwargs={ k: v for k, v in kwargs.iteritems() if v is not None }) + generate_query_string(request.GET, get_overrides)

    # statistics type - one of the tables or the chart
    possible_stats_types = [
        ("authors", "Number of authors"),
#        ("pages", "Pages"),
#        ("format", "Format"),
#        ("spectech", "Specification techniques"),
    ]

    possible_stats_types = [ (slug, label, build_document_stats_url(stats_type_override=slug))
                             for slug, label in possible_stats_types ]

    if not stats_type:
        return HttpResponseRedirect(build_document_stats_url(stats_type_override=possible_stats_types[0][0]))

    possible_document_states = [
        ("all", "All"),
        ("rfc", "RFCs"),
        ("draft", "Drafts (not published as RFC)"),
    ]

    possible_document_states = [ (slug, label, build_document_stats_url(document_state_override=slug))
                                for slug, label in possible_document_states ]

    if not document_state:
        return HttpResponseRedirect(build_document_stats_url(document_state_override=possible_document_states[0][0]))
    

    # filter documents
    doc_qs = Document.objects.filter(type="draft")

    if document_state == "rfc":
        doc_qs = doc_qs.filter(states__type="draft", states__slug="rfc")
    elif document_state == "draft":
        doc_qs = doc_qs.exclude(states__type="draft", states__slug="rfc")

    chart_data = []
    table_data = []
    stats_title = ""

    if stats_type == "authors":
        stats_title = "Number of authors for each document"

        groups = defaultdict(list)

        for name, author_count in doc_qs.values_list("name").annotate(Count("authors")).iterator():
            groups[author_count].append(name)

        total_docs = sum(len(names) for author_count, names in groups.iteritems())

        series_data = []
        for author_count, names in sorted(groups.iteritems(), key=lambda t: t[0]):
            series_data.append((author_count, len(names) * 100.0 / total_docs))
            table_data.append((author_count, names))

        chart_data.append({
            "data": series_data,
            "name": "Percentage of documents",
        })


    return render(request, "stats/document_stats.html", {
        "chart_data": mark_safe(json.dumps(chart_data)),
        "table_data": table_data,
        "stats_title": stats_title,
        "possible_stats_types": possible_stats_types,
        "stats_type": stats_type,
        "possible_document_states": possible_document_states,
        "document_state": document_state,
    })

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

    def build_review_stats_url(stats_type_override=Ellipsis, acronym_override=Ellipsis, get_overrides={}):
        kwargs = {
            "stats_type": stats_type if stats_type_override is Ellipsis else stats_type_override,
        }
        acr = acronym if acronym_override is Ellipsis else acronym_override
        if acr:
            kwargs["acronym"] = acr

        return urlreverse(review_stats, kwargs=kwargs) + generate_query_string(request.GET, get_overrides)

    def get_choice(get_parameter, possible_choices, multiple=False):
        values = request.GET.getlist(get_parameter)
        found = [t[0] for t in possible_choices if t[0] in values]

        if multiple:
            return found
        else:
            if found:
                return found[0]
            else:
                return None

    # which overview - team or reviewer
    if acronym:
        level = "reviewer"
    else:
        level = "team"

    # statistics type - one of the tables or the chart
    possible_stats_types = [
        ("completion", "Completion status"),
        ("results", "Review results"),
        ("states", "Request states"),
    ]

    if level == "team":
        possible_stats_types.append(("time", "Changes over time"))

    possible_stats_types = [ (slug, label, build_review_stats_url(stats_type_override=slug))
                             for slug, label in possible_stats_types ]

    if not stats_type:
        return HttpResponseRedirect(build_review_stats_url(stats_type_override=possible_stats_types[0][0]))

    # what to count
    possible_count_choices = [
        ("", "Review requests"),
        ("pages", "Reviewed pages"),
    ]

    possible_count_choices = [ (slug, label, build_review_stats_url(get_overrides={ "count": slug })) for slug, label in possible_count_choices ]

    count = get_choice("count", possible_count_choices) or ""

    # time range
    def parse_date(s):
        if not s:
            return None
        try:
            return datetime.datetime.strptime(s.strip(), "%Y-%m-%d").date()
        except ValueError:
            return None

    today = datetime.date.today()
    from_date = parse_date(request.GET.get("from")) or today - dateutil.relativedelta.relativedelta(years=1)
    to_date = parse_date(request.GET.get("to")) or today

    from_time = datetime.datetime.combine(from_date, datetime.time.min)
    to_time = datetime.datetime.combine(to_date, datetime.time.max)

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
            return HttpResponseForbidden("You do not have the necessary permissions to view this page")

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
        group_by_index = ReviewRequestData._fields.index("team")

    elif level == "reviewer":
        for t in teams:
            if t.acronym == acronym:
                reviewers_for_team = t
                break
        else:
            return HttpResponseRedirect(urlreverse(review_stats))

        query_reviewers = list(Person.objects.filter(
            email__reviewrequest__time__gte=from_time,
            email__reviewrequest__time__lte=to_time,
            email__reviewrequest__team=reviewers_for_team,
            **reviewer_filter_args.get(t.pk, {})
        ).distinct())
        query_reviewers.sort(key=lambda p: p.last_name())

        query_teams = [t]

        group_by_objs = { r.pk: r for r in query_reviewers }
        group_by_index = ReviewRequestData._fields.index("reviewer")

    # now filter and aggregate the data
    possible_teams = possible_completion_types = possible_results = possible_states = None
    selected_teams = selected_completion_type = selected_result = selected_state = None

    if stats_type == "time":
        possible_teams = [(t.acronym, t.acronym) for t in teams]
        selected_teams = get_choice("team", possible_teams, multiple=True)

        def add_if_exists_else_subtract(element, l):
            if element in l:
                return [x for x in l if x != element]
            else:
                return l + [element]

        possible_teams = [(slug, label, build_review_stats_url(get_overrides={
            "team": add_if_exists_else_subtract(slug, selected_teams)
        })) for slug, label in possible_teams]
        query_teams = [t for t in query_teams if t.acronym in selected_teams]

        extracted_data = extract_review_request_data(query_teams, query_reviewers, from_time, to_time)

        req_time_index = ReviewRequestData._fields.index("req_time")

        def time_key_fn(t):
            d = t[req_time_index].date()
            #d -= datetime.timedelta(days=d.weekday()) # weekly
            d -= datetime.timedelta(days=d.day) # monthly
            return d

        found_results = set()
        found_states = set()
        aggrs = []
        for d, request_data_items in itertools.groupby(extracted_data, key=time_key_fn):
            raw_aggr = aggregate_raw_review_request_stats(request_data_items, count=count)
            aggr = compute_review_request_stats(raw_aggr)

            aggrs.append((d, aggr))

            for slug in aggr["result"]:
                found_results.add(slug)
            for slug in aggr["state"]:
                found_states.add(slug)

        results = ReviewResultName.objects.filter(slug__in=found_results)
        states = ReviewRequestStateName.objects.filter(slug__in=found_states)

        # choice

        possible_completion_types = [
            ("completed_in_time", "Completed in time"),
            ("completed_late", "Completed late"),
            ("not_completed", "Not completed"),
            ("average_assignment_to_closure_days", "Avg. compl. days"),
        ]

        possible_completion_types = [
            (slug, label, build_review_stats_url(get_overrides={ "completion": slug, "result": None, "state": None }))
            for slug, label in possible_completion_types
        ]

        selected_completion_type = get_choice("completion", possible_completion_types)

        possible_results = [
            (r.slug, r.name, build_review_stats_url(get_overrides={ "completion": None, "result": r.slug, "state": None }))
            for r in results
        ]

        selected_result = get_choice("result", possible_results)
        
        possible_states = [
            (s.slug, s.name, build_review_stats_url(get_overrides={ "completion": None, "result": None, "state": s.slug }))
            for s in states
        ]

        selected_state = get_choice("state", possible_states)

        if not selected_completion_type and not selected_result and not selected_state:
            selected_completion_type = "completed_in_time"

        series_data = []
        for d, aggr in aggrs:
            v = 0
            if selected_completion_type is not None:
                v = aggr[selected_completion_type]
            elif selected_result is not None:
                v = aggr["result"][selected_result]
            elif selected_state is not None:
                v = aggr["state"][selected_state]

            series_data.append((calendar.timegm(d.timetuple()) * 1000, v))

        data = json.dumps([{
            "data": series_data
        }])

    else: # tabular data
        extracted_data = extract_review_request_data(query_teams, query_reviewers, from_time, to_time, ordering=[level])

        data = []

        found_results = set()
        found_states = set()
        raw_aggrs = []
        for group_pk, request_data_items in itertools.groupby(extracted_data, key=lambda t: t[group_by_index]):
            raw_aggr = aggregate_raw_review_request_stats(request_data_items, count=count)
            raw_aggrs.append(raw_aggr)

            aggr = compute_review_request_stats(raw_aggr)

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
            totals = compute_review_request_stats(sum_raw_review_request_aggregations(raw_aggrs))
            totals["obj"] = "Totals"
            data.append(totals)

        results = ReviewResultName.objects.filter(slug__in=found_results)
        states = ReviewRequestStateName.objects.filter(slug__in=found_states)

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
