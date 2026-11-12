# Copyright The IETF Trust 2016-2026, All Rights Reserved

from collections import Counter, defaultdict

from django.conf import settings
from django.core.cache import cache
from django.db.models import DateTimeField, OuterRef, Q, Subquery
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse as urlreverse

from ietf.doc.models import DocEvent, DocumentAuthor, RfcAuthor
from ietf.stats.utils import (
    color_from_hash,
    get_aliased_affiliations,
    get_aliased_countries,
    complete_periods,
    get_top_n_choices,
    get_valid_monthly,
    get_valid_top_n,
    period_of,
)
from ietf.utils.timezone import RPC_TZINFO


def _country_not_available_error(request: HttpRequest, doc_type: str) -> HttpResponse | None:
    """Return the country-stat error response (HTTP 400) when the selected doc set cannot provide it."""
    if doc_type in ["all", "rfc"]:
        return render(
            request,
            "stats/error.html",
            {
                "message": f"Country information not (yet) available for {doc_type} documents from the RFC Editor.",
            },
            status=400,
        )
    return None


def _get_document_type_choices(view, doc_type: str, stats_type: str) -> list[tuple[str, str, str]]:
    """Build the document-type navigation choices for each stats view."""
    possible_docs_types = [
        ("draft", "Drafts", urlreverse(view, kwargs={"doc_type": "draft", "stats_type": stats_type})),
        ("wg-draft", "WG Drafts", urlreverse(view, kwargs={"doc_type": "wg-draft", "stats_type": stats_type})),
    ]
    if stats_type != "country":
        possible_docs_types = [
            ("all", "All documents", urlreverse(view, kwargs={"doc_type": "all", "stats_type": stats_type})),
        ] + possible_docs_types + [
            ("rfc", "RFCs", urlreverse(view, kwargs={"doc_type": "rfc", "stats_type": stats_type})),
        ]
    return possible_docs_types


def _get_stats_type_choices(view, doc_type: str, stats_type: str) -> list[tuple[str, str, str]]:
    """Build the stats-type navigation choices for each stats view."""
    possible_stats_types = [
        ("affiliation", "Affiliation", urlreverse(view, kwargs={"doc_type": doc_type, "stats_type": "affiliation"})),
    ]
    if doc_type not in ["all", "rfc"]:
        possible_stats_types.append(
            ("country", "Country", urlreverse(view, kwargs={"doc_type": doc_type, "stats_type": "country"})),
        )
    return possible_stats_types


def _author_key(person_id: int | None, titlepage_name: str) -> object:
    """Return an identity for an author, usable to avoid counting them twice.

    RfcAuthor.person is nullable (authors without a datatracker Person, mostly
    from early RFCs). Such authors are identified by their normalized title-page
    name, which is a best-effort identity: two different people with the same
    name and no Person are assumed to be the same individual.
    """
    if person_id is not None:
        return person_id
    return ("name", titlepage_name.strip().casefold())


def _draft_author_rows(doc_type: str):
    """Return a DocumentAuthor queryset for the draft-based doc_types."""
    filters = Q(document__type_id="draft")
    if doc_type == "wg-draft":
        filters &= Q(document__group__type_id="wg")
    return DocumentAuthor.objects.filter(filters)


def _alias_groups(groups, group_by: str) -> dict:
    """Map raw country/affiliation values to their canonical value."""
    if group_by == "affiliation":
        return get_aliased_affiliations(groups)
    if group_by == "country":
        return get_aliased_countries(groups)
    return {}


def get_authors_total_data_for_documents(doc_type: str = "all",
                                         group_by: str = "country",
                                         top_n: int = 20) -> dict[str, object]:
    """Build chart data for author totals.

    Each author is counted once per group, no matter how many documents they
    have authored, and no matter how many raw spellings of the group they used.

    Args:
        doc_type: Document category to filter on: all, draft, wg-draft, rfc,
        group_by: Field used to group authors, e.g., "country" or "affiliation".
        top_n: Maximum number of top groups to include before aggregating into Other.

    Returns:
        A Chart.js-compatible data dictionary.

    """
    # DocumentAuthor for drafts, RfcAuthor for RFCs; "all" is the union of both.
    # Collect (author identity, raw group) pairs and de-duplicate them in Python:
    # a SQL COUNT() would double count an author present in both models.
    raw_pairs: set[tuple[object, str]] = set()
    if doc_type != "rfc":
        raw_pairs |= set(
            _draft_author_rows(doc_type)
            .values_list("person_id", group_by)
            .distinct()
        )
    if doc_type in ("rfc", "all"):
        for person_id, name, group in (
            RfcAuthor.objects
            .values_list("person_id", "titlepage_name", group_by)
            .distinct()
        ):
            raw_pairs.add((_author_key(person_id, name), group))

    # Alias *before* de-duplicating, so that an author using several spellings
    # of the same organization is only counted once.
    # (not a set: the number of authors using each spelling decides which case variant wins)
    alias_map = _alias_groups([group for _, group in raw_pairs], group_by)
    author_groups = {
        (author, "Unspecified" if not alias_map.get(group, group) else str(alias_map.get(group, group)))
        for author, group in raw_pairs
    }
    group_count_dict: dict[str, int] = dict(Counter(group for _, group in author_groups))

    group_count_sorted = sorted(group_count_dict.items(),
                                key=lambda x: x[1], reverse=True)
    top_groups = group_count_sorted[:top_n]
    other_count = sum(count for _, count in group_count_sorted[top_n:])
    if other_count > 0:
        top_groups.append(("Other", other_count))

    labels, data = zip(*top_groups) if top_groups else ((), ())
    labels_list = list(labels)
    data_list = list(data)
    chart_data: dict[str, object] = {
        "labels": labels_list,
        "datasets": [{
            "data": data_list,
            "backgroundColor": [color_from_hash(label)
                                if label else "#202020"
                                for label in labels_list],
            "borderColor": "black",
            "borderWidth": 1,
        }],
    }

    return chart_data

def authors_total(request: HttpRequest, doc_type: str = "all",
                  stats_type: str = "affiliation") -> HttpResponse:
    """Render total author statistics.

    Args:
        request: The incoming HTTP request.
        doc_type: Document category to filter on.
        stats_type: Grouping type for statistics.

    Returns:
        Rendered response for the total statistics page.

    """
    top_n, error_response = get_valid_top_n(request)

    if error_response is not None:
        return error_response

    if stats_type == "affiliation":
        chart_data = get_authors_total_data_for_documents(doc_type, "affiliation", top_n)
    elif stats_type == "country":
        error_response = _country_not_available_error(request, doc_type)
        if error_response is not None:
            return error_response
        chart_data = get_authors_total_data_for_documents(doc_type, "country", top_n)
    else:
        return HttpResponseRedirect(urlreverse("ietf.stats.views.stats_index"))

    possible_docs_types = _get_document_type_choices(authors_total, doc_type, stats_type)
    possible_stats_types = _get_stats_type_choices(authors_total, doc_type, stats_type)

    return render(request, "stats/documents_total.html", {
        "top_n": top_n,
        "top_n_choices": get_top_n_choices(),
        "objects": "authors",
        "possible_docs_types": possible_docs_types,
        "possible_stats_types": possible_stats_types,
        "timeline_url": urlreverse(authors_timeline, kwargs={"doc_type": doc_type, "stats_type": stats_type}),
        "total_url": urlreverse(authors_total, kwargs={"doc_type": doc_type, "stats_type": stats_type}),
        "doc_type": doc_type,
        "stats_type": stats_type,
        "chart_data": chart_data,
    })


def get_authors_timeline_data_for_documents(doc_type: str = "all", group_by: str = "country", top_n: int = 10,
                                            monthly: bool = False) -> tuple[list[int] | list[str], list[dict[str, object]]]:
    """Build timeline datasets for author statistics.

    Args:
        doc_type: Document category to filter on: all, draft, wg-draft, rfc,
        group_by: Field used to group authors, e.g., "country" or "affiliation".
        top_n: Maximum number of top groups to include before aggregating into Other.
        monthly: Bucket by month ("YYYY-MM" labels) instead of by year.

    Returns:
        A tuple containing the ordered years list and Chart.js datasets.

    """
    cache_key = f"stats:get_authors_timeline_data_for_documents:{doc_type}-{group_by}-{'monthly' if monthly else 'yearly'}"
    result = cache.get(cache_key, None)
    if result is not None:
        years_list, documents_totals, data_map = result
    else:
        # Fetch each document's publication event time in the same query rather
        # than triggering a separate query per row via Document.pub_date().
        new_revision_time = None
        published_rfc_time = None
        if (doc_type in ("draft", "wg-draft")) or (doc_type == "all"):
            new_revision_time = Subquery(
                DocEvent.objects
                .filter(doc=OuterRef("document_id"), type="new_revision")
                .order_by("-time", "-id")
                .values("time")[:1],
                output_field=DateTimeField(),
            )
        if (doc_type == "rfc") or (doc_type == "all"):
            published_rfc_time = Subquery(
                DocEvent.objects
                .filter(doc=OuterRef("document_id"), type="published_rfc")
                .order_by("-time", "-id")
                .values("time")[:1],
                output_field=DateTimeField(),
            )

        # DocumentAuthor for drafts, RfcAuthor for RFCs; "all" is both.
        # Collect (year, author identity, raw group) so that an author is counted
        # only once per year and group (e.g., a draft and its RFC in the same
        # year do not count twice), consistently with the totals view.
        raw_rows: set[tuple[int | str, object, str]] = set()
        if doc_type != "rfc":
            for person_id, group, pub_datetime in (
                _draft_author_rows(doc_type)
                .annotate(pub_datetime=new_revision_time)
                .values_list("person_id", group_by, "pub_datetime")
            ):
                if pub_datetime is not None:
                    raw_rows.add((period_of(pub_datetime.astimezone(RPC_TZINFO), monthly), person_id, group))
        if doc_type in ("rfc", "all"):
            for person_id, name, group, pub_datetime in (
                RfcAuthor.objects
                .annotate(pub_datetime=published_rfc_time)
                .values_list("person_id", "titlepage_name", group_by, "pub_datetime")
            ):
                if pub_datetime is not None:
                    raw_rows.add((
                        period_of(pub_datetime.astimezone(RPC_TZINFO), monthly),
                        _author_key(person_id, name),
                        group,
                    ))

    # ── Step 1: Alias the groups, then de-duplicate authors per year and group ──
        years_set = set()
        documents_totals = defaultdict(int)
        data_map = defaultdict(dict)

        # (not a set: the number of rows using each spelling decides which case variant wins)
        alias_map = _alias_groups([group for _, _, group in raw_rows], group_by)
        # Let us define a value when there is none...
        alias_map[""] = "Unspecified"
        year_author_groups = {
            (year, author, alias_map.get(group, group))
            for year, author, group in raw_rows
        }

        years_set = {year for year, _, _ in year_author_groups}

        for year, _, aliased_group in year_author_groups:
            data_map[year][aliased_group] = data_map[year].get(aliased_group, 0) + 1
            documents_totals[aliased_group] += 1

        # ── Step 2: Sort periods chronologically (and fill the gaps when monthly) ──
        years_list = complete_periods(years_set, monthly)
        cache.set(
            cache_key,
            (years_list, documents_totals, data_map),
            settings.STATS_TIMELINE_CACHE_TIMEOUT,
        )

    # ── Step 3: Get top N and others ── must be outside of the cache
    top_groups = sorted(
        documents_totals.keys(),
        key=lambda c: documents_totals[c],
        reverse=True,
    )[:top_n]
    non_top_groups = documents_totals.keys() - set(top_groups)
    other_totals: dict[int | str, int] = defaultdict(int)
    other_bin_is_empty = True
    for y in years_list:
        for g in non_top_groups:
            count = int(data_map.get(y, {}).get(g, 0))
            other_totals[y] += count
            if count > 0:
                other_bin_is_empty = False

    # ── Step 4: Build Chart.js datasets ──

    datasets = []
    for group in top_groups:
        color = color_from_hash(group)
        datasets.append({
            "label": group,
            "data": [data_map.get(year, {}).get(group, 0) for year in years_list],
            "borderColor": color,
            "backgroundColor": color + "99", # 60% opacity fill
            "fill": False,
            "tension": 0.0,
            "pointColor": color,
            "pointBackgroundColor": color,
            "pointRadius": 4,
            "pointHoverRadius": 6,
            "borderWidth": 2,
        })

    # -- Step 4.bis handle the other --
    if not other_bin_is_empty:
        datasets.append({
            "label": "Other",
            "data": [other_totals.get(year, 0) for year in years_list],
            "borderColor": "black",
            "fill": False,
            "tension": 0.0,
            "pointColor": "black",
            "pointBackgroundColor": "black",
            "pointRadius": 4,
            "pointHoverRadius": 6,
            "borderWidth": 2,
        })

    return years_list, datasets


def authors_timeline(request: HttpRequest, doc_type: str = "all", stats_type: str = "affiliation") -> HttpResponse:
    """Render author timeline statistics.

    Args:
        request: The incoming HTTP request.
        doc_type: Document category to filter on.
        stats_type: Grouping type for statistics.

    Returns:
        Rendered response for the timeline statistics page.

    """
    top_n, error_response = get_valid_top_n(request)

    if error_response is not None:
        return error_response

    monthly, error_response = get_valid_monthly(request)

    if error_response is not None:
        return error_response

    if stats_type == "affiliation":
        total_labels, total_data_sets = get_authors_timeline_data_for_documents(doc_type, "affiliation", top_n, monthly)
    elif stats_type == "country":
        error_response = _country_not_available_error(request, doc_type)
        if error_response is not None:
            return error_response
        total_labels, total_data_sets = get_authors_timeline_data_for_documents(doc_type, "country", top_n, monthly)
    else:
        return HttpResponseRedirect(urlreverse("ietf.stats.views.stats_index"))

    chart_data = {
        "labels": total_labels,
        "datasets": total_data_sets,
    }

    possible_docs_types = _get_document_type_choices(authors_timeline, doc_type, stats_type)
    possible_stats_types = _get_stats_type_choices(authors_timeline, doc_type, stats_type)

    return render(request, "stats/documents_timeline.html", {
        "top_n": top_n,
        "monthly": monthly,
        "top_n_choices": get_top_n_choices(),
        "objects": "authors",
        "possible_docs_types": possible_docs_types,
        "possible_stats_types": possible_stats_types,
        "timeline_url": urlreverse(authors_timeline, kwargs={"doc_type": doc_type, "stats_type": stats_type}),
        "total_url": urlreverse(authors_total, kwargs={"doc_type": doc_type, "stats_type": stats_type}),
        "doc_type": doc_type,
        "stats_type": stats_type,
        "chart_data": chart_data,
    })
