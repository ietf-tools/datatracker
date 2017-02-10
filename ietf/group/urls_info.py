# Copyright The IETF Trust 2008, All Rights Reserved

from django.conf.urls import url, include
from django.views.generic import RedirectView
from django.conf import settings

from ietf.group import views, views_edit

urlpatterns = [
    url(r'^$', views.active_groups), 
    url(r'^summary.txt', RedirectView.as_view(url='/wg/1wg-summary.txt', permanent=True)),
    url(r'^summary-by-area.txt', RedirectView.as_view(url='/wg/1wg-summary.txt', permanent=True)),
    url(r'^summary-by-acronym.txt', RedirectView.as_view(url='/wg/1wg-summary-by-acronym.txt', permanent=True)),
    url(r'^1wg-summary.txt', views.wg_summary_area),
    url(r'^1wg-summary-by-acronym.txt', views.wg_summary_acronym),
    url(r'^1wg-charters.txt', views.wg_charters),
    url(r'^1wg-charters-by-acronym.txt', views.wg_charters_by_acronym),
    url(r'^chartering/$', RedirectView.as_view(url='/group/chartering/', permanent=True)),
    url(r'^chartering/create/$', RedirectView.as_view(url='/group/chartering/create/%(group_type)s/', permanent=True)),
    url(r'^bofs/$', views.bofs),
    url(r'^email-aliases/$', views.email_aliases),
    url(r'^bofs/create/$', views_edit.edit, {'action': "create", }, "bof_create"),
    url(r'^photos/$', views.chair_photos),
    url(r'^%(acronym)s/' % settings.URL_REGEXPS, include('ietf.group.urls_info_details')),
]
