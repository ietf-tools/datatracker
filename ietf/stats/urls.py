# Copyright The IETF Trust 2016-2026, All Rights Reserved
# -*- coding: utf-8 -*-


from django.conf import settings

from ietf.stats import views
from ietf.utils.urls  import url
from ietf.stats import views_authors, views_documents, views_meetings, views_reviews

urlpatterns = [
    url(r"^$", views.stats_index),
    url(r"^authors/(?P<doc_type>all|draft|wg-draft|rfc)/(?P<stats_type>affiliation|country)/$", views_authors.authors_timeline),
    url(r"^total/authors/(?P<doc_type>all|draft|wg-draft|rfc)/(?P<stats_type>affiliation|country)/$", views_authors.authors_total),
    url(r"^documents/(?P<doc_type>draft|rfc)/(?P<stats_type>level|stream|wg)/$", views_documents.documents_timeline),
    url(r"^total/documents/(?P<doc_type>draft|rfc)/(?P<stats_type>level|stream|wg)/$", views_documents.documents_total),
    url(r"^knowncountries/$", views.known_countries_list),
    url(r"^meeting/(?P<meeting_number>\d+)/(?P<stats_type>affiliation|country)/$", views_meetings.meeting_stats),
    url(r"^meeting/(?:(?P<stats_type>affiliation|country|total)/)?$", views_meetings.meetings_timeline),
    url(r"^review/(?:(?P<stats_type>completion|results|states|time)/)?(?:%(acronym)s/)?$" % settings.URL_REGEXPS, views_reviews.review_stats),
    url(r"^annual_report_inputs/(?:(?P<year>\d{4})/)?$", views.annual_report_inputs),
]
