# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.conf import settings

from ietf.stats import views
from ietf.utils.urls  import url

urlpatterns = [
    url(r"^$", views.stats_index),
    url(r"^authors/(?P<doc_type>all|draft|wg-draft|rfc)/(?P<stats_type>affiliation|country)/$", views.authors_timeline),
    url(r"^document/(?P<doc_type>draft|rfc)/(?P<stats_type>level|stream|wg)/$", views.documents_timeline),
    url(r"^knowncountries/$", views.known_countries_list),
    url(r"^meeting/$", views.meetings_timeline),
    url(r"^meeting/(?P<meeting_number>\d+)/(?P<stats_type>affiliation|country)/$", views.meeting_stats),
    url(r"^meeting/(?:(?P<stats_type>affiliation|country|total)/)?$", views.meetings_timeline),
    url(r"^review/(?:(?P<stats_type>completion|results|states|time)/)?(?:%(acronym)s/)?$" % settings.URL_REGEXPS, views.review_stats),
]
