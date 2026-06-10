# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import calendar
import datetime
import itertools
import json
import dateutil.relativedelta
from collections import defaultdict

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse as urlreverse
from django.db.models import Count

import debug                            # pyflakes:ignore

from ietf.review.utils import (extract_review_assignment_data,
                               aggregate_raw_period_review_assignment_stats,
                               ReviewAssignmentData,
                               sum_period_review_assignment_stats,
                               sum_raw_review_assignment_aggregations)
from ietf.group.models import Role, Group
from ietf.person.models import Person
from ietf.name.models import ReviewResultName, CountryName, ReviewAssignmentStateName
from ietf.meeting.models import Registration
from ietf.ietfauth.utils import has_role
from ietf.utils.response import permission_denied
from ietf.utils.timezone import date_today, DEADLINE_TZINFO
from ietf.meeting.helpers import get_current_ietf_meeting_num, get_ietf_meeting

# Color palette for lines
colors = [
    '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
    '#FF9F40', '#C9CBCF', '#7BC043', '#F37735', '#00ABA9',
    '#2B5797', '#E81123', '#00A4EF', '#7FBA00', '#FFB900',
    '#D83B01', '#B4009E', '#5C2D91', '#008575', '#E3008C',
]

def stats_index(request):
    """Render the statistics index page with the current meeting number as it is required by the meeting menu item."""
    current_meeting = get_current_ietf_meeting_num()
    return render(request, "stats/index.html", {
        "current_meeting": current_meeting
    })

def generate_query_string(query_dict, overrides):
    """
    Returns:
        A query string starting with '?' if there are parameters, empty string otherwise.
    """
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
    """Extract a choice from the request GET parameters.

    Since statistics pages use links for navigation instead of forms,
    this helper selects between possible choices from the URL parameters.

    Args:
        request: The HTTP request object.
        get_parameter: The name of the GET parameter.
        possible_choices: List of tuples (value, label).
        multiple: If True, return a list of found values; otherwise return the first found or None.

    Returns:
        The selected value(s) or None.
    """
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
    """Add URLs to a list of choices.

    Args:
        choices: List of tuples (slug, label).
        url_builder: Function that takes a slug and returns a URL.

    Returns:
        List of tuples (slug, label, url).
    """
    return [ (slug, label, url_builder(slug)) for slug, label in choices]

def document_stats(request, stats_type=None):
    # timeline per year, or per specific year: streams, affiliation, rfc vs I-D
    # could also be time between individual/WG I-D to rfc publication/IESG ballot
    # DISCUSS resolution time
    # Humm also split by authors (affiliation) / documents (the rest) probably
    """Redirect to the stats index page. Deprecated view."""
    return HttpResponseRedirect(urlreverse("ietf.stats.views.stats_index"))

def known_countries_list(request, stats_type=None, acronym=None):
    """Render a list of known countries with their aliases."""
    countries = CountryName.objects.prefetch_related("countryalias_set")
    for c in countries:
        # the sorting is a bit of a hack - it puts the ISO code first
        # since it was added in a migration
        c.aliases = sorted(c.countryalias_set.all(), key=lambda a: a.pk)

    return render(request, "stats/known_countries_list.html", {
        "countries": countries,
    })

def canonicalize_affiliation(affiliation):
    """Canonicalize an affiliation string by removing common suffixes and standardizing prefixes.

    Args:
        affiliation: The affiliation string to canonicalize.

    Returns:
        The canonicalized affiliation string, or None if input is None.
    """
    if not affiliation or affiliation.lower() in ('n/a', 'none', 'unspecified'):
        return None
    for suffix in ('ab', 'ag', 'corp', 'corp.', 'corporation', 'gmbh', 'inc.', 'inc', 'international pte ltd', 'llc', 'ltd', 'ltd.', 'private limited', 'pty ltd', 'pvt ltd'):
        if affiliation.lower().endswith(', ' + suffix):
            affiliation = affiliation[:-(len(suffix)+2)]
        elif affiliation.lower().endswith(' ' + suffix):
            affiliation = affiliation[:-(len(suffix)+1)]
        elif affiliation.lower().endswith(',' + suffix):
            affiliation = affiliation[:-(len(suffix)+1)]
    for prefix in ('akamai','apple', 'cisco', 'futurewei', 'google', 'hitachi', 'hpe', 'huawei', 'juniper', 'meta', 'nokia', 'ntt', 'siemens'):
        if affiliation.lower().startswith(prefix + ' '):
            affiliation = prefix
    return affiliation.title()

def get_affiliation_data_for_meetings(attendance_type=None):
    """Get affiliation participation data for meetings timeline chart.

    Args:
        attendance_type: Optional filter for attendance type (e.g., 'onsite').

    Returns:
        Tuple of (sorted_meetings, datasets) for Chart.js.
    """
    cache_key = f'stats:get_affiliation_data_for_meetings:{attendance_type}'
    sorted_meetings, datasets = cache.get(cache_key, (None, None))
    if (sorted_meetings, datasets) == (None, None):
        top_n = 20  # could be a parameter, but would need to adjust cache handling

        # Get registration status details
        if attendance_type:
            registrations = Registration.objects.filter(tickets__attendance_type=attendance_type)
        else:
            registrations = Registration.objects.all()
        registrations = registrations.values('affiliation', 'meeting__number')
    
        # Count per canonicalized affiliation
        organization = dict()
        meetings_set = set()
        org_totals = defaultdict(int)
        data_map = defaultdict(dict)  # {org: {meeting: count}}
    
        for reg in registrations:
            meeting = reg['meeting__number']
            meetings_set.add(meeting)
            affiliation = canonicalize_affiliation(reg['affiliation']) or "Unspecified"
            organization[affiliation] = organization.get(affiliation, 0) + 1
            org_totals[affiliation] = org_totals.get(affiliation, 0) + 1
            data_map[affiliation][meeting] = data_map[affiliation].get(meeting, 0) + 1
    
        # ── Step 2: Sort meetings numerically rather than alphabetically  ──
        sorted_meetings = sorted(meetings_set, key=lambda x: int(x) if x.isdigit() else x)
    
        # ── Step 3: Get top N countries ──
        top_orgs = sorted(
            org_totals.keys(),
            key=lambda c: org_totals[c],
            reverse=True
        )[:top_n]
        non_top_orgs = org_totals.keys() - top_orgs
        other_totals = defaultdict(int)
        for m in sorted_meetings:
            other_totals[m] = 0
            for c in non_top_orgs:
                other_totals[m] += int(data_map[c].get(m, 0))
    
        # ── Step 4: Build Chart.js datasets ──
    
        datasets = []
        for idx, org in enumerate(top_orgs):
            color = colors[idx % len(colors)]
            datasets.append({
                'label': org,
                'data': [data_map[org].get(m, 0) for m in sorted_meetings],
                'borderColor': color,
                'fill': False,
                'tension': 0.3,
                'pointColor': color,
                'pointBackgroundColor': color,
                'pointRadius': 4,
                'pointHoverRadius': 6,
                'borderWidth': 2,
            })
    
        # -- Step 4.bis handle the other --
        datasets.append({
            'label': 'Other',
            'data': [other_totals.get(m, 0) for m in sorted_meetings],
            'borderColor': 'black',
            'fill': False,
            'tension': 0.3,
            'pointColor': 'black',
            'pointBackgroundColor': 'black',
            'pointRadius': 4,
            'pointHoverRadius': 6,
            'borderWidth': 2,
        })
        cache.set(
            cache_key,
            (sorted_meetings, datasets),
            settings.STATS_TIMELINE_CACHE_TIMEOUT,
        )

    return sorted_meetings, datasets

def get_country_data_for_meetings(attendance_type=None):
    """Get country participation data for meetings timeline chart.

    Args:
        attendance_type: Optional filter for attendance type (e.g., 'onsite').

    Returns:
        Tuple of (sorted_meetings, datasets) for Chart.js.
    """
    cache_key = f'stats:get_country_data_for_meetings:{attendance_type}'
    sorted_meetings, datasets = cache.get(cache_key, (None, None))
    if (sorted_meetings, datasets) == (None, None):
        top_n = 10  # could be a parameter, but would need to adjust cache handling
        # Get registration status counts, aggregated by country_code
        if attendance_type:
            registrations = Registration.objects.filter(tickets__attendance_type=attendance_type)
        else:
            registrations = Registration.objects.all()
        queryset = (
            registrations
            .values(
                'meeting__number',      # e.g. "118", "119", "120"
                'country_code'          # country code of the participant
            )
            .annotate(participant_count=Count('id'))
            .order_by('meeting__number')  # chronological order
        )
    
        # ── Step 1: Collect all meetings and country totals ──
        meetings_set = set()
        country_totals = defaultdict(int)
        data_map = defaultdict(dict)  # {country: {meeting: count}}
    
        for row in queryset:
            meeting = row['meeting__number']
            country = row['country_code']
            count = row['participant_count']
    
            meetings_set.add(meeting)
            country_totals[country] += count
            data_map[country][meeting] = count
    
        # ── Step 2: Sort meetings numerically rather than alphabetically  ──
        sorted_meetings = sorted(meetings_set, key=lambda x: int(x) if x.isdigit() else x)
    
        # ── Step 3: Get top N countries ──
        top_countries = sorted(
            country_totals.keys(),
            key=lambda c: country_totals[c],
            reverse=True
        )[:top_n]
    
        # -- Step 3.bis do the 'other' category --
        non_top_countries = country_totals.keys() - top_countries
        other_totals = defaultdict(int)
        for m in sorted_meetings:
            other_totals[m] = 0
            for c in non_top_countries:
                other_totals[m] += int(data_map[c].get(m, 0))
    
        # ── Step 4: Build Chart.js datasets ──
    
        datasets = []
        for idx, country in enumerate(top_countries):
            color = colors[idx % len(colors)]
            datasets.append({
                'label': country,
                'data': [data_map[country].get(m, 0) for m in sorted_meetings],
                'borderColor': color,
                'fill': False,
                'tension': 0.3,
                'pointColor': color,
                'pointBackgroundColor': color,
                'pointRadius': 4,
                'pointHoverRadius': 6,
                'borderWidth': 2,
            })
    
        # -- Step 4.bis handle the other --
        datasets.append({
            'label': 'Other',
            'data': [other_totals.get(m, 0) for m in sorted_meetings],
            'borderColor': 'black',
            'fill': False,
            'tension': 0.3,
            'pointColor': 'black',
            'pointBackgroundColor': 'black',
            'pointRadius': 4,
            'pointHoverRadius': 6,
            'borderWidth': 2,
        })
        cache.set(
            cache_key,
            (sorted_meetings, datasets),
            settings.STATS_TIMELINE_CACHE_TIMEOUT,
        )

    return sorted_meetings, datasets

def get_data_for_meetings():
    """Get total participation data by attendance type for meetings timeline chart.

    Returns:
        Tuple of (sorted_meetings, datasets) for Chart.js.
    """
    cache_key = "stats:get_data_for_meetings"
    sorted_meetings, datasets = cache.get(cache_key, (None, None))
    if (sorted_meetings, datasets) == (None, None):
        # Get registration status counts, aggregated by ticket types
        registrations = Registration.objects.filter(tickets__attendance_type__in=['onsite', 'remote'])
        queryset = (
            registrations
            .values(
                'meeting__number',      # e.g. "118", "119", "120"
                'tickets__attendance_type'
            )
            .annotate(participant_count=Count('id'))
            .order_by('meeting__number')  # chronological order
        )
    
        # ── Step 1: Collect all meetings and tickets totals ──
        meetings_set = set()
        tickets_totals = defaultdict(int)
        data_map = defaultdict(dict)  # {ticket: {meeting: count}}
    
        for row in queryset:
            meeting = row['meeting__number']
            ticket = row['tickets__attendance_type']
            count = row['participant_count']
    
            meetings_set.add(meeting)
            tickets_totals[ticket] += count
            data_map[ticket][meeting] = count
    
        # ── Step 2: Sort meetings numerically rather than alphabetically  ──
        sorted_meetings = sorted(meetings_set, key=lambda x: int(x) if x.isdigit() else x)
        ticket_types = tickets_totals.keys()
        
        # ── Step 4: Build Chart.js datasets ──
        # Color palette for lines
        colors = [ '#FF6384', '#36A2EB']
    
        datasets = []
        for idx, ticket_type in enumerate(ticket_types):
            color = colors[idx % len(colors)]
            datasets.append({
                'label': ticket_type,
                'data': [data_map[ticket_type].get(m, 0) for m in sorted_meetings],
                'borderColor': color,
                'backgroundColor': color + '99', # 60% opacity fill
                'fill': True,
                'tension': 0.0,
                'pointColor': color,
                'pointBackgroundColor': color,
                'pointRadius': 4,
                'pointHoverRadius': 6,
                'borderWidth': 2,
            })
        cache.set(
            cache_key,
            (sorted_meetings, datasets),
            settings.STATS_TIMELINE_CACHE_TIMEOUT,
        )
    return sorted_meetings, datasets

def meetings_timeline(request, stats_type='country'):
    """Render the meetings timeline page with participation statistics over time.

    Args:
        request: The HTTP request object.
        stats_type: Type of statistics ('country' or 'total').
        top_n: Number of top items to show (for country stats).

    Returns:
        Rendered response for the meetings timeline template.
    """
    if stats_type == 'total':
        total_labels, total_data_sets = get_data_for_meetings()
        in_person_labels = ([], [])
        in_person_data_sets = ([], [])
        top_n = len(total_data_sets) - 1  # subtract one because we don't count "other"
    elif stats_type == 'affiliation':
        total_labels, total_data_sets = get_affiliation_data_for_meetings()
        in_person_labels, in_person_data_sets = get_affiliation_data_for_meetings(attendance_type='onsite')
        top_n = len(total_data_sets) - 1  # subtract one because we don't count "other"
    elif stats_type == 'country':
        total_labels, total_data_sets = get_country_data_for_meetings()
        in_person_labels, in_person_data_sets = get_country_data_for_meetings(attendance_type='onsite')
        top_n = len(total_data_sets) - 1  # subtract one because we don't count "other"
    else:
        return HttpResponseRedirect(urlreverse("ietf.stats.views.stats_index"))

    total_chart_data = {
        'labels': total_labels,
        'datasets': total_data_sets,
    }

    # On per country/affiliation have a separate graph for inperson
    if stats_type == 'total':
        in_person_chart_data = None
    else:
        in_person_chart_data = {
            'labels': in_person_labels,
            'datasets': in_person_data_sets,
        }

    # Prepare the list of choice buttons for the template
    possible_stats_types = [
        ("affiliation", "Per affiliation", urlreverse(meetings_timeline, kwargs={'stats_type': 'affiliation'})),
        ("country", "Per country", urlreverse(meetings_timeline, kwargs={'stats_type': 'country'})),
        ("total", "Total", urlreverse(meetings_timeline, kwargs={'stats_type': 'total'})),
    ]

    current_meeting = get_current_ietf_meeting_num()
    if stats_type == 'total':
        possible_stats_type = 'country'
    else:
        possible_stats_type = stats_type

    possible_meeting_numbers = [(int(current_meeting)-1, urlreverse(meeting_stats, kwargs={'meeting_number': int(current_meeting)-1, 'stats_type': possible_stats_type})),
        (int(current_meeting), urlreverse(meeting_stats, kwargs={'meeting_number': int(current_meeting), 'stats_type': possible_stats_type})),
        (int(current_meeting)+1, urlreverse(meeting_stats, kwargs={'meeting_number': int(current_meeting)+1, 'stats_type': possible_stats_type}))]

    return render(request, "stats/meetings_timeline.html", {
        "top_n": top_n,
        "possible_stats_types": possible_stats_types,
        "possible_meeting_numbers": possible_meeting_numbers,
        "stats_type": stats_type,
        "total_chart_data": total_chart_data,
        "in_person_chart_data": in_person_chart_data,
    })

def get_affiliation_data_for_meeting(meeting_number, minimum_required, attendance_type=None):
    """Get affiliation participation data for a specific meeting.

    Args:
        meeting_number: The meeting number.
        minimum_required: Minimum count to include in main data (others go to 'Other').
        attendance_type: Optional filter for attendance type.

    Returns:
        Tuple of (labels, data, total) for chart display.
    """
    # Get registration status details
    registrations = Registration.objects.filter(meeting__number=meeting_number)
    if attendance_type:
        registrations = registrations.filter(tickets__attendance_type=attendance_type)
    registrations = registrations.values('affiliation')

    # Count per canonicalized affiliation
    organization = dict()
    for reg in registrations:
        affiliation = canonicalize_affiliation(reg['affiliation']) or "Unspecified"
        organization[affiliation] = organization.get(affiliation, 0) + 1

    # Sort to have the largest count first (nicer in pie chart)
    sorted_orgs = sorted(organization.items(), key=lambda t: t[1], reverse=True)
    labels = []
    data = []
    others_count = 0
    total = 0
    for org, count in sorted_orgs:
        total += count
        if count > minimum_required:
            labels.append(org)
            data.append(count)
        else:
            others_count += count

    if others_count > 0:
        labels.append('Other')
        data.append(others_count)

    return labels, data, total

def get_data_for_meeting(meeting_number, minimum_required, attendance_type=None):
    """Get country participation data for a specific meeting.

    Args:
        meeting_number: The meeting number.
        minimum_required: Minimum count to include in main data (others go to 'Other').
        attendance_type: Optional filter for attendance type.

    Returns:
        Tuple of (labels, data, total) for chart display.
    """
    # Get registration status counts, aggregated by country_code
    registration_counts = Registration.objects.filter(meeting__number=meeting_number)
    if attendance_type:
        registration_counts = registration_counts.filter(tickets__attendance_type=attendance_type)
    registration_counts = registration_counts.values('country_code').annotate(count=Count('country_code')).order_by('-count')

    labels = []
    data = []
    others_count = 0
    total = 0
    for item in registration_counts:
        total += item['count']
        if item['count'] > minimum_required:
            labels.append(item['country_code'])
            data.append(item['count'])
        else:
            others_count += item['count']

    if others_count > 0:
        labels.append('Other')
        data.append(others_count)

    return labels, data, total

def meeting_stats(request, meeting_number=None, stats_type='country'):
    """Render statistics for a specific meeting.

    Args:
        request: The HTTP request object.
        meeting_number: The meeting number (defaults to current).
        stats_type: Type of statistics ('country' or 'affiliation').

    Returns:
        Rendered response for the meeting stats template.
    """

    current_meeting = get_current_ietf_meeting_num()
    if meeting_number is None:
        meeting_number = current_meeting

    this_meeting = get_ietf_meeting(meeting_number)

    if stats_type == 'affiliation':
        minimum_required = 4
        total_labels, total_data, total_total = get_affiliation_data_for_meeting(meeting_number, minimum_required)
        in_person_labels, in_person_data, in_person_total = get_affiliation_data_for_meeting(meeting_number, minimum_required, attendance_type='onsite')
    elif stats_type == 'country':
        minimum_required = 10
        total_labels, total_data, total_total = get_data_for_meeting(meeting_number, minimum_required)
        in_person_labels, in_person_data, in_person_total = get_data_for_meeting(meeting_number, minimum_required, attendance_type='onsite')
    else:
        return HttpResponseRedirect(urlreverse("ietf.stats.views.stats_index"))

    total_chart_data = {
        'labels': total_labels,
        'datasets': [{
            'label': 'Total Registrations by ' + stats_type,
            'data': total_data,
            'borderColor': '#ffffff',
            'borderWidth': 2,
        }]
    }
    in_person_chart_data = {
        'labels': in_person_labels,
        'datasets': [{
            'label': 'In Person Registrations by ' + stats_type,
            'data': in_person_data,
            'borderColor': '#ffffff',
            'borderWidth': 2,
        }]
    }

    # Prepare the list of choice buttons for the template
    possible_stats_types = [
        ("affiliation", "Per affiliation", urlreverse(meeting_stats, kwargs={'meeting_number': meeting_number, 'stats_type': 'affiliation'})),
        ("country", "Per country", urlreverse(meeting_stats, kwargs={'meeting_number': meeting_number, 'stats_type': 'country'})),
    ]

    # Prepare the list of meeting number buttons for the template
    possible_meeting_numbers = [('All', urlreverse(meetings_timeline, kwargs={'stats_type': stats_type}))]
    if int(meeting_number) > 72:  # No registration data before IETF-72
        possible_meeting_numbers.append((int(meeting_number)-1, urlreverse(meeting_stats, kwargs={'meeting_number': int(meeting_number)-1, 'stats_type': stats_type})))
    possible_meeting_numbers.append((meeting_number, urlreverse(meeting_stats, kwargs={'meeting_number': meeting_number, 'stats_type': stats_type})))
    if int(meeting_number) <= int(current_meeting): # Allow current meeting +1
        possible_meeting_numbers.append((int(meeting_number)+1, urlreverse(meeting_stats, kwargs={'meeting_number': int(meeting_number)+1, 'stats_type': stats_type})))

    return render(request, "stats/meeting_stats.html", {
        "meeting_number": meeting_number,
        "meeting_date": this_meeting.date,
        "meeting_country": this_meeting.country,
        "meeting_city": this_meeting.city,
        "possible_stats_types": possible_stats_types,
        "possible_meeting_numbers": possible_meeting_numbers,
        "stats_type": stats_type,
        "minimum_required": minimum_required,
        "total_chart_data": total_chart_data,
        "total_total": total_total,
        "in_person_chart_data": in_person_chart_data,
        "in_person_total": in_person_total
    })


@login_required
def review_stats(request, stats_type=None, acronym=None):
    """Render review statistics page with tables and charts for review assignments.

    Shows completion status, results, assignment states, and time series data.
    Supports both team-level and reviewer-level views with filtering options.

    Args:
        request: The HTTP request object.
        stats_type: Type of statistics ('completion', 'results', 'states', 'time').
        acronym: Team acronym for reviewer-level view (None for team view).

    Returns:
        Rendered response for the review stats template.
    """
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
