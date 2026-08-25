# Copyright The IETF Trust 2016-2026, All Rights Reserved


import csv
import datetime

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse as urlreverse
from django.db.models import Count

from ietf.ietfauth.utils import role_required
from ietf.meeting.helpers import get_current_ietf_meeting_num
from ietf.name.models import CountryName
from ietf.doc.models import DocumentAuthor
from ietf.stats.utils import get_aliased_affiliations


def stats_index(request):
    """Render the statistics index page with the current meeting number as it is required by the meeting menu item."""
    current_meeting = get_current_ietf_meeting_num()
    return render(request, "stats/index.html", {
        "current_meeting": current_meeting,
    })

@role_required("LLC Staff")
def used_affiliations_list(request):
    """Render a list of used affiliations in the DocAuthor model with their aliases."""
    qs = (
        DocumentAuthor.objects
        .filter(document__type_id="draft")
        .values('affiliation')
        .annotate(author_count=Count("person", distinct=True))
    )

    affiliations = []
    for row in qs:
        affiliation = row['affiliation']
        author_count = row['author_count']
        aliases_map = get_aliased_affiliations([affiliation])
        if affiliation in aliases_map:
            if aliases_map[affiliation] != affiliation:
                canonical = aliases_map[affiliation]
            else:
                canonical = '' # affiliation is already canonical
        else:
            canonical = '' # Nothing was found, affiliation is assumed to be canonical
        affiliations.append({
            "affiliation": affiliation,
            "author_count": author_count,
            "canonical": canonical,
        })

    return render(request, "stats/used_affiliations_list.html", {
        "affiliations": affiliations,
    })

@role_required("LLC Staff")
def known_countries_list(request):
    """Render a list of known countries with their aliases."""
    countries = CountryName.objects.prefetch_related("countryalias_set")
    for c in countries:
        # the sorting is a bit of a hack - it puts the ISO code first
        # since it was added in a migration
        c.aliases = sorted(c.countryalias_set.all(), key=lambda a: a.pk)

    return render(request, "stats/known_countries_list.html", {
        "countries": countries,
    })

@role_required("LLC Staff")
def annual_report_inputs(request, year=None):
    if year is None and "year" in request.GET:
        return HttpResponseRedirect(
            urlreverse("ietf.stats.views.annual_report_inputs", kwargs={"year": request.GET["year"]}),
        )
    year = int(year) if year else datetime.date.today().year - 1

    from ietf.doc.models import NewRevisionDocEvent
    from ietf.utils.reports import authors_by_year, submitters_by_year, unique_people

    download = request.GET.get("download")
    if download in ("authors", "submitters"):
        addresses = authors_by_year(year) if download == "authors" else submitters_by_year(year)
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{download}-{year}.csv"'
        writer = csv.writer(response)
        writer.writerow(sorted(addresses))
        return response

    authors = authors_by_year(year)
    submitters = submitters_by_year(year)
    author_persons, author_nopersons = unique_people(authors)
    submitter_persons, submitter_nopersons = unique_people(submitters)

    draft_count = len(set(
        NewRevisionDocEvent.objects.filter(
            doc__type_id="draft", time__year=year,
        ).values_list("doc__name", flat=True),
    ))

    return render(request, "stats/annual_report_inputs.html", {
        "year": year,
        "author_count": len(authors),
        "submitter_count": len(submitters),
        "author_person_count": author_persons.count(),
        "author_noperson_count": len(author_nopersons),
        "submitter_person_count": submitter_persons.count(),
        "submitter_noperson_count": len(submitter_nopersons),
        "draft_count": draft_count,
    })
