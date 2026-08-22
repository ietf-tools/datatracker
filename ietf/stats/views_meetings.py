# Copyright The IETF Trust 2016-2026, All Rights Reserved

from collections import defaultdict
from typing import Any
import csv

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse as urlreverse

from ietf.meeting.helpers import get_current_ietf_meeting_num
from ietf.meeting.models import Meeting, Registration
from ietf.stats.utils import (
    check_top_n_choice,
    color_from_hash,
    get_aliased_affiliations,
    get_aliased_countries,
    get_top_n_choices,
)

# Constants
FIRST_MEETING_WITH_REGISTRATION_DATA = 72


def _build_timeline_datasets(
    top_items: list[str],
    data_map: dict[str, dict[str, int]],
    sorted_meetings: list[str],
    other_totals: dict[str, int],
    include_background_color: bool = False,
) -> list[dict[str, Any]]:
    """Build Chart.js datasets for timeline charts.

    Args:
        top_items: List of top item labels (countries, affiliations, etc.).
        data_map: Mapping of {item: {meeting: count}}.
        sorted_meetings: Sorted list of meeting numbers.
        other_totals: Mapping of {meeting: count} for 'Other' category.
        include_background_color: Whether to include backgroundColor (for filled areas).

    Returns:
        List of Chart.js dataset dictionaries.

    """
    datasets: list[dict[str, Any]] = []
    for item in top_items:
        color = color_from_hash(item)
        dataset = {
            "label": item,
            "data": [data_map[item].get(m, 0) for m in sorted_meetings],
            "borderColor": color,
            "fill": bool(include_background_color),
            "tension": 0.0 if include_background_color else 0.3,
            "pointColor": color,
            "pointBackgroundColor": color,
            "pointRadius": 4,
            "pointHoverRadius": 6,
            "borderWidth": 2,
        }
        if include_background_color:
            dataset["backgroundColor"] = color + "99"
        datasets.append(dataset)

    # Add "Other" category
    datasets.append({
        "label": "Other",
        "data": [other_totals.get(m, 0) for m in sorted_meetings],
        "borderColor": "black",
        "fill": bool(include_background_color),
        "tension": 0.0 if include_background_color else 0.3,
        "pointColor": "black",
        "pointBackgroundColor": "black",
        "pointRadius": 4,
        "pointHoverRadius": 6,
        "borderWidth": 2,
    })
    if include_background_color:
        datasets[-1]["backgroundColor"] = "#00000099"

    return datasets


def _build_pie_chart_data(
    items_with_counts: list[tuple[str, int]],
    top_n: int = 20,
) -> tuple[list[str], list[int], int]:
    """Build pie chart data from sorted items.

    Args:
        items_with_counts: List of (label, count) tuples, already sorted.
        top_n: Number of top items to display.

    Returns:
        Tuple of (labels, data, total).

    """
    labels: list[str] = []
    data: list[int] = []
    total = 0

    for item, count in items_with_counts[:top_n]:
        total += count
        labels.append(item)
        data.append(count)

    other_total = 0
    for _, count in items_with_counts[top_n:]:
        other_total += count
        total += count

    if other_total > 0:
        labels.append("Other")
        data.append(other_total)

    return labels, data, total


def get_affiliation_data_for_meetings(attendance_type: str | None = None,
                                      top_n: int = 20) -> tuple[list[str], list[dict[str, Any]]]:
    """Get affiliation participation data for meetings timeline chart.

    Args:
        attendance_type: Optional filter for attendance type (e.g., 'onsite').
        top_n: Number of top items to return.

    Returns:
        Tuple of (sorted_meetings, datasets) for Chart.js.

    """
    cache_key = f"stats:get_affiliation_data_for_meetings:{attendance_type}"
    sorted_meetings, sorted_orgs = cache.get(cache_key, (None, None))
    if (sorted_meetings, sorted_orgs) == (None, None):

        # Get registration status details
        if attendance_type:
            base_registrations = Registration.objects.filter(tickets__attendance_type=attendance_type)
        else:
            base_registrations = Registration.objects.all()
        registrations = list(
            base_registrations.values("affiliation", "meeting__number")
        )

        # Prepare affiliation data, applying canonicalization and aliasing
        alias_map = get_aliased_affiliations(
            registration["affiliation"] for registration in registrations
        )

        # Count per canonicalized affiliation
        organization: dict[str, int] = {}
        meetings_set: set[str] = set()
        org_totals: dict[str, int] = defaultdict(int)
        data_map: dict[str, dict[str, int]] = defaultdict(dict)  # {org: {meeting: count}}

        for reg in registrations:
            meeting = reg["meeting__number"]
            meetings_set.add(meeting)
            if not reg["affiliation"] or not reg["affiliation"].strip():
                affiliation = "Unspecified"
            else:
                affiliation = alias_map.get(reg["affiliation"], reg["affiliation"])
            organization[affiliation] = organization.get(affiliation, 0) + 1
            org_totals[affiliation] = org_totals.get(affiliation, 0) + 1
            data_map[affiliation][meeting] = data_map[affiliation].get(meeting, 0) + 1

        # ── Step 2: Sort meetings numerically rather than alphabetically  ──
        sorted_meetings = sorted(meetings_set, key=lambda x: int(x))

        # ── Step 3: Get top N countries ──
        sorted_orgs = sorted(
            org_totals.keys(),
            key=lambda c: org_totals[c],
            reverse=True,
        )
        cache.set(
            cache_key,
            (sorted_meetings, sorted_orgs),
            settings.STATS_TIMELINE_CACHE_TIMEOUT,
        )
    top_orgs = sorted_orgs[:top_n]
    non_top_orgs = set(org_totals.keys()) - set(top_orgs)
    other_totals: dict[str, int] = defaultdict(int)
    for m in sorted_meetings:
        other_totals[m] = 0
        for c in non_top_orgs:
            other_totals[m] += int(data_map[c].get(m, 0))

    # ── Step 4: Build Chart.js datasets ──
    datasets = _build_timeline_datasets(top_orgs, data_map, sorted_meetings, other_totals)

    return sorted_meetings, datasets

def get_country_data_for_meetings(attendance_type: str | None = None,
                                  top_n: int = 20) -> tuple[list[str], list[dict[str, Any]]]:
    """Get country participation data for meetings timeline chart.

    Args:
        attendance_type: Optional filter for attendance type (e.g., 'onsite').
        top_n: Number of top items to return.

    Returns:
        Tuple of (sorted_meetings, datasets) for Chart.js.

    """
    cache_key = f"stats:get_country_data_for_meetings:{attendance_type}"
    sorted_meetings, sorted_countries = cache.get(cache_key, (None, None))
    if (sorted_meetings, sorted_countries) == (None, None):
        # Get registration status counts, aggregated by country_code
        if attendance_type:
            base_registrations = Registration.objects.filter(tickets__attendance_type=attendance_type)
        else:
            base_registrations = Registration.objects.all()
        queryset = (
            base_registrations
            .values(
                "meeting__number",      # e.g. "118", "119", "120"
                "country_code",          # country code of the participant
            )
            .annotate(participant_count=Count("id"))
            .order_by("meeting__number")  # chronological order
        )

        # Prepare country data, applying canonicalization and aliasing
        # Mainly used to conver 2-letter country code into a full name
        alias_map = get_aliased_countries(country_code
                                          for country_code
                                          in queryset.values_list("country_code", flat=True))

        # ── Step 1: Collect all meetings and country totals ──
        meetings_set: set[str] = set()
        country_totals: dict[str, int] = defaultdict(int)
        data_map: dict[str, dict[str, int]] = defaultdict(dict)  # {country: {meeting: count}}

        for row in queryset:
            meeting = row["meeting__number"]
            country = alias_map.get(row["country_code"], row["country_code"])
            count = row["participant_count"]

            meetings_set.add(meeting)
            country_totals[country] += count
            data_map[country][meeting] = data_map[country].get(meeting, 0) + count

        # ── Step 2: Sort meetings numerically rather than alphabetically  ──
        sorted_meetings = sorted(meetings_set, key=lambda x: int(x))

        # ── Step 3: Get top N countries ──
        sorted_countries = sorted(
            country_totals.keys(),
            key=lambda c: country_totals[c],
            reverse=True,
        )
        cache.set(
            cache_key,
            (sorted_meetings, sorted_countries),
            settings.STATS_TIMELINE_CACHE_TIMEOUT,
        )

    top_countries = sorted_countries[:top_n]

    # -- Step 3.bis do the 'other' category --
    non_top_countries = set(country_totals.keys()) - set(top_countries)
    other_totals: dict[str, int] = defaultdict(int)
    for m in sorted_meetings:
        other_totals[m] = 0
        for c in non_top_countries:
            other_totals[m] += int(data_map[c].get(m, 0))

    # ── Step 4: Build Chart.js datasets ──
    datasets = _build_timeline_datasets(top_countries, data_map, sorted_meetings, other_totals)

    return sorted_meetings, datasets

def get_data_for_meetings(top_n: int = 20) -> tuple[list[str], list[dict[str, Any]]]:
    """Get total participation data by attendance type for meetings timeline chart.

    Args:
        top_n: Number of top items to display in the chart.

    Returns:
        Tuple of (sorted_meetings, datasets) for Chart.js.

    """
    cache_key = f"stats:get_data_for_meetings:{top_n}"
    sorted_meetings, datasets = cache.get(cache_key, (None, None))
    if (sorted_meetings, datasets) == (None, None):
        # Get registration status counts, aggregated by ticket types
        base_registrations = (
            Registration.objects
            .filter(tickets__attendance_type__in=["onsite", "remote"])
        )
        queryset = (
            base_registrations
            .values(
                "meeting__number",      # e.g. "118", "119", "120"
                "tickets__attendance_type",
            )
            .annotate(participant_count=Count("id"))
            .order_by("meeting__number")  # chronological order
        )

        # ── Step 1: Collect all meetings and tickets totals ──
        meetings_set: set[str] = set()
        tickets_totals: dict[str, int] = defaultdict(int)
        data_map: dict[str, dict[str, int]] = defaultdict(dict)  # {ticket: {meeting: count}}

        for row in queryset:
            meeting = row["meeting__number"]
            ticket = row["tickets__attendance_type"]
            count = row["participant_count"]

            meetings_set.add(meeting)
            tickets_totals[ticket] += count
            data_map[ticket][meeting] = count

        # ── Step 2: Sort meetings numerically rather than alphabetically  ──
        sorted_meetings = sorted(meetings_set, key=lambda x: int(x))
        ticket_types = tickets_totals.keys()

        # ── Step 4: Build Chart.js datasets ──
        datasets = _build_timeline_datasets(list(ticket_types), data_map, sorted_meetings, {}, include_background_color=True)
        cache.set(
            cache_key,
            (sorted_meetings, datasets),
            settings.STATS_TIMELINE_CACHE_TIMEOUT,
        )
    return sorted_meetings, datasets

def meetings_timeline(request: Any, stats_type: str = "country") -> Any:
    """Render the meetings timeline page with participation statistics over time.

    Args:
        request: The HTTP request object.
        stats_type: Type of statistics ('country' or 'total').

    Returns:
        Rendered response for the meetings timeline template.

    """
    # Query parameters (from ?key=value)
    top_n = int(request.GET.get("top", "20"))
    # Check the top-n value against the allowed choices
    if not check_top_n_choice(top_n):
        return render(request,
                      "stats/error.html",
                      {"message": f"Invalid top_n choice: {top_n}. Valid choices are: {get_top_n_choices()}"})

    if stats_type == "reg_type":
        total_labels, total_data_sets = get_data_for_meetings(top_n=top_n)
        in_person_labels: list[str] = []
        in_person_data_sets: list[dict[str, Any]] = []
        plural_stats_type = "registration types"
    elif stats_type == "affiliation":
        total_labels, total_data_sets = get_affiliation_data_for_meetings(top_n=top_n)
        in_person_labels, in_person_data_sets = get_affiliation_data_for_meetings(attendance_type="onsite", top_n=top_n)
        plural_stats_type = "affiliations"
    elif stats_type == "country":
        total_labels, total_data_sets = get_country_data_for_meetings(top_n=top_n)
        in_person_labels, in_person_data_sets = get_country_data_for_meetings(attendance_type="onsite", top_n=top_n)
        plural_stats_type = "countries"
    else:
        return HttpResponseRedirect(urlreverse("ietf.stats.views.stats_index"))

    # Handle the download of CSV data if requested
    download = request.GET.get("download")
    if download in ("total", "in_person"):
        if download == "total":
            labels, data_sets = total_labels, total_data_sets
        else:
            labels, data_sets = in_person_labels, in_person_data_sets

        response = HttpResponse(content_type="text/csv")
        # Let's set the filename to include the stats_type, download type, and meeting number (even if template sets it, this ensures the correct filename is used)
        response["Content-Disposition"] = f'attachment; filename="{stats_type}-{download}-all.csv"'
        writer = csv.writer(response, quoting=csv.QUOTE_NONNUMERIC, lineterminator="\n", dialect="excel")
        writer.writerow(["IETF meeting", stats_type, "count"])
        for meeting_nr in labels:
            for ds in data_sets:
                count = ds["data"][labels.index(meeting_nr)]
                writer.writerow([int(meeting_nr), ds["label"], count])
        return response

    # Not for download, prepare the chart data for rendering in the template
    total_chart_data = {
        "labels": total_labels,
        "datasets": total_data_sets,
    }

    # On per country/affiliation have a separate graph for inperson
    if stats_type == "reg_type":
        in_person_chart_data = None
    else:
        in_person_chart_data = {
            "labels": in_person_labels,
            "datasets": in_person_data_sets,
        }

    # Prepare the list of choice buttons for the template
    possible_stats_types = [
        ("affiliation", "Per affiliation", urlreverse(meetings_timeline,
                                                      kwargs={"stats_type": "affiliation"})),
        ("country", "Per country", urlreverse(meetings_timeline,
                                              kwargs={"stats_type": "country"})),
        ("reg_type", "Registration type", urlreverse(meetings_timeline,
                                      kwargs={"stats_type": "reg_type"})),
    ]

    current_meeting = get_current_ietf_meeting_num()
    if stats_type == "reg_type":
        possible_stats_type = "country"
    else:
        possible_stats_type = stats_type

    possible_meeting_numbers: list[tuple[str | int, str]] = [
        ("All", urlreverse(meetings_timeline, kwargs={"stats_type": stats_type})),
        (int(current_meeting)-1, urlreverse(meeting_stats,
                                            kwargs={"meeting_number": int(current_meeting)-1, "stats_type": possible_stats_type})),
        (int(current_meeting), urlreverse(meeting_stats,
                                          kwargs={"meeting_number": int(current_meeting), "stats_type": possible_stats_type})),
        (int(current_meeting)+1, urlreverse(meeting_stats,
                                            kwargs={"meeting_number": int(current_meeting)+1, "stats_type": possible_stats_type}))]

    return render(request, "stats/meetings_timeline.html", {
        "top_n": top_n,
        "top_n_choices": get_top_n_choices(),
        "possible_stats_types": possible_stats_types,
        "possible_meeting_numbers": possible_meeting_numbers,
        "stats_type": stats_type,
        "plural_stats_type": plural_stats_type,
        "total_chart_data": total_chart_data,
        "in_person_chart_data": in_person_chart_data,
    })

def get_affiliation_data_for_meeting(meeting_number: str, top_n: int = 20,
                                     attendance_type: str | None = None) -> tuple[list[str], list[int], int]:
    """Get affiliation participation data for a specific meeting.

    Args:
        meeting_number: The meeting number.
        top_n: Number of top items to display in the chart.
        attendance_type: Optional filter for attendance type.

    Returns:
        Tuple of (labels, data, total) for chart.js display.

    """
    # Get registration status details
    base_registrations = Registration.objects.filter(meeting__number=meeting_number)
    if attendance_type:
        base_registrations = base_registrations.filter(tickets__attendance_type=attendance_type)
    registrations = base_registrations.values("affiliation")

    alias_map = get_aliased_affiliations(affiliation for affiliation
                                         in registrations.values_list("affiliation", flat=True))

    # Count per canonicalized affiliation
    organization: dict[str, int] = {}
    for reg in registrations:
        if not reg["affiliation"] or not reg["affiliation"].strip():
            affiliation = "Unspecified"
        else:
            affiliation = alias_map.get(reg["affiliation"], reg["affiliation"])
        organization[affiliation] = organization.get(affiliation, 0) + 1

    # Sort to have the largest count first (nicer in pie chart)
    sorted_orgs = sorted(organization.items(), key=lambda t: t[1], reverse=True)
    return _build_pie_chart_data(sorted_orgs, top_n)

def get_country_data_for_meeting(meeting_number: str, top_n: int = 20,
                                 attendance_type: str | None = None) -> tuple[list[str], list[int], int]:
    """Get country participation data for a specific meeting.

    Args:
        meeting_number: The meeting number.
        top_n: Number of top items to display in the chart.
        attendance_type: Optional filter for attendance type.

    Returns:
        Tuple of (labels, data, total) for chart.js display.

    """
    # Get registration status counts, aggregated by country_code
    base_registration_counts = Registration.objects.filter(meeting__number=meeting_number)
    if attendance_type:
        base_registration_counts = (
            base_registration_counts
            .filter(tickets__attendance_type=attendance_type)
        )
    registration_counts = (
        base_registration_counts
        .values("country_code")
        .annotate(count=Count("country_code"))
        .order_by("-count")
    )

    alias_map = get_aliased_countries(reg for reg in registration_counts.values_list("country_code", flat=True))

    # Convert queryset to list of (label, count) tuples
    items_with_counts = [
        (alias_map.get(item["country_code"], item["country_code"]), item["count"])
        for item in registration_counts
    ]

    return _build_pie_chart_data(items_with_counts, top_n)

def meeting_stats(request: Any, meeting_number: str | None = None, stats_type: str = "country") -> Any:
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
        Meeting.objects.filter(type_id="ietf"), number=meeting_number,
    )

    # Query parameters (from ?key=value)
    top_n = int(request.GET.get("top", "20"))
    # Check the top-n value against the allowed choices
    if not check_top_n_choice(top_n):
        return render(request, "stats/error.html", {"message": f"Invalid top_n choice: {top_n}. Valid choices are: {get_top_n_choices()}"})

    if stats_type == "affiliation":
        total_labels, total_data, total_total = get_affiliation_data_for_meeting(meeting_number, top_n=top_n)
        in_person_labels, in_person_data, in_person_total = get_affiliation_data_for_meeting(meeting_number, top_n=top_n, attendance_type="onsite")
    elif stats_type == "country":
        total_labels, total_data, total_total = get_country_data_for_meeting(meeting_number, top_n=top_n)
        in_person_labels, in_person_data, in_person_total = get_country_data_for_meeting(meeting_number, top_n=top_n, attendance_type="onsite")
    else:
        return HttpResponseRedirect(urlreverse("ietf.stats.views.stats_index"))

    # Handle the download of CSV data if requested
    download = request.GET.get("download")
    if download in ("total", "in_person"):
        if download == "total":
            labels, data = total_labels, total_data
        else:
            labels, data = in_person_labels, in_person_data

        response = HttpResponse(content_type="text/csv")
        # Let's set the filename to include the stats_type, download type, and meeting number (even if template sets it, this ensures the correct filename is used)
        response["Content-Disposition"] = f'attachment; filename="{stats_type}-{download}-{meeting_number}.csv"'
        writer = csv.writer(response, quoting=csv.QUOTE_NONNUMERIC, lineterminator="\n", dialect="excel")
        writer.writerow([stats_type, "count"])
        for label, count in zip(labels, data):
            writer.writerow([label, count])
        return response
    
    # Not for download, prepare the chart data for rendering in the template
    total_chart_data = {
        "labels": total_labels,
        "datasets": [{
            "label": f"Total Registrations by {stats_type}",
            "data": total_data,
            "backgroundColor": [color_from_hash(label)
                                if label else "#202020"
                                for label in total_labels],
            "borderColor": "#ffffff",
            "borderWidth": 2,
        }],
    }
    in_person_chart_data = {
        "labels": in_person_labels,
        "datasets": [{
            "label": f"In Person Registrations by {stats_type}",
            "data": in_person_data,
            "backgroundColor": [color_from_hash(label)
                                if label else "#202020"
                                for label in in_person_labels],
            "borderColor": "#ffffff",
            "borderWidth": 2,
        }],
    }

    # Prepare the list of choice buttons for the template
    possible_stats_types = [
        ("affiliation", "Per affiliation", urlreverse(meeting_stats,
                                                      kwargs={"meeting_number": meeting_number, "stats_type": "affiliation"})),
        ("country", "Per country", urlreverse(meeting_stats,
                                              kwargs={"meeting_number": meeting_number, "stats_type": "country"})),
    ]

    # Prepare the list of meeting number buttons for the template
    possible_meeting_numbers: list[tuple[str | int, str]] = [("All", urlreverse(meetings_timeline,
                                                                                kwargs={"stats_type": stats_type}))]
    if int(meeting_number) > FIRST_MEETING_WITH_REGISTRATION_DATA:
        possible_meeting_numbers.append((int(meeting_number)-1, urlreverse(meeting_stats,
                                                                           kwargs={"meeting_number": int(meeting_number)-1, "stats_type": stats_type})))
    possible_meeting_numbers.append((meeting_number, urlreverse(meeting_stats,
                                                                kwargs={"meeting_number": meeting_number, "stats_type": stats_type})))
    if int(meeting_number) <= int(current_meeting_number): # Allow current meeting +1
        possible_meeting_numbers.append((int(meeting_number)+1, urlreverse(meeting_stats,
                                                                           kwargs={"meeting_number": int(meeting_number)+1, "stats_type": stats_type})))

    return render(request, "stats/meeting_stats.html", {
        "meeting_number": meeting_number,
        "meeting_date": this_meeting.date,
        "meeting_country": this_meeting.country,
        "meeting_city": this_meeting.city,
        "possible_stats_types": possible_stats_types,
        "possible_meeting_numbers": possible_meeting_numbers,
        "stats_type": stats_type,
        "top_n": top_n,
        "top_n_choices": get_top_n_choices(),
        "total_chart_data": total_chart_data,
        "total_total": total_total,
        "in_person_chart_data": in_person_chart_data,
        "in_person_total": in_person_total,
    })
