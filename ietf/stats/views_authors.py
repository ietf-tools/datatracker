# Copyright The IETF Trust 2016-2026, All Rights Reserved
# -*- coding: utf-8 -*-

from django.conf import settings
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse as urlreverse
from django.core.cache import cache
from collections import defaultdict

import debug                            # pyflakes:ignore

from ietf.doc.models import DocumentAuthor
from ietf.stats.utils import color_from_hash, get_aliased_affiliations, get_aliased_countries

def get_authors_total_data_for_documents(doc_type: str = 'all', group_by: str = 'country', top_n: int = 20) -> dict[str, object]:
    # Build a dynamic query set filter
    filters = Q()    
    if doc_type != 'all' and doc_type  != 'wg-draft':
        filters &= Q(document__type_id=doc_type)
    if doc_type == 'wg-draft':
        filters &= Q(document__type_id= 'draft')
        filters &= Q(document__name__startswith='draft-ietf')
    queryset = (
        DocumentAuthor.objects
        .filter(filters)
        .values(group_by)
        .annotate(author_count=Count('person', distinct=True))  # Count as many document authored by this author
    )

    group_count_set = {
        (group, count)
        for group, count in queryset.values_list(group_by, 'author_count')
    }

    if group_by == 'affiliation':
        alias_map = get_aliased_affiliations(group for group, _ in group_count_set)
    elif group_by == 'country':
        alias_map = get_aliased_countries(group for group, _ in group_count_set)
    else:
        alias_map = {}

    group_count_dict = dict()
    for group, count in group_count_set:
        group = alias_map.get(group, group)
        if group == '':
            group = 'Unspecified'
        group_count_dict[group] = group_count_dict.get(group, 0) + count

    group_count_sorted = sorted(group_count_dict.items(), key=lambda x: x[1], reverse=True)
    top_groups = group_count_sorted[:top_n]
    other_count = sum(count for _, count in group_count_sorted[top_n:])
    if other_count > 0:
        top_groups.append(('Other', other_count))

    labels, data = zip(*top_groups) if top_groups else ([], [])
    chart_data = {
        'labels': labels,
        'datasets': [{
            'data': data,
            'backgroundColor': [color_from_hash(label) if label else '#202020' for label in labels],
            'borderColor': 'black',
            'borderWidth': 1,
        }],
    }

    return chart_data

def authors_total(request: HttpRequest, doc_type: str = 'all', stats_type: str = 'affiliation') -> HttpResponse:

    # Query parameters (from ?key=value)
    try:
        top_n = max(1, min(int(request.GET.get('top', '10')), 100))
    except ValueError:
        top_n = 10

    if stats_type == 'affiliation':
        chart_data = get_authors_total_data_for_documents(doc_type, 'affiliation', top_n)
    elif stats_type == 'country':
        chart_data = get_authors_total_data_for_documents(doc_type, 'country', top_n)
    else:
        return HttpResponseRedirect(urlreverse("ietf.stats.views.stats_index"))

    # Prepare the list of choice buttons for the template
    possible_docs_types = [
        ("all", "All documents", urlreverse(authors_total, kwargs={'doc_type': 'all', 'stats_type': stats_type})),
        ("draft", "Drafts", urlreverse(authors_total, kwargs={'doc_type': 'draft', 'stats_type': stats_type})),
        ("wg-draft", "WG Drafts", urlreverse(authors_total, kwargs={'doc_type': 'wg-draft', 'stats_type': stats_type})),
        ("rfc", "RFCs", urlreverse(authors_total, kwargs={'doc_type': 'rfc', 'stats_type': stats_type})),
    ]
    possible_stats_types = [
        ("affiliation", "Affiliation", urlreverse(authors_total, kwargs={'doc_type': doc_type, 'stats_type': 'affiliation'})),
        ("country", "Country", urlreverse(authors_total, kwargs={'doc_type': doc_type, 'stats_type': 'country'})),
    ]

    return render(request, "stats/documents_total.html", {
        "top_n": top_n,
        "objects": "authors",
        "possible_docs_types": possible_docs_types,
        "possible_stats_types": possible_stats_types,
        "timeline_url": urlreverse(authors_timeline, kwargs={'doc_type': doc_type, 'stats_type': stats_type}),
        "total_url": urlreverse(authors_total, kwargs={'doc_type': doc_type, 'stats_type': stats_type}),
        "doc_type": doc_type,
        "stats_type": stats_type,
        "chart_data": chart_data,
    })


def get_authors_timeline_data_for_documents(doc_type: str = 'all', group_by: str = 'country', top_n: int = 10) -> tuple[list[int], list[dict[str, object]]]:

    cache_key = f'stats:get_authors_timeline_data_for_documents:{doc_type}-{group_by}'
    result = cache.get(cache_key, None)
    if result is not None:
        years_list, documents_totals, data_map = result
    else:
        # Build a dynamic query set filter
        filters = Q()    
        if doc_type != 'all' and doc_type  != 'wg-draft':
            filters &= Q(document__type_id=doc_type)
        if doc_type == 'wg-draft':
            filters &= Q(document__type_id= 'draft')
            filters &= Q(document__name__startswith='draft-ietf')
        queryset = (
            DocumentAuthor.objects
            .select_related('document')
            .filter(filters)
        )

    # ── Step 1: Collect all meetings and tickets totals ──
        years_set = set()
        documents_totals = defaultdict(int)
        data_map = defaultdict(dict)
        year_group_list = [
            (row.document.pub_date().year, getattr(row, group_by))
            for row in queryset
            if row.document.pub_date() is not None
        ]
        if group_by == 'affiliation':
            alias_map = get_aliased_affiliations(group for _, group in year_group_list)
            year_group_list = [(year, alias_map.get(group, group)) for year, group in year_group_list]
        elif group_by == 'country':
            alias_map = get_aliased_countries(group for _, group in year_group_list)
            year_group_list = [(year, alias_map.get(group, group)) for year, group in year_group_list]
        else:
            alias_map = {}
        alias_map[''] = 'Unspecified'

        years_set = {year for year, _ in year_group_list}

        for year, group in year_group_list:
            if group is None or group == '':
                group = 'Unspecified'
            else:
                group = alias_map.get(group, group)
            data_map[year][group] = data_map[year].get(group, 0) + 1
            documents_totals[group] += 1

        # ── Step 2: Sort years numerically rather than alphabetically  ──
        years_list = sorted(years_set)
        cache.set(
            cache_key,
            (years_list, documents_totals, data_map),
            settings.STATS_TIMELINE_CACHE_TIMEOUT,
        )

    # ── Step 3: Get top N and others ── must be outside of the cache
    top_groups = sorted(
        documents_totals.keys(),
        key=lambda c: documents_totals[c],
        reverse=True
    )[:top_n]
    non_top_groups = documents_totals.keys() - set(top_groups)
    other_totals = defaultdict(int)
    for y in years_list:
        other_totals[y] = 0
        for g in non_top_groups:
            other_totals[y] += int(data_map[y].get(g, 0))

    # ── Step 4: Build Chart.js datasets ──

    datasets = []
    for group in top_groups:
        color = color_from_hash(group)
        datasets.append({
            'label': group,
            'data': [data_map[year].get(group, 0) for year in years_list],
            'borderColor': color,
            'backgroundColor': color + '99', # 60% opacity fill
            'fill': False,
            'tension': 0.0,
            'pointColor': color,
            'pointBackgroundColor': color,
            'pointRadius': 4,
            'pointHoverRadius': 6,
            'borderWidth': 2,
        })

    # -- Step 4.bis handle the other --
    datasets.append({
        'label': 'Other',
        'data': [other_totals.get(year, 0) for year in years_list],
        'borderColor': 'black',
        'fill': False,
        'tension': 0.0,
        'pointColor': 'black',
        'pointBackgroundColor': 'black',
        'pointRadius': 4,
        'pointHoverRadius': 6,
        'borderWidth': 2,
    })

    return years_list, datasets


def authors_timeline(request: HttpRequest, doc_type: str = 'all', stats_type: str = 'affiliation') -> HttpResponse:
    """Render the documents timeline page with document statistics over time.

    Args:
        request: The HTTP request object.
        stats_type: Type of statistics.
        top_n: Number of top items to show (for country stats).

    Returns:
        Rendered response for the documents timeline template.
    """

    # Query parameters (from ?key=value)
    try:
        top_n = max(1, min(int(request.GET.get('top', '20')), 100))
    except ValueError:
        top_n = 20

    if stats_type == 'affiliation':
        total_labels, total_data_sets = get_authors_timeline_data_for_documents(doc_type, 'affiliation', top_n)
    elif stats_type == 'country':
        total_labels, total_data_sets = get_authors_timeline_data_for_documents(doc_type, 'country', top_n)
    else:
        return HttpResponseRedirect(urlreverse("ietf.stats.views.stats_index"))

    chart_data = {
        'labels': total_labels,
        'datasets': total_data_sets,
    }

    # Prepare the list of choice buttons for the template
    possible_docs_types = [
        ("all", "All documents", urlreverse(authors_timeline, kwargs={'doc_type': 'all', 'stats_type': stats_type})),
        ("draft", "Drafts", urlreverse(authors_timeline, kwargs={'doc_type': 'draft', 'stats_type': stats_type})),
        ("wg-draft", "WG Drafts", urlreverse(authors_timeline, kwargs={'doc_type': 'wg-draft', 'stats_type': stats_type})),
        ("rfc", "RFCs", urlreverse(authors_timeline, kwargs={'doc_type': 'rfc', 'stats_type': stats_type})),
    ]
    possible_stats_types = [
        ("affiliation", "Affiliation", urlreverse(authors_timeline, kwargs={'doc_type': doc_type, 'stats_type': 'affiliation'})),
        ("country", "Country", urlreverse(authors_timeline, kwargs={'doc_type': doc_type, 'stats_type': 'country'})),
    ]

    return render(request, "stats/documents_timeline.html", {
        "top_n": top_n,
        "objects": "authors",
        "possible_docs_types": possible_docs_types,
        "possible_stats_types": possible_stats_types,
        "timeline_url": urlreverse(authors_timeline, kwargs={'doc_type': doc_type, 'stats_type': stats_type}),
        "total_url": urlreverse(authors_total, kwargs={'doc_type': doc_type, 'stats_type': stats_type}),
        "doc_type": doc_type,
        "stats_type": stats_type,
        "chart_data": chart_data,
    })
