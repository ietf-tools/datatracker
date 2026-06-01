# Copyright The IETF Trust 2016-2026, All Rights Reserved
# -*- coding: utf-8 -*-

from django.conf import settings
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse as urlreverse
from django.core.cache import cache

from collections import defaultdict

import debug                            # pyflakes:ignore

from ietf.doc.models import Document
from ietf.stats.utils import color_from_hash

def get_total_data_for_documents(doc_type = 'rfc', group_by = 'level', top_n = 20):
    # Build a dynamic query set filter
    filters = Q()    
    if doc_type != 'all' and doc_type  != 'wg-draft':
        filters &= Q(type_id=doc_type)
    if doc_type == 'wg-draft':
        filters &= Q(type_id= 'draft')
        filters &= Q(name__startswith='draft-ietf')
    queryset = (
        Document.objects
        .filter(filters)
        .values(group_by)
        .annotate(document_count=Count('id', distinct=True))  # Count as many document authored by this author
        .order_by('-document_count')
    )

    group_count_set = {
        (group, count)
        for group, count in queryset.values_list(group_by, 'document_count')
    }

    group_count_dict = dict()
    for group, count in group_count_set:
        if group is None or group == '':
            group = 'Unspecified'
        group_count_dict[group] = group_count_dict.get(group, 0) + count

    group_count_dict = sorted(group_count_dict.items(), key=lambda x: x[1], reverse=True)
    top_groups = group_count_dict[:top_n]
    other_count = sum(count for _, count in group_count_dict[top_n:])
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

def documents_total(request, doc_type='rfc', stats_type='level'):

    # Query parameters (from ?key=value)
    top_n = int(request.GET.get('top', '10'))

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
        "objects": "documents",
        "possible_docs_types": possible_docs_types,
        "possible_stats_types": possible_stats_types,
        "timeline_url": urlreverse(documents_timeline, kwargs={'doc_type': doc_type, 'stats_type': stats_type}),
        "total_url": urlreverse(documents_total, kwargs={'doc_type': doc_type, 'stats_type': stats_type}),
        "doc_type": doc_type,
        "stats_type": stats_type,
        "chart_data": chart_data,
    })

def get_timeline_data_for_documents(doc_type = 'rfc', group_by = 'stream__name', top_n = 10):
    cache_key = f'stats:get_timeline_data_for_documents:{doc_type}-{group_by}'
    result = cache.get(cache_key, None)
    if result is not None:
        years_set, documents_totals, data_map = result
    else:
        if doc_type != 'all':
            queryset = Document.objects.filter(type_id=doc_type)
        else:
            queryset = Document.objects.all()

    # ── Step 1: Collect all meetings and tickets totals ──
        years_set = set()
        documents_totals = defaultdict(int)
        data_map = defaultdict(dict)  # {year: {stream: count}}

        for row in queryset:
            if not row.pub_date():
                continue
            year = row.pub_date().year
            if group_by == 'stream__name':
                if row.stream is None:
                    group = 'Unspecified'
                else:
                    group = row.stream.name
            elif group_by == 'group__name':
                if row.group is None:
                    group = 'Unspecified'
                else:
                    group = row.group.name
            else:
                group = getattr(row, group_by)
                if group is None:
                    group = 'Unspecified'
            years_set.add(year)
            documents_totals[group] += 1
            data_map[year][group] = data_map[year].get(group, 0) + 1

        # ── Step 2: Sort years numerically rather than alphabetically  ──
        years_set = sorted(years_set)
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
    non_top_groups = documents_totals.keys() - top_groups
    other_totals = defaultdict(int)
    other_bin_is_empty = True
    for y in years_set:
        other_totals[y] = 0
        for g in non_top_groups:
            other_totals[y] += int(data_map[y].get(g, 0))
            if int(data_map[y].get(g, 0)) > 0:
                other_bin_is_empty = False

    # ── Step 4: Build Chart.js datasets ──

    datasets = []
    for group in top_groups:
        color = color_from_hash(group)
        datasets.append({
            'label': group,
            'data': [data_map[year].get(group, 0) for year in years_set],
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

def documents_timeline(request, doc_type='rfc', stats_type='level'):
    """Render the documents timeline page with document statistics over time.

    Args:
        request: The HTTP request object.
        stats_type: Type of statistics.

    Returns:
        Rendered response for the documents timeline template.
    """

    # Query parameters (from ?key=value)
    top_n = int(request.GET.get('top', '10'))

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
        "objects": "documents",
        "possible_docs_types": possible_docs_types,
        "possible_stats_types": possible_stats_types,
        "total_url": urlreverse(documents_total, kwargs={'doc_type': doc_type, 'stats_type': stats_type}),
        "doc_type": doc_type,
        "stats_type": stats_type,
        "chart_data": chart_data,
    })

