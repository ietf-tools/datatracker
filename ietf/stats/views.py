# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import os
import calendar
import datetime
import email.utils
import itertools
import json
import dateutil.relativedelta
from collections import defaultdict

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse as urlreverse
from django.utils.safestring import mark_safe
from django.utils.text import slugify

import debug                            # pyflakes:ignore

from ietf.review.utils import (extract_review_assignment_data,
                               aggregate_raw_period_review_assignment_stats,
                               ReviewAssignmentData,
                               sum_period_review_assignment_stats,
                               sum_raw_review_assignment_aggregations)
from ietf.submit.models import Submission
from ietf.group.models import Role, Group
from ietf.person.models import Person
from ietf.name.models import ReviewResultName, CountryName, DocRelationshipName, ReviewAssignmentStateName
from ietf.person.name import plain_name
from ietf.doc.models import DocAlias, Document, State, DocEvent
from ietf.meeting.models import Meeting
from ietf.stats.models import MeetingRegistration, CountryAlias
from ietf.stats.utils import get_aliased_affiliations, get_aliased_countries, compute_hirsch_index
from ietf.ietfauth.utils import has_role
from ietf.utils.log import log
from ietf.utils.response import permission_denied

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
    def build_document_stats_url(stats_type_override=Ellipsis, get_overrides={}):
        kwargs = {
            "stats_type": stats_type if stats_type_override is Ellipsis else stats_type_override,
        }

        return urlreverse(document_stats, kwargs={ k: v for k, v in kwargs.items() if v is not None }) + generate_query_string(request.GET, get_overrides)

    # the length limitation is to keep the key shorter than memcached's limit
    # of 250 after django has added the key_prefix and key_version parameters
    cache_key = ("stats:document_stats:%s:%s" % (stats_type, slugify(request.META.get('QUERY_STRING',''))))[:228]
    data = cache.get(cache_key)
    if not data:
        names_limit = settings.STATS_NAMES_LIMIT
        # statistics types
        possible_document_stats_types = add_url_to_choices([
            ("authors", "Number of authors"),
            ("pages", "Pages"),
            ("words", "Words"),
            ("format", "Format"),
            ("formlang", "Formal languages"),
        ], lambda slug: build_document_stats_url(stats_type_override=slug))

        possible_author_stats_types = add_url_to_choices([
            ("author/documents", "Number of documents"),
            ("author/affiliation", "Affiliation"),
            ("author/country", "Country"),
            ("author/continent", "Continent"),
            ("author/citations", "Citations"),
            ("author/hindex", "h-index"),
        ], lambda slug: build_document_stats_url(stats_type_override=slug))

        possible_yearly_stats_types = add_url_to_choices([
            ("yearly/affiliation", "Affiliation"),
            ("yearly/country", "Country"),
            ("yearly/continent", "Continent"),
        ], lambda slug: build_document_stats_url(stats_type_override=slug))


        if not stats_type:
            return HttpResponseRedirect(build_document_stats_url(stats_type_override=possible_document_stats_types[0][0]))


        possible_document_types = add_url_to_choices([
            ("", "All"),
            ("rfc", "RFCs"),
            ("draft", "Drafts"),
        ], lambda slug: build_document_stats_url(get_overrides={ "type": slug }))

        document_type = get_choice(request, "type", possible_document_types) or ""


        possible_time_choices = add_url_to_choices([
            ("", "All time"),
            ("5y", "Past 5 years"),
        ], lambda slug: build_document_stats_url(get_overrides={ "time": slug }))

        time_choice = request.GET.get("time") or ""

        from_time = None
        if "y" in time_choice:
            try:
                y = int(time_choice.rstrip("y"))
                from_time = datetime.datetime.today() - dateutil.relativedelta.relativedelta(years=y)
            except ValueError:
                pass

        chart_data = []
        table_data = []
        stats_title = ""
        template_name = stats_type.replace("/", "_")
        bin_size = 1
        alias_data = []
        eu_countries = None


        if any(stats_type == t[0] for t in possible_document_stats_types):
            # filter documents
            docalias_filters = Q(docs__type="draft")

            rfc_state = State.objects.get(type="draft", slug="rfc")
            if document_type == "rfc":
                docalias_filters &= Q(docs__states=rfc_state)
            elif document_type == "draft":
                docalias_filters &= ~Q(docs__states=rfc_state)

            if from_time:
                # this is actually faster than joining in the database,
                # despite the round-trip back and forth
                docs_within_time_constraint = list(Document.objects.filter(
                    type="draft",
                    docevent__time__gte=from_time,
                    docevent__type__in=["published_rfc", "new_revision"],
                ).values_list("pk"))

                docalias_filters &= Q(docs__in=docs_within_time_constraint)

            docalias_qs = DocAlias.objects.filter(docalias_filters)

            if document_type == "rfc":
                doc_label = "RFC"
            elif document_type == "draft":
                doc_label = "draft"
            else:
                doc_label = "document"

            total_docs = docalias_qs.values_list("docs__name").distinct().count()

            def generate_canonical_names(values):
                for doc_id, ts in itertools.groupby(values.order_by("docs__name"), lambda a: a[0]):
                    chosen = None
                    for t in ts:
                        if chosen is None:
                            chosen = t
                        else:
                            if t[1].startswith("rfc"):
                                chosen = t
                            elif t[1].startswith("draft") and not chosen[1].startswith("rfc"):
                                chosen = t
                    yield chosen

            if stats_type == "authors":
                stats_title = "Number of authors for each {}".format(doc_label)

                bins = defaultdict(set)

                for name, canonical_name, author_count in generate_canonical_names(docalias_qs.values_list("docs__name", "name").annotate(Count("docs__documentauthor"))):
                    bins[author_count or 0].add(canonical_name)

                series_data = []
                for author_count, names in sorted(bins.items(), key=lambda t: t[0]):
                    percentage = len(names) * 100.0 / (total_docs or 1)
                    series_data.append((author_count, percentage))
                    table_data.append((author_count, percentage, len(names), list(names)[:names_limit]))

                chart_data.append({ "data": series_data })

            elif stats_type == "pages":
                stats_title = "Number of pages for each {}".format(doc_label)

                bins = defaultdict(set)

                for name, canonical_name, pages in generate_canonical_names(docalias_qs.values_list("docs__name", "name", "docs__pages")):
                    bins[pages or 0].add(canonical_name)

                series_data = []
                for pages, names in sorted(bins.items(), key=lambda t: t[0]):
                    percentage = len(names) * 100.0 / (total_docs or 1)
                    if pages is not None:
                        series_data.append((pages, len(names)))
                        table_data.append((pages, percentage, len(names), list(names)[:names_limit]))

                chart_data.append({ "data": series_data })

            elif stats_type == "words":
                stats_title = "Number of words for each {}".format(doc_label)

                bin_size = 500

                bins = defaultdict(set)

                for name, canonical_name, words in generate_canonical_names(docalias_qs.values_list("docs__name", "name", "docs__words")):
                    bins[put_into_bin(words, bin_size)].add(canonical_name)

                series_data = []
                for (value, words), names in sorted(bins.items(), key=lambda t: t[0][0]):
                    percentage = len(names) * 100.0 / (total_docs or 1)
                    if words is not None:
                        series_data.append((value, len(names)))

                    table_data.append((words, percentage, len(names), list(names)[:names_limit]))

                chart_data.append({ "data": series_data })

            elif stats_type == "format":
                stats_title = "Submission formats for each {}".format(doc_label)

                bins = defaultdict(set)

                # on new documents, we should have a Submission row with the file types
                submission_types = {}

                for doc_name, file_types in Submission.objects.values_list("draft", "file_types").order_by("submission_date", "id"):
                    submission_types[doc_name] = file_types

                doc_names_with_missing_types = {}
                for doc_name, canonical_name, rev in generate_canonical_names(docalias_qs.values_list("docs__name", "name", "docs__rev")):
                    types = submission_types.get(doc_name)
                    if types:
                        for dot_ext in types.split(","):
                            bins[dot_ext.lstrip(".").upper()].add(canonical_name)

                    else:

                        if canonical_name.startswith("rfc"):
                            filename = canonical_name
                        else:
                            filename = canonical_name + "-" + rev

                        doc_names_with_missing_types[filename] = canonical_name

                # look up the remaining documents on disk
                for filename in itertools.chain(os.listdir(settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR), os.listdir(settings.RFC_PATH)):
                    t = filename.split(".", 1)
                    if len(t) != 2:
                        continue

                    basename, ext = t
                    ext = ext.lower()
                    if not any(ext==whitelisted_ext for whitelisted_ext in settings.DOCUMENT_FORMAT_WHITELIST):
                        continue

                    canonical_name = doc_names_with_missing_types.get(basename)

                    if canonical_name:
                        bins[ext.upper()].add(canonical_name)

                series_data = []
                for fmt, names in sorted(bins.items(), key=lambda t: t[0]):
                    percentage = len(names) * 100.0 / (total_docs or 1)
                    series_data.append((fmt, len(names)))

                    table_data.append((fmt, percentage, len(names), list(names)[:names_limit]))

                chart_data.append({ "data": series_data })

            elif stats_type == "formlang":
                stats_title = "Formal languages used for each {}".format(doc_label)

                bins = defaultdict(set)

                for name, canonical_name, formal_language_name in generate_canonical_names(docalias_qs.values_list("docs__name", "name", "docs__formal_languages__name")):
                    bins[formal_language_name or ""].add(canonical_name)

                series_data = []
                for formal_language, names in sorted(bins.items(), key=lambda t: t[0]):
                    percentage = len(names) * 100.0 / (total_docs or 1)
                    if formal_language is not None:
                        series_data.append((formal_language, len(names)))
                        table_data.append((formal_language, percentage, len(names), list(names)[:names_limit]))

                chart_data.append({ "data": series_data })

        elif any(stats_type == t[0] for t in possible_author_stats_types):
            person_filters = Q(documentauthor__document__type="draft")

            # filter persons
            rfc_state = State.objects.get(type="draft", slug="rfc")
            if document_type == "rfc":
                person_filters &= Q(documentauthor__document__states=rfc_state)
            elif document_type == "draft":
                person_filters &= ~Q(documentauthor__document__states=rfc_state)

            if from_time:
                # this is actually faster than joining in the database,
                # despite the round-trip back and forth
                docs_within_time_constraint = set(Document.objects.filter(
                    type="draft",
                    docevent__time__gte=from_time,
                    docevent__type__in=["published_rfc", "new_revision"],
                ).values_list("pk"))

                person_filters &= Q(documentauthor__document__in=docs_within_time_constraint)

            person_qs = Person.objects.filter(person_filters)

            if document_type == "rfc":
                doc_label = "RFC"
            elif document_type == "draft":
                doc_label = "draft"
            else:
                doc_label = "document"

            if stats_type == "author/documents":
                stats_title = "Number of {}s per author".format(doc_label)

                bins = defaultdict(set)

                person_qs = Person.objects.filter(person_filters)

                for name, document_count in person_qs.values_list("name").annotate(Count("documentauthor")):
                    bins[document_count or 0].add(name)

                total_persons = count_bins(bins)

                series_data = []
                for document_count, names in sorted(bins.items(), key=lambda t: t[0]):
                    percentage = len(names) * 100.0 / (total_persons or 1)
                    series_data.append((document_count, percentage))
                    plain_names = sorted([ plain_name(n) for n in names ])
                    table_data.append((document_count, percentage, len(plain_names), list(plain_names)[:names_limit]))

                chart_data.append({ "data": series_data })

            elif stats_type == "author/affiliation":
                stats_title = "Number of {} authors per affiliation".format(doc_label)

                bins = defaultdict(set)

                person_qs = Person.objects.filter(person_filters)

                # Since people don't write the affiliation names in the
                # same way, and we don't want to go back and edit them
                # either, we transform them here.

                name_affiliation_set = {
                    (name, affiliation)
                    for name, affiliation in person_qs.values_list("name", "documentauthor__affiliation")
                }

                aliases = get_aliased_affiliations(affiliation for _, affiliation in name_affiliation_set)

                for name, affiliation in name_affiliation_set:
                    bins[aliases.get(affiliation, affiliation)].add(name)

                prune_unknown_bin_with_known(bins)
                total_persons = count_bins(bins)

                series_data = []
                for affiliation, names in sorted(bins.items(), key=lambda t: t[0].lower()):
                    percentage = len(names) * 100.0 / (total_persons or 1)
                    if affiliation:
                        series_data.append((affiliation, len(names)))
                    plain_names = sorted([ plain_name(n) for n in names ])
                    table_data.append((affiliation, percentage, len(plain_names), list(plain_names)[:names_limit]))

                series_data.sort(key=lambda t: t[1], reverse=True)
                series_data = series_data[:30]

                chart_data.append({ "data": series_data })

                for alias, name in sorted(aliases.items(), key=lambda t: t[1]):
                    alias_data.append((name, alias))

            elif stats_type == "author/country":
                stats_title = "Number of {} authors per country".format(doc_label)

                bins = defaultdict(set)

                person_qs = Person.objects.filter(person_filters)

                # Since people don't write the country names in the
                # same way, and we don't want to go back and edit them
                # either, we transform them here.

                name_country_set = {
                    (name, country)
                    for name, country in person_qs.values_list("name", "documentauthor__country")
                }

                aliases = get_aliased_countries(country for _, country in name_country_set)

                countries = { c.name: c for c in CountryName.objects.all() }
                eu_name = "EU"
                eu_countries = { c for c in countries.values() if c.in_eu }

                for name, country in name_country_set:
                    country_name = aliases.get(country, country)
                    bins[country_name].add(name)

                    c = countries.get(country_name)
                    if c and c.in_eu:
                        bins[eu_name].add(name)

                prune_unknown_bin_with_known(bins)
                total_persons = count_bins(bins)

                series_data = []
                for country, names in sorted(bins.items(), key=lambda t: t[0].lower()):
                    percentage = len(names) * 100.0 / (total_persons or 1)
                    if country:
                        series_data.append((country, len(names)))
                    plain_names = sorted([ plain_name(n) for n in names ])
                    table_data.append((country, percentage, len(plain_names), list(plain_names)[:names_limit]))

                series_data.sort(key=lambda t: t[1], reverse=True)
                series_data = series_data[:30]

                chart_data.append({ "data": series_data })

                for alias, country_name in aliases.items():
                    alias_data.append((country_name, alias, countries.get(country_name)))

                alias_data.sort()

            elif stats_type == "author/continent":
                stats_title = "Number of {} authors per continent".format(doc_label)

                bins = defaultdict(set)

                person_qs = Person.objects.filter(person_filters)

                name_country_set = {
                    (name, country)
                    for name, country in person_qs.values_list("name", "documentauthor__country")
                }

                aliases = get_aliased_countries(country for _, country in name_country_set)

                country_to_continent = dict(CountryName.objects.values_list("name", "continent__name"))

                for name, country in name_country_set:
                    country_name = aliases.get(country, country)
                    continent_name = country_to_continent.get(country_name, "")
                    bins[continent_name].add(name)

                prune_unknown_bin_with_known(bins)
                total_persons = count_bins(bins)

                series_data = []
                for continent, names in sorted(bins.items(), key=lambda t: t[0].lower()):
                    percentage = len(names) * 100.0 / (total_persons or 1)
                    if continent:
                        series_data.append((continent, len(names)))
                    plain_names = sorted([ plain_name(n) for n in names ])
                    table_data.append((continent, percentage, len(plain_names), list(plain_names)[:names_limit]))

                series_data.sort(key=lambda t: t[1], reverse=True)

                chart_data.append({ "data": series_data })

            elif stats_type == "author/citations":
                stats_title = "Number of citations of {}s written by author".format(doc_label)

                bins = defaultdict(set)

                cite_relationships = list(DocRelationshipName.objects.filter(slug__in=['refnorm', 'refinfo', 'refunk', 'refold']))
                person_filters &= Q(documentauthor__document__docalias__relateddocument__relationship__in=cite_relationships)

                person_qs = Person.objects.filter(person_filters)

                for name, citations in person_qs.values_list("name").annotate(Count("documentauthor__document__docalias__relateddocument")):
                    bins[citations or 0].add(name)

                total_persons = count_bins(bins)

                series_data = []
                for citations, names in sorted(bins.items(), key=lambda t: t[0], reverse=True):
                    percentage = len(names) * 100.0 / (total_persons or 1)
                    series_data.append((citations, percentage))
                    plain_names = sorted([ plain_name(n) for n in names ])
                    table_data.append((citations, percentage, len(plain_names), list(plain_names)[:names_limit]))

                chart_data.append({ "data": sorted(series_data, key=lambda t: t[0]) })

            elif stats_type == "author/hindex":
                stats_title = "h-index for {}s written by author".format(doc_label)

                bins = defaultdict(set)

                cite_relationships = list(DocRelationshipName.objects.filter(slug__in=['refnorm', 'refinfo', 'refunk', 'refold']))
                person_filters &= Q(documentauthor__document__docalias__relateddocument__relationship__in=cite_relationships)

                person_qs = Person.objects.filter(person_filters)

                values = person_qs.values_list("name", "documentauthor__document").annotate(Count("documentauthor__document__docalias__relateddocument"))
                for name, ts in itertools.groupby(values.order_by("name"), key=lambda t: t[0]):
                    h_index = compute_hirsch_index([citations for _, document, citations in ts])
                    bins[h_index or 0].add(name)

                total_persons = count_bins(bins)

                series_data = []
                for citations, names in sorted(bins.items(), key=lambda t: t[0], reverse=True):
                    percentage = len(names) * 100.0 / (total_persons or 1)
                    series_data.append((citations, percentage))
                    plain_names = sorted([ plain_name(n) for n in names ])
                    table_data.append((citations, percentage, len(plain_names), list(plain_names)[:names_limit]))

                chart_data.append({ "data": sorted(series_data, key=lambda t: t[0]) })

        elif any(stats_type == t[0] for t in possible_yearly_stats_types):

            person_filters = Q(documentauthor__document__type="draft")

            # filter persons
            rfc_state = State.objects.get(type="draft", slug="rfc")
            if document_type == "rfc":
                person_filters &= Q(documentauthor__document__states=rfc_state)
            elif document_type == "draft":
                person_filters &= ~Q(documentauthor__document__states=rfc_state)

            doc_years = defaultdict(set)

            docevent_qs = DocEvent.objects.filter(
                doc__type="draft",
                type__in=["published_rfc", "new_revision"],
            ).values_list("doc", "time").order_by("doc")

            for doc, time in docevent_qs.iterator():
                doc_years[doc].add(time.year)

            person_qs = Person.objects.filter(person_filters)

            if document_type == "rfc":
                doc_label = "RFC"
            elif document_type == "draft":
                doc_label = "draft"
            else:
                doc_label = "document"

            template_name = "yearly"

            years_from = from_time.year if from_time else 1
            years_to = datetime.date.today().year - 1


            if stats_type == "yearly/affiliation":
                stats_title = "Number of {} authors per affiliation over the years".format(doc_label)

                person_qs = Person.objects.filter(person_filters)

                name_affiliation_doc_set = {
                    (name, affiliation, doc)
                    for name, affiliation, doc in person_qs.values_list("name", "documentauthor__affiliation", "documentauthor__document")
                }

                aliases = get_aliased_affiliations(affiliation for _, affiliation, _ in name_affiliation_doc_set)

                bins = defaultdict(set)
                for name, affiliation, doc in name_affiliation_doc_set:
                    a = aliases.get(affiliation, affiliation)
                    if a:
                        for year in doc_years.get(doc):
                            if years_from <= year <= years_to:
                                bins[(year, a)].add(name)

                add_labeled_top_series_from_bins(chart_data, bins, limit=8)

            elif stats_type == "yearly/country":
                stats_title = "Number of {} authors per country over the years".format(doc_label)

                person_qs = Person.objects.filter(person_filters)

                name_country_doc_set = {
                    (name, country, doc)
                    for name, country, doc in person_qs.values_list("name", "documentauthor__country", "documentauthor__document")
                }

                aliases = get_aliased_countries(country for _, country, _ in name_country_doc_set)

                countries = { c.name: c for c in CountryName.objects.all() }
                eu_name = "EU"
                eu_countries = { c for c in countries.values() if c.in_eu }

                bins = defaultdict(set)

                for name, country, doc in name_country_doc_set:
                    country_name = aliases.get(country, country)
                    c = countries.get(country_name)

                    years = doc_years.get(doc)
                    if country_name and years:
                        for year in years:
                            if years_from <= year <= years_to:
                                bins[(year, country_name)].add(name)

                                if c and c.in_eu:
                                    bins[(year, eu_name)].add(name)

                add_labeled_top_series_from_bins(chart_data, bins, limit=8)


            elif stats_type == "yearly/continent":
                stats_title = "Number of {} authors per continent".format(doc_label)

                person_qs = Person.objects.filter(person_filters)

                name_country_doc_set = {
                    (name, country, doc)
                    for name, country, doc in person_qs.values_list("name", "documentauthor__country", "documentauthor__document")
                }

                aliases = get_aliased_countries(country for _, country, _ in name_country_doc_set)

                country_to_continent = dict(CountryName.objects.values_list("name", "continent__name"))

                bins = defaultdict(set)

                for name, country, doc in name_country_doc_set:
                    country_name = aliases.get(country, country)
                    continent_name = country_to_continent.get(country_name, "")

                    if continent_name:
                        for year in doc_years.get(doc):
                            if years_from <= year <= years_to:
                                bins[(year, continent_name)].add(name)

                add_labeled_top_series_from_bins(chart_data, bins, limit=8)

        data = {
            "chart_data": mark_safe(json.dumps(chart_data)),
            "table_data": table_data,
            "stats_title": stats_title,
            "possible_document_stats_types": possible_document_stats_types,
            "possible_author_stats_types": possible_author_stats_types,
            "possible_yearly_stats_types": possible_yearly_stats_types,
            "stats_type": stats_type,
            "possible_document_types": possible_document_types,
            "document_type": document_type,
            "possible_time_choices": possible_time_choices,
            "time_choice": time_choice,
            "doc_label": doc_label,
            "bin_size": bin_size,
            "show_aliases_url": build_document_stats_url(get_overrides={ "showaliases": "1" }),
            "hide_aliases_url": build_document_stats_url(get_overrides={ "showaliases": None }),
            "alias_data": alias_data,
            "eu_countries": sorted(eu_countries or [], key=lambda c: c.name),
            "content_template": "stats/document_stats_{}.html".format(template_name),
        }
        log("Cache miss for '%s'.  Data size: %sk" % (cache_key, len(str(data))/1000))
        cache.set(cache_key, data, 24*60*60)
    return render(request, "stats/document_stats.html", data)

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
    meeting = None
    if num is not None:
        meeting = get_object_or_404(Meeting, number=num, type="ietf")

    def build_meeting_stats_url(number=None, stats_type_override=Ellipsis, get_overrides={}):
        kwargs = {
            "stats_type": stats_type if stats_type_override is Ellipsis else stats_type_override,
        }

        if number is not None:
            kwargs["num"] = number

        return urlreverse(meeting_stats, kwargs={ k: v for k, v in kwargs.items() if v is not None }) + generate_query_string(request.GET, get_overrides)

    cache_key = ("stats:meeting_stats:%s:%s:%s" % (num, stats_type, slugify(request.META.get('QUERY_STRING',''))))[:228]
    data = cache.get(cache_key)
    if not data:
        names_limit = settings.STATS_NAMES_LIMIT
        # statistics types
        if meeting:
            possible_stats_types = add_url_to_choices([
                ("country", "Country"),
                ("continent", "Continent"),
            ], lambda slug: build_meeting_stats_url(number=meeting.number, stats_type_override=slug))
        else:
            possible_stats_types = add_url_to_choices([
                ("overview", "Overview"),
                ("country", "Country"),
                ("continent", "Continent"),
            ], lambda slug: build_meeting_stats_url(number=None, stats_type_override=slug))

        if not stats_type:
            return HttpResponseRedirect(build_meeting_stats_url(number=num, stats_type_override=possible_stats_types[0][0]))

        chart_data = []
        piechart_data = []
        table_data = []
        stats_title = ""
        template_name = stats_type
        bin_size = 1
        eu_countries = None

        def get_country_mapping(attendees):
            return {
                alias.alias: alias.country
                for alias in CountryAlias.objects.filter(alias__in=set(r.country_code for r in attendees)).select_related("country", "country__continent")
                if alias.alias.isupper()
            }

        def reg_name(r):
            return email.utils.formataddr(((r.first_name + " " + r.last_name).strip(), r.email))

        if meeting and any(stats_type == t[0] for t in possible_stats_types):
            attendees = MeetingRegistration.objects.filter(meeting=meeting, attended=True)

            if stats_type == "country":
                stats_title = "Number of attendees for {} {} per country".format(meeting.type.name, meeting.number)

                bins = defaultdict(set)

                country_mapping = get_country_mapping(attendees)

                eu_name = "EU"
                eu_countries = set(CountryName.objects.filter(in_eu=True))

                for r in attendees:
                    name = reg_name(r)
                    c = country_mapping.get(r.country_code)
                    bins[c.name if c else ""].add(name)

                    if c and c.in_eu:
                        bins[eu_name].add(name)

                prune_unknown_bin_with_known(bins)
                total_attendees = count_bins(bins)

                series_data = []
                for country, names in sorted(bins.items(), key=lambda t: t[0].lower()):
                    percentage = len(names) * 100.0 / (total_attendees or 1)
                    if country:
                        series_data.append((country, len(names)))
                    table_data.append((country, percentage, len(names), list(names)[:names_limit]))

                    if country and country != eu_name:
                        piechart_data.append({ "name": country, "y": percentage })

                series_data.sort(key=lambda t: t[1], reverse=True)
                series_data = series_data[:20]

                piechart_data.sort(key=lambda d: d["y"], reverse=True)
                pie_cut_off = 8
                piechart_data = piechart_data[:pie_cut_off] + [{ "name": "Other", "y": sum(d["y"] for d in piechart_data[pie_cut_off:])}]

                chart_data.append({ "data": series_data })

            elif stats_type == "continent":
                stats_title = "Number of attendees for {} {} per continent".format(meeting.type.name, meeting.number)

                bins = defaultdict(set)

                country_mapping = get_country_mapping(attendees)

                for r in attendees:
                    name = reg_name(r)
                    c = country_mapping.get(r.country_code)
                    bins[c.continent.name if c else ""].add(name)

                prune_unknown_bin_with_known(bins)
                total_attendees = count_bins(bins)

                series_data = []
                for continent, names in sorted(bins.items(), key=lambda t: t[0].lower()):
                    percentage = len(names) * 100.0 / (total_attendees or 1)
                    if continent:
                        series_data.append((continent, len(names)))
                    table_data.append((continent, percentage, len(names), list(names)[:names_limit]))

                series_data.sort(key=lambda t: t[1], reverse=True)

                chart_data.append({ "data": series_data })


        elif not meeting and any(stats_type == t[0] for t in possible_stats_types):
            template_name = "overview"

            attendees = MeetingRegistration.objects.filter(meeting__type="ietf", attended=True).select_related('meeting')

            if stats_type == "overview":
                stats_title = "Number of attendees per meeting"

                continents = {}
                
                meetings = Meeting.objects.filter(type='ietf', date__lte=datetime.date.today()).order_by('number')
                for m in meetings:
                    country = CountryName.objects.get(slug=m.country)
                    continents[country.continent.name] = country.continent.name

                bins = defaultdict(set)

                for r in attendees:
                    meeting_number = int(r.meeting.number)
                    name = reg_name(r)
                    bins[meeting_number].add(name)

                series_data = {}
                for continent in list(continents.keys()):
                    series_data[continent] = []

                for m in meetings:
                    country = CountryName.objects.get(slug=m.country)
                    url = build_meeting_stats_url(number=m.number,
                                                  stats_type_override="country")
                    for continent in list(continents.keys()):
                        if continent == country.continent.name:
                            d = {
                                "name": "IETF {} - {}, {}".format(int(m.number), m.city, country),
                                "x": int(m.number),
                                "y": m.attendees,
                                "date": m.date.strftime("%d %b %Y"),
                                "url": url,
                                }
                        else:
                            d = {
                                "x": int(m.number),
                                "y": 0,
                                }
                        series_data[continent].append(d)
                    table_data.append((m, url,
                                       m.attendees, country))

                for continent in list(continents.keys()):
#                    series_data[continent].sort(key=lambda t: t[0]["x"])
                    chart_data.append( { "name": continent,
                                         "data": series_data[continent] })
                    
                table_data.sort(key=lambda t: int(t[0].number), reverse=True)

            elif stats_type == "country":
                stats_title = "Number of attendees per country across meetings"

                country_mapping = get_country_mapping(attendees)

                eu_name = "EU"
                eu_countries = set(CountryName.objects.filter(in_eu=True))

                bins = defaultdict(set)

                for r in attendees:
                    meeting_number = int(r.meeting.number)
                    name = reg_name(r)
                    c = country_mapping.get(r.country_code)

                    if c:
                        bins[(meeting_number, c.name)].add(name)
                        if c.in_eu:
                            bins[(meeting_number, eu_name)].add(name)

                add_labeled_top_series_from_bins(chart_data, bins, limit=8)


            elif stats_type == "continent":
                stats_title = "Number of attendees per continent across meetings"

                country_mapping = get_country_mapping(attendees)

                bins = defaultdict(set)

                for r in attendees:
                    meeting_number = int(r.meeting.number)
                    name = reg_name(r)
                    c = country_mapping.get(r.country_code)

                    if c:
                        bins[(meeting_number, c.continent.name)].add(name)

                add_labeled_top_series_from_bins(chart_data, bins, limit=8)
        data = {
            "chart_data": mark_safe(json.dumps(chart_data)),
            "piechart_data": mark_safe(json.dumps(piechart_data)),
            "table_data": table_data,
            "stats_title": stats_title,
            "possible_stats_types": possible_stats_types,
            "stats_type": stats_type,
            "bin_size": bin_size,
            "meeting": meeting,
            "eu_countries": sorted(eu_countries or [], key=lambda c: c.name),
            "content_template": "stats/meeting_stats_{}.html".format(template_name),
        }
        log("Cache miss for '%s'.  Data size: %sk" % (cache_key, len(str(data))/1000))
        cache.set(cache_key, data, 24*60*60)
    #
    return render(request, "stats/meeting_stats.html", data)


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
