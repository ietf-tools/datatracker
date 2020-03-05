# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.conf import settings

from ietf.stats import views
from ietf.utils.urls  import url

urlpatterns = [
    url(r"^$", views.stats_index),
    url(r"^document/(?:(?P<stats_type>authors|pages|words|format|formlang|author/(?:documents|affiliation|country|continent|citations|hindex)|yearly/(?:affiliation|country|continent))/)?$", views.document_stats),
    url(r"^knowncountries/$", views.known_countries_list),
    url(r"^meeting/(?P<num>\d+)/(?P<stats_type>country|continent)/$", views.meeting_stats),
    url(r"^meeting/(?:(?P<stats_type>overview|country|continent)/)?$", views.meeting_stats),
    url(r"^review/(?:(?P<stats_type>completion|results|states|time)/)?(?:%(acronym)s/)?$" % settings.URL_REGEXPS, views.review_stats),
]
