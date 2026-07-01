# Copyright The IETF Trust 2016-2026, All Rights Reserved
# -*- coding: utf-8 -*-

from typing import Tuple, List, Dict, Any

from django.conf import settings
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse as urlreverse
from django.core.cache import cache

import debug                            # pyflakes:ignore

from collections import defaultdict

from ietf.doc.models import Document
from ietf.stats.utils import color_from_hash, check_top_n_choice, get_top_n_choices

def get_total_data_for_documents(
    doc_type: str = 'rfc',
    group_by: str = 'level',
    top_n: int = 20,
) -> Dict[str, Any]:
    """Get aggregated document statistics grouped by the specified field.

    Args:
        doc_type: Document type filter ('rfc', 'draft', 'all', 'wg-draft').
        group_by: Field to group by (e.g., 'stream__name', 'group__name').
        top_n: Number of top groups to display.

    Returns:
        Chart.js compatible data dictionary with labels and datasets.
    """
    # Build a dynamic query set filter
    filters = Q()
    if doc_type == 'all':
        filters &= Q(type_id__in=['draft', 'rfc'])
    elif doc_type == 'wg-draft':
        filters &= Q(type_id='draft')
        filters &= Q(document__group__type_id="wg")
    else:
        filters &= Q(type_id=doc_type)
    queryset = (
        Document.objects
        .filter(filters)
        .values(group_by)
        .annotate(document_count=Count('id', distinct=True))
        .order_by('-document_count')
    )

    # Convert queryset to dictionary, aggregating by group
    group_count_dict: Dict[str, int] = {}
    for group, count in queryset.values_list(group_by, 'document_count'):
        if not group or group == '':
            group = 'Unspecified'
        group_count_dict[group] = group_count_dict.get(group, 0) + count

    sorted_groups = sorted(group_count_dict.items(), key=lambda x: x[1], reverse=True)
    top_groups = sorted_groups[:top_n]
    other_count = sum(count for _, count in sorted_groups[top_n:])
    if other_count > 0:
        top_groups.append(('Other', other_count))

    labels: Tuple[str, ...] = tuple(label for label, _ in top_groups)
    data: Tuple[int, ...] = tuple(count for _, count in top_groups)
    chart_data: Dict[str, Any] = {
        'labels': labels,
        'datasets': [{
            'data': data,
            'backgroundColor': [color_from_hash(label) if label else '#202020' for label in labels],
            'borderColor': 'black',
            'borderWidth': 1,
        }],
    }
    return chart_data

def documents_total(request: Any, doc_type: str = 'rfc', stats_type: str = 'level') -> Any:
    """Render document statistics page with pie chart aggregations.

    Args:
        request: The HTTP request object.
        doc_type: Type of documents to display.
        stats_type: Field to aggregate by.

    Returns:
        Rendered response for the documents_total template.
    """
    # Query parameters (from ?key=value)
    try:
        top_n = max(1, min(int(request.GET.get('top', '10')), 100))
    except (ValueError, TypeError):
        top_n = 10
    # Check the top-n value against the allowed choices
    if not check_top_n_choice(top_n):
        return render(request, "stats/error.html", {"message": f"Invalid top_n choice: {top_n}. Valid choices are: {get_top_n_choices()}"})


    if stats_type == 'stream':
        chart_data = get_total_data_for_documents(doc_type, 'stream__name', top_n)
    elif stats_type == 'level' and doc_type == 'draft':
        chart_data = get_total_data_for_documents(doc_type, 'intended_std_level_id', top_n)
    elif stats_type == 'level' and doc_type == 'rfc':
        chart_data = get_total_data_for_documents(doc_type, 'std_level_id', top_n)
    elif stats_type == 'wg':
        chart_data = get_total_data_for_documents(doc_type, 'group__name', top_n)
    else:
        return HttpResponseRedirect(urlreverse("ietf.stats.views.stats_index"))

    # Prepare the list of choice buttons for the template
    possible_docs_types = [
        ("draft", "Drafts", urlreverse(documents_total, kwargs={'doc_type': 'draft', 'stats_type': stats_type})),
        ("rfc", "RFCs", urlreverse(documents_total, kwargs={'doc_type': 'rfc', 'stats_type': stats_type})),
    ]

    possible_stats_types = [
        ("stream", "Streams", urlreverse(documents_total, kwargs={'doc_type': doc_type, 'stats_type': 'stream'})),
        ("wg", "Working Groups", urlreverse(documents_total, kwargs={'doc_type': doc_type, 'stats_type': 'wg'})),
    ]
    if doc_type == 'draft':
        possible_stats_types.append(("level", "Intended Status", urlreverse(documents_total, kwargs={'doc_type': doc_type, 'stats_type': 'level'})))
    elif doc_type == 'rfc':
        possible_stats_types.append(("level", "Category", urlreverse(documents_total, kwargs={'doc_type': doc_type, 'stats_type': 'level'})))

    return render(request, "stats/documents_total.html", {
        "top_n": top_n,
        "top_n_choices": get_top_n_choices(),
        "objects": "documents",
        "possible_docs_types": possible_docs_types,
        "possible_stats_types": possible_stats_types,
        "timeline_url": urlreverse(documents_timeline, kwargs={'doc_type': doc_type, 'stats_type': stats_type}),
        "total_url": urlreverse(documents_total, kwargs={'doc_type': doc_type, 'stats_type': stats_type}),
        "doc_type": doc_type,
        "stats_type": stats_type,
        "chart_data": chart_data,
    })

def get_timeline_data_for_documents(
    doc_type: str = 'rfc',
    group_by: str = 'stream__name',
    top_n: int = 10,
) -> Tuple[List[int], List[Dict[str, Any]]]:
    """Get timeline data for documents grouped by field over years.

    Args:
        doc_type: Document type filter ('rfc', 'draft', 'all').
        group_by: Field to group by (e.g., 'stream__name', 'group__name').
        top_n: Number of top groups to display.

    Returns:
        Tuple of (sorted_years, datasets) for Chart.js timeline chart.
    """
    cache_key = f'stats:get_timeline_data_for_documents:{doc_type}-{group_by}'
    result = cache.get(cache_key, None)
    
    # Initialize variables with proper types
    years_set: list[int]
    documents_totals: Dict[str, int]
    data_map: Dict[int, Dict[str, int]]
    
    if result is not None:
        years_set, documents_totals, data_map = result
    else:
        if doc_type != 'all':  # Filter by specific document type
            queryset = Document.objects.filter(type_id=doc_type)
        else: # doc_type == 'all', include both drafts and RFCs (and this option is no more used in urls.py though)
            queryset = Document.objects.filter(type_id__in=['draft', 'rfc'])

        # ── Step 1: Collect all years and document totals ──
        years_set_temp: set[int] = set()
        documents_totals = defaultdict(int)
        data_map = defaultdict(dict)  # {year: {group: count}}

        for row in queryset:
            if not row.pub_date():
                continue
            year = row.pub_date().year
            if group_by == 'stream__name':
                group = row.stream.name if row.stream else 'Unspecified'
            elif group_by == 'group__name':
                group = row.group.name if row.group else 'Unspecified'
            else:
                group = getattr(row, group_by, None)
                if not group:
                    group = 'Unspecified'
            years_set_temp.add(year)
            documents_totals[group] += 1
            data_map[year][group] = data_map[year].get(group, 0) + 1

        # ── Step 2: Sort years numerically ──
        years_set = sorted(years_set_temp)
        cache.set(
            cache_key,
            (years_set, documents_totals, data_map),
            settings.STATS_TIMELINE_CACHE_TIMEOUT,
        )

    top_groups = sorted(
        documents_totals.keys(),
        key=lambda c: documents_totals[c],
        reverse=True
    )[:top_n]
    non_top_groups = set(documents_totals.keys()) - set(top_groups)
    other_totals: Dict[int, int] = defaultdict(int)
    other_bin_is_empty = True
    for y in years_set:
        for g in non_top_groups:
            count = int(data_map[y].get(g, 0))
            other_totals[y] += count
            if count > 0:
                other_bin_is_empty = False

    # ── Step 3: Build Chart.js datasets ──
    datasets: List[Dict[str, Any]] = []
    for group in top_groups:
        color = color_from_hash(group)
        datasets.append({
            'label': group,
            'data': [data_map[year].get(group, 0) for year in years_set],
            'borderColor': color,
            'backgroundColor': color + '99',  # 60% opacity fill
            'fill': False,
            'tension': 0.0,
            'pointColor': color,
            'pointBackgroundColor': color,
            'pointRadius': 4,
            'pointHoverRadius': 6,
            'borderWidth': 2,
        })

    if not other_bin_is_empty:
        datasets.append({
            'label': 'Other',
            'data': [other_totals.get(year, 0) for year in years_set],
            'borderColor': 'black',
            'fill': False,
            'tension': 0.0,
            'pointColor': 'black',
            'pointBackgroundColor': 'black',
            'pointRadius': 4,
            'pointHoverRadius': 6,
            'borderWidth': 2,
        })
    return years_set, datasets

def documents_timeline(request: Any, doc_type: str = 'rfc', stats_type: str = 'level') -> Any:
    """Render the documents timeline page with document statistics over time.

    Args:
        request: The HTTP request object.
        doc_type: Type of documents to display.
        stats_type: Field to aggregate by.

    Returns:
        Rendered response for the documents timeline template.
    """
    # Query parameters (from ?key=value)
    try:
        top_n = max(1, min(int(request.GET.get('top', '10')), 100))
    except (ValueError, TypeError):
        top_n = 10
    # Check the top-n value against the allowed choices
    if not check_top_n_choice(top_n):
        return render(request, "stats/error.html", {"message": f"Invalid top_n choice: {top_n}. Valid choices are: {get_top_n_choices()}"})

    if stats_type == 'stream':
        total_labels, total_data_sets = get_timeline_data_for_documents(doc_type, 'stream__name', top_n)
    elif stats_type == 'level' and doc_type == 'draft':
        total_labels, total_data_sets = get_timeline_data_for_documents(doc_type, 'intended_std_level_id', top_n)
    elif stats_type == 'level' and doc_type == 'rfc':
        total_labels, total_data_sets = get_timeline_data_for_documents(doc_type, 'std_level_id', top_n)
    elif stats_type == 'wg':
        total_labels, total_data_sets = get_timeline_data_for_documents(doc_type, 'group__name', top_n)
    else:
        return HttpResponseRedirect(urlreverse("ietf.stats.views.stats_index"))

    chart_data = {
        'labels': total_labels,
        'datasets': total_data_sets,
    }

    # Prepare the list of choice buttons for the template
    possible_docs_types = [
        ("draft", "Drafts", urlreverse(documents_timeline, kwargs={'doc_type': 'draft', 'stats_type': stats_type})),
        ("rfc", "RFC", urlreverse(documents_timeline, kwargs={'doc_type': 'rfc', 'stats_type': stats_type})),
    ]
    possible_stats_types = [
        ("stream", "Streams", urlreverse(documents_timeline, kwargs={'doc_type': doc_type, 'stats_type': 'stream'})),
        ("wg", "Working Groups", urlreverse(documents_timeline, kwargs={'doc_type': doc_type, 'stats_type': 'wg'})),
    ]
    if doc_type == 'draft':
        possible_stats_types.append(("level", "Intended Status", urlreverse(documents_timeline, kwargs={'doc_type': doc_type, 'stats_type': 'level'})))
    elif doc_type == 'rfc':
        possible_stats_types.append(("level", "Category", urlreverse(documents_timeline, kwargs={'doc_type': doc_type, 'stats_type': 'level'})))

    return render(request, "stats/documents_timeline.html", {
        "top_n": top_n,
        "top_n_choices": get_top_n_choices(),
        "objects": "documents",
        "possible_docs_types": possible_docs_types,
        "possible_stats_types": possible_stats_types,
        "total_url": urlreverse(documents_total, kwargs={'doc_type': doc_type, 'stats_type': stats_type}),
        "doc_type": doc_type,
        "stats_type": stats_type,
        "chart_data": chart_data,
    })
