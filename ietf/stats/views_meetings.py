# Copyright The IETF Trust 2016-2026, All Rights Reserved
# -*- coding: utf-8 -*-

from django.conf import settings
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse as urlreverse
from django.core.cache import cache
from collections import defaultdict

import debug                            # pyflakes:ignore

from ietf.meeting.models import Registration, Meeting
from ietf.stats.utils import color_from_hash, get_aliased_affiliations, get_aliased_countries
from ietf.meeting.helpers import get_current_ietf_meeting_num


def get_affiliation_data_for_meetings(attendance_type=None, top_n=20):
    """Get affiliation participation data for meetings timeline chart.

    Args:
        attendance_type: Optional filter for attendance type (e.g., 'onsite').

    Returns:
        Tuple of (sorted_meetings, datasets) for Chart.js.
    """
    cache_key = f'stats:get_affiliation_data_for_meetings:{attendance_type}-{top_n}'
    sorted_meetings, datasets = cache.get(cache_key, (None, None))
    if (sorted_meetings, datasets) == (None, None):

        # Get registration status details
        if attendance_type:
            registrations = Registration.objects.filter(tickets__attendance_type=attendance_type)
        else:
            registrations = Registration.objects.all()
        registrations = registrations.values('affiliation', 'meeting__number')
    
        # Prepare affiliation data, applying canonicalization and aliasing
        alias_map = get_aliased_affiliations(affiliation for affiliation in registrations.values_list('affiliation', flat=True))

        # Count per canonicalized affiliation
        organization = dict()
        meetings_set = set()
        org_totals = defaultdict(int)
        data_map = defaultdict(dict)  # {org: {meeting: count}}
    
        for reg in registrations:
            meeting = reg['meeting__number']
            meetings_set.add(meeting)
            if reg['affiliation'] is None or reg['affiliation'].strip() == '':
                affiliation = 'Unspecified'
            else:                
                affiliation = alias_map.get(reg['affiliation'], reg['affiliation'])
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
            color = color_from_hash(org)
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

def get_country_data_for_meetings(attendance_type=None, top_n=20):
    """Get country participation data for meetings timeline chart.

    Args:
        attendance_type: Optional filter for attendance type (e.g., 'onsite').

    Returns:
        Tuple of (sorted_meetings, datasets) for Chart.js.
    """
    cache_key = f'stats:get_country_data_for_meetings:{attendance_type}-{top_n}'
    sorted_meetings, datasets = cache.get(cache_key, (None, None))
    if (sorted_meetings, datasets) == (None, None):
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

        # Prepare country affiliation data, applying canonicalization and aliasing
        # Mainly used to conver 2-letter country code into a full name
        # Could possible use Country directly
        alias_map = get_aliased_countries(country_code for country_code in queryset.values_list('country_code', flat=True))

        # ── Step 1: Collect all meetings and country totals ──
        meetings_set = set()
        country_totals = defaultdict(int)
        data_map = defaultdict(dict)  # {country: {meeting: count}}
    
        for row in queryset:
            meeting = row['meeting__number']
            country = alias_map.get(row['country_code'], row['country_code']) 
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
            color = color_from_hash(country)
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

def get_data_for_meetings(top_n=20):
    """Get total participation data by attendance type for meetings timeline chart.

    Returns:
        Tuple of (sorted_meetings, datasets) for Chart.js.
    """
    cache_key = f'stats:get_data_for_meetings:{top_n}'
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
        datasets = []
        for idx, ticket_type in enumerate(ticket_types):
            color = color_from_hash(ticket_type)
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
    # Query parameters (from ?key=value)
    top_n = int(request.GET.get('top', '20'))

    if stats_type == 'total':
        total_labels, total_data_sets = get_data_for_meetings(top_n=top_n)
        in_person_labels = ([], [])
        in_person_data_sets = ([], [])
        plural_stats_type = ''
    elif stats_type == 'affiliation':
        total_labels, total_data_sets = get_affiliation_data_for_meetings(top_n=top_n)
        in_person_labels, in_person_data_sets = get_affiliation_data_for_meetings(attendance_type='onsite', top_n=top_n)
        plural_stats_type = 'affiliations'
    elif stats_type == 'country':
        total_labels, total_data_sets = get_country_data_for_meetings(top_n=top_n)
        in_person_labels, in_person_data_sets = get_country_data_for_meetings(attendance_type='onsite', top_n=top_n)
        plural_stats_type = 'countries'
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

    possible_meeting_numbers = [
        ('All', urlreverse(meetings_timeline, kwargs={'stats_type': stats_type})),
        (int(current_meeting)-1, urlreverse(meeting_stats, kwargs={'meeting_number': int(current_meeting)-1, 'stats_type': possible_stats_type})),
        (int(current_meeting), urlreverse(meeting_stats, kwargs={'meeting_number': int(current_meeting), 'stats_type': possible_stats_type})),
        (int(current_meeting)+1, urlreverse(meeting_stats, kwargs={'meeting_number': int(current_meeting)+1, 'stats_type': possible_stats_type}))]

    return render(request, "stats/meetings_timeline.html", {
        "top_n": top_n,
        "possible_stats_types": possible_stats_types,
        "possible_meeting_numbers": possible_meeting_numbers,
        "stats_type": stats_type,
        "plural_stats_type": plural_stats_type,
        "total_chart_data": total_chart_data,
        "in_person_chart_data": in_person_chart_data,
    })

def get_affiliation_data_for_meeting(meeting_number, top_n=20, attendance_type=None):
    """Get affiliation participation data for a specific meeting.

    Args:
        meeting_number: The meeting number.
        attendance_type: Optional filter for attendance type.

    Returns:
        Tuple of (labels, data, total) for chart display.
    """
    # Get registration status details
    registrations = Registration.objects.filter(meeting__number=meeting_number)
    if attendance_type:
        registrations = registrations.filter(tickets__attendance_type=attendance_type)
    registrations = registrations.values('affiliation')

    alias_map = get_aliased_affiliations(affiliation for affiliation in registrations.values_list('affiliation', flat=True))

    # Count per canonicalized affiliation
    organization = dict()
    for reg in registrations:
        if reg['affiliation'] is None or reg['affiliation'].strip() == '':
            affiliation = 'Unspecified'
        else:
            affiliation = alias_map.get(reg['affiliation'], reg['affiliation'])                                
        organization[affiliation] = organization.get(affiliation, 0) + 1

    # Sort to have the largest count first (nicer in pie chart)
    sorted_orgs = sorted(organization.items(), key=lambda t: t[1], reverse=True)
    labels = []
    data = []
    total = 0
    for org, count in sorted_orgs[:top_n]:
        total += count
        labels.append(org)
        data.append(count)

    other_total = 0
    for _, count in sorted_orgs[top_n:]:
        other_total += count
        total += count

    if other_total > 0:
        labels.append('Other')
        data.append(other_total)


    return labels, data, total

def get_country_data_for_meeting(meeting_number, top_n=20, attendance_type=None):
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

    alias_map = get_aliased_countries(reg for reg in registration_counts.values_list('country_code', flat=True))
    labels = []
    data = []
    total = 0
    country_totals = defaultdict(int)
    for item in registration_counts[:top_n]:
        total += item['count']
        country = alias_map.get(item['country_code'], item['country_code'])
        labels.append(country)
        data.append(item['count'])
        country_totals[country] = item['count']

    other_total = 0
    for item in registration_counts[top_n:]:
        other_total += item['count']
        total += item['count']

    if other_total > 0:
        labels.append('Other')
        data.append(other_total)

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
    current_meeting_number = get_current_ietf_meeting_num()
    if meeting_number is None:
        meeting_number = current_meeting_number
    this_meeting = get_object_or_404(
        Meeting.objects.filter(type_id="ietf"), number=meeting_number
    )

    # Query parameters (from ?key=value)
    top_n = int(request.GET.get('top', '20'))

    if stats_type == 'affiliation':
        total_labels, total_data, total_total = get_affiliation_data_for_meeting(meeting_number, top_n=top_n)
        in_person_labels, in_person_data, in_person_total = get_affiliation_data_for_meeting(meeting_number, top_n=top_n, attendance_type='onsite')
    elif stats_type == 'country':
        total_labels, total_data, total_total = get_country_data_for_meeting(meeting_number, top_n=top_n)
        in_person_labels, in_person_data, in_person_total = get_country_data_for_meeting(meeting_number, top_n=top_n, attendance_type='onsite')
    else:
        return HttpResponseRedirect(urlreverse("ietf.stats.views.stats_index"))

    total_chart_data = {
        'labels': total_labels,
        'datasets': [{
            'label': 'Total Registrations by ' + stats_type,
            'data': total_data,
            'backgroundColor': [color_from_hash(label) if label else '#202020' for label in total_labels],
            'borderColor': '#ffffff',
            'borderWidth': 2,
        }]
    }
    in_person_chart_data = {
        'labels': in_person_labels,
        'datasets': [{
            'label': 'In Person Registrations by ' + stats_type,
            'data': in_person_data,
            'backgroundColor': [color_from_hash(label) if label else '#202020' for label in in_person_labels],
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
    if int(meeting_number) <= int(current_meeting_number): # Allow current meeting +1
        possible_meeting_numbers.append((int(meeting_number)+1, urlreverse(meeting_stats, kwargs={'meeting_number': int(meeting_number)+1, 'stats_type': stats_type})))

    return render(request, "stats/meeting_stats.html", {
        "meeting_number": meeting_number,
        "meeting_date": this_meeting.date,
        "meeting_country": this_meeting.country,
        "meeting_city": this_meeting.city,
        "possible_stats_types": possible_stats_types,
        "possible_meeting_numbers": possible_meeting_numbers,
        "stats_type": stats_type,
        "top_n": top_n,
        "total_chart_data": total_chart_data,
        "total_total": total_total,
        "in_person_chart_data": in_person_chart_data,
        "in_person_total": in_person_total
    })
