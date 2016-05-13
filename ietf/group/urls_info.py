# Copyright The IETF Trust 2008, All Rights Reserved

from django.conf.urls import patterns, include
from django.views.generic import RedirectView

from ietf.group import views, views_edit

urlpatterns = patterns('',
    (r'^$', views.active_groups), 
    (r'^summary.txt', RedirectView.as_view(url='/wg/1wg-summary.txt')),
    (r'^summary-by-area.txt', RedirectView.as_view(url='/wg/1wg-summary.txt')),
    (r'^summary-by-acronym.txt', RedirectView.as_view(url='/wg/1wg-summary-by-acronym.txt')),
    (r'^1wg-summary.txt', views.wg_summary_area),
    (r'^1wg-summary-by-acronym.txt', views.wg_summary_acronym),
    (r'^1wg-charters.txt', views.wg_charters),
    (r'^1wg-charters-by-acronym.txt', views.wg_charters_by_acronym),
    (r'^chartering/$', RedirectView.as_view(url='/group/chartering/')),
    (r'^chartering/create/$', RedirectView.as_view(url='/group/chartering/create/%(group_type)s/')),
    (r'^bofs/$', views.bofs),
    (r'^email-aliases/$', 'ietf.group.views.email_aliases'),
    (r'^bofs/create/$', views_edit.edit, {'action': "create"}, "bof_create"),
    (r'^(?P<acronym>[a-zA-Z0-9-._]+)/', include('ietf.group.urls_info_details')),
)
