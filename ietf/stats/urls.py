# Copyright The IETF Trust 2016-2026, All Rights Reserved
# -*- coding: utf-8 -*-


from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse as urlreverse

from ietf.stats import views
from ietf.utils.urls  import url
from ietf.stats import views_authors, views_documents, views_meetings, views_reviews

# "total" was renamed to "reg_type" when meetings_timeline moved to views_meetings.py
_OLD_MEETING_STATS_TYPE_MAP = {"total": "reg_type"}

def _redirect_old_meetings_timeline(request, stats_type=None):
    kwargs = {}
    if stats_type is not None:
        kwargs["stats_type"] = _OLD_MEETING_STATS_TYPE_MAP.get(stats_type, stats_type)
    return redirect(urlreverse(views_meetings.meetings_timeline, kwargs=kwargs), permanent=True)

def _redirect_old_document_stats(request):
    """Redirect any old /stats/document/... URL to the stats index.

    On main, document_stats() was a deprecated view that redirected everything
    under /stats/document/ (/, authors/, pages/, author/affiliation/,
    yearly/country/, ...) to the stats index. The per-document-type pages now
    live under /stats/documents/ and /stats/authors/, with different URL shapes,
    so there is no 1:1 mapping: send the visitor to the index to pick a chart.
    """
    return redirect(urlreverse(views.stats_index))

def _redirect_old_meeting_stats(request, meeting_number, stats_type):
    return redirect(
        urlreverse(views_meetings.meeting_stats, kwargs={"meeting_number": meeting_number, "stats_type": stats_type}),
        permanent=True,
    )

# Some URLs have changed during the development, so we need to redirect the old ones to the new ones.

urlpatterns = [
    url(r"^$", views.stats_index),
    url(r"^annual_report_inputs/(?:(?P<year>\d{4})/)?$", views.annual_report_inputs),
    url(r"^authors/(?P<doc_type>all|draft|wg-draft|rfc)/(?P<stats_type>affiliation|country)/total/$", views_authors.authors_total),
    url(r"^authors/(?P<doc_type>all|draft|wg-draft|rfc)/(?P<stats_type>affiliation|country)/$", views_authors.authors_timeline),
    url(r"^document/", _redirect_old_document_stats),
    url(r"^documents/(?P<doc_type>draft|rfc)/(?P<stats_type>level|stream|wg)/total/$", views_documents.documents_total),
    url(r"^documents/(?P<doc_type>draft|rfc)/(?P<stats_type>level|stream|wg)/$", views_documents.documents_timeline),
    url(r"^knowncountries/$", views.known_countries_list),
    url(r"^meeting/(?P<meeting_number>\d+)/(?P<stats_type>affiliation|country)/$", _redirect_old_meeting_stats),
    url(r"^meeting/(?:(?P<stats_type>affiliation|country|total)/)?$", _redirect_old_meetings_timeline),
    url(r"^meetings/(?:(?P<stats_type>affiliation|country|reg_type)/)?$", views_meetings.meetings_timeline),
    url(r"^meetings/(?P<meeting_number>\d+)/(?P<stats_type>affiliation|country)/$", views_meetings.meeting_stats),
    url(r"^review/(?:(?P<stats_type>completion|results|states|time)/)?(?:%(acronym)s/)?$" % settings.URL_REGEXPS, views_reviews.review_stats),
    url(r"^usedaffiliations/$", views.used_affiliations_list),
]
